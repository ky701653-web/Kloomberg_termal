"""Module 1: Home / Market Overview with Parallel Loading & AI Daily Market Summary."""

from __future__ import annotations

import html
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from data.macro_news_mf import fetch_news_feed
from data.market_data import (
    GLOBAL_INDICES,
    INDIAN_INDICES,
    MACRO_COMMODITIES,
    fetch_usd_inr_frankfurter,
    fetch_yfinance_quotes,
)
from data.nse_data import fetch_nse_nifty50_breadth_and_movers
from utils.formatting import format_inr, format_number, format_pct
from utils.market_hours import get_market_status
from utils.market_summary import generate_ai_market_summary
from utils.ui import (
    get_theme_palette,
    render_csv_download,
    render_metric_card,
    render_section_header,
    style_change_dataframe,
)


def _fetch_macro_bundle() -> Tuple[List[Dict[str, Any]], bool, str]:
    items = [(name, sym) for name, sym, _ in MACRO_COMMODITIES]
    rows, is_stale, ts_ist = fetch_yfinance_quotes(
        items, cache_key="home_macro_commodities", ttl_seconds=60
    )
    if not any(r["symbol"] == "INR=X" for r in rows):
        fx_fallback = fetch_usd_inr_frankfurter()
        if fx_fallback:
            rows = [fx_fallback] + list(rows)
    return rows, is_stale, ts_ist


def _load_home_parallel() -> Dict[str, Any]:
    """Fetch all Home panels concurrently to minimize cold-load latency."""
    with ThreadPoolExecutor(max_workers=5) as pool:
        f_ind = pool.submit(fetch_yfinance_quotes, INDIAN_INDICES, "home_indian_indices", 60)
        f_mac = pool.submit(_fetch_macro_bundle)
        f_glob = pool.submit(fetch_yfinance_quotes, GLOBAL_INDICES, "home_global_indices", 60)
        f_brd = pool.submit(fetch_nse_nifty50_breadth_and_movers, 60)
        f_news = pool.submit(fetch_news_feed, None, 600)

        ind_res = f_ind.result()
        mac_res = f_mac.result()
        glob_res = f_glob.result()
        brd_res = f_brd.result()
        news_res = f_news.result()

    return {
        "indian": ind_res,
        "macro": mac_res,
        "global": glob_res,
        "breadth": brd_res,
        "news": news_res,
    }


def _render_movers_table(rows: List[Dict[str, Any]], csv_name: str) -> None:
    if not rows:
        st.info("No data available right now. Check Data Source Status for details.")
        return
    df = pd.DataFrame(
        [
            {
                "Symbol": r["name"],
                "LTP (₹)": format_inr(r["price"]),
                "Chg": f"{r['change']:+.2f}",
                "% Chg": format_pct(r["pct_change"]),
                "High": format_inr(r["high"]) if r.get("high") is not None else "N/A",
                "Low": format_inr(r["low"]) if r.get("low") is not None else "N/A",
            }
            for r in rows
        ]
    )
    st.dataframe(
        style_change_dataframe(df, ["Chg", "% Chg"], ["LTP (₹)", "Chg", "% Chg", "High", "Low"]),
        width="stretch",
        hide_index=True,
    )
    render_csv_download(df, csv_name, label="CSV")


def _render_dashboard_body() -> None:
    """Render all live overview panels (called inside optional auto-refresh fragment)."""
    pal = get_theme_palette()

    # 1. Market Status Banner (IST)
    status = get_market_status()
    pill_class = (
        "it-pill-open"
        if status.state == "OPEN"
        else ("it-pill-pre" if status.state == "PRE-OPEN" else "it-pill-closed")
    )
    next_open_str = (
        f" | Next open: {status.next_open_ist.strftime('%a %d %b, %I:%M %p IST')}"
        if status.next_open_ist
        else ""
    )
    st.markdown(
        f"""
        <div class="it-status-bar">
            <span class="{pill_class}">NSE {html.escape(status.state)}</span>
            <span>{html.escape(status.reason)}</span>
            <span class="it-mono" style="color:{pal['muted']}; margin-left:auto;">{html.escape(status.timestamp_str + next_open_str)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    active_ticker = st.session_state.get("active_ticker")
    if active_ticker:
        st.caption(
            f"Active security from Command Bar: **{active_ticker}** "
            f"(try `{active_ticker.replace('.NS', '')} GP`, `FA`, or `BT`)"
        )

    with st.spinner("Loading Indian benchmarks, macro, breadth, and market brief..."):
        bundle = _load_home_parallel()

    ind_rows, ind_stale, ind_ts = bundle["indian"]
    macro_rows, macro_stale, macro_ts = bundle["macro"]
    glob_rows, glob_stale, glob_ts = bundle["global"]
    breadth, breadth_stale, breadth_ts = bundle["breadth"]
    headlines, _, _ = bundle["news"]

    # AI / NLP Daily Market Summary
    render_section_header("AI Daily Market Summary")
    summary_md, summary_engine, summary_ts = generate_ai_market_summary(
        indices=ind_rows,
        macro=macro_rows,
        breadth=breadth,
        headlines=headlines,
        ttl_seconds=300,
    )
    with st.container(border=True):
        st.markdown(summary_md)
        st.caption(f"Engine: **{summary_engine}** | Updated: {summary_ts}")

    # 2. Indian Benchmark Indices
    render_section_header("Indian Benchmark Indices (NSE / BSE — ~15 min delayed via yfinance)")
    if ind_stale:
        st.warning(f"Showing last cached Indian index quotes from {ind_ts} (live fetch failed).")

    if ind_rows:
        cols = st.columns(len(ind_rows))
        for col, item in zip(cols, ind_rows):
            with col:
                render_metric_card(
                    label=f"{item['name']} ({item['symbol']})",
                    value_str=format_number(item["price"]),
                    change=item["change"],
                    pct_change=item["pct_change"],
                )
        ind_df = pd.DataFrame(ind_rows)[["name", "symbol", "price", "change", "pct_change"]]
        ind_df.columns = ["Index", "Ticker", "Last", "Chg", "% Chg"]
        render_csv_download(ind_df, "indian_indices.csv", label="Download Indian Indices CSV")
    else:
        st.error("Unable to fetch Indian benchmark indices. Check internet connection or Data Source Status.")

    # 3. Macro FX & Commodities
    render_section_header("INR FX & Commodities")
    if macro_stale:
        st.warning(f"Showing cached FX/commodity snapshot from {macro_ts}.")

    prefix_map = {sym: pfx for _, sym, pfx in MACRO_COMMODITIES}
    if macro_rows:
        m_cols = st.columns(len(macro_rows))
        for col, item in zip(m_cols, macro_rows):
            pfx = prefix_map.get(item["symbol"], "₹" if "INR" in item["symbol"] else "$")
            with col:
                render_metric_card(
                    label=item["name"],
                    value_str=format_number(item["price"], prefix=pfx),
                    change=item["change"],
                    pct_change=item["pct_change"],
                )
    else:
        st.info("FX and commodity quotes temporarily unavailable.")

    # 4. Nifty 50 Breadth + Top Gainers & Losers
    render_section_header("Nifty 50 Market Breadth & Top Movers")
    if breadth_stale:
        st.warning(f"Showing cached Nifty 50 breadth/movers from {breadth_ts}.")

    adv = int(breadth.get("advances", 0))
    dec = int(breadth.get("declines", 0))
    unc = int(breadth.get("unchanged", 0))
    total = adv + dec + unc

    if total > 0:
        adv_pct = adv / total * 100
        dec_pct = dec / total * 100
        unc_pct = unc / total * 100
        src_safe = html.escape(str(breadth.get("source", "N/A")))
        ts_safe = html.escape(str(breadth_ts))
        st.markdown(
            f"""
            <div style="margin-bottom:6px; font-size:0.84rem;">
                <span class="it-mono" style="color:{pal['up']}; font-weight:600;">Advances: {adv} ({adv_pct:.0f}%)</span>
                &nbsp;|&nbsp;
                <span class="it-mono" style="color:{pal['down']}; font-weight:600;">Declines: {dec} ({dec_pct:.0f}%)</span>
                &nbsp;|&nbsp;
                <span class="it-mono" style="color:{pal['muted']};">Unchanged: {unc}</span>
                <span style="color:{pal['muted']}; float:right; font-size:0.78rem;">Source: {src_safe} | Updated: {ts_safe}</span>
            </div>
            <div style="display:flex; height:8px; width:100%; border-radius:999px; overflow:hidden; margin-bottom:12px;">
                <div style="width:{adv_pct:.1f}%; background:{pal['up']};"></div>
                <div style="width:{unc_pct:.1f}%; background:{pal['muted']};"></div>
                <div style="width:{dec_pct:.1f}%; background:{pal['down']};"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col_gain, col_lose = st.columns(2)
    with col_gain:
        st.markdown(f"<strong style='color:{pal['up']}; font-size:0.85rem;'>TOP 5 GAINERS (NIFTY 50)</strong>", unsafe_allow_html=True)
        _render_movers_table(breadth.get("gainers", []), "nifty50_top_gainers.csv")
    with col_lose:
        st.markdown(f"<strong style='color:{pal['down']}; font-size:0.85rem;'>TOP 5 LOSERS (NIFTY 50)</strong>", unsafe_allow_html=True)
        _render_movers_table(breadth.get("losers", []), "nifty50_top_losers.csv")

    # 5. Global Indices Table
    render_section_header("Global Markets Snapshot")
    if glob_stale:
        st.warning(f"Showing cached global indices from {glob_ts}.")
    if glob_rows:
        g_df = pd.DataFrame(
            [
                {
                    "Index": r["name"],
                    "Ticker": r["symbol"],
                    "Last": format_number(r["price"]),
                    "Chg": f"{r['change']:+.2f}",
                    "% Chg": format_pct(r["pct_change"]),
                }
                for r in glob_rows
            ]
        )
        st.dataframe(
            style_change_dataframe(g_df, ["Chg", "% Chg"], ["Last", "Chg", "% Chg"]),
            width="stretch",
            hide_index=True,
        )
        render_csv_download(g_df, "global_indices.csv", label="Download Global Indices CSV")
    else:
        st.info("Global index quotes temporarily unavailable.")


def render_home() -> None:
    """Entry point for Module 1: Home / Market Overview."""
    ctrl_col1, ctrl_col2 = st.columns([3, 1])
    with ctrl_col1:
        refresh_choice = st.radio(
            "Auto-refresh",
            options=["Off", "30s", "60s"],
            horizontal=True,
            key="home_auto_refresh",
        )
    with ctrl_col2:
        if st.button("Refresh Now", width="stretch"):
            from utils.cache import terminal_cache

            terminal_cache.clear_kv_cache()
            st.cache_data.clear()
            st.rerun()

    if refresh_choice == "30s":
        @st.fragment(run_every=30)
        def _auto_30() -> None:
            _render_dashboard_body()

        _auto_30()
    elif refresh_choice == "60s":
        @st.fragment(run_every=60)
        def _auto_60() -> None:
            _render_dashboard_body()

        _auto_60()
    else:
        _render_dashboard_body()
