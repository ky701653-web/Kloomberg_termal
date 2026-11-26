"""Module 1: Home / Market Overview (Indian & Global Benchmarks, Breadth, Movers)."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from data.market_data import (
    GLOBAL_INDICES,
    INDIAN_INDICES,
    MACRO_COMMODITIES,
    fetch_usd_inr_frankfurter,
    fetch_yfinance_quotes,
)
from data.nse_data import fetch_nse_nifty50_breadth_and_movers
from utils.formatting import (
    COLOR_DOWN,
    COLOR_FLAT,
    COLOR_UP,
    format_inr,
    format_number,
    format_pct,
)
from utils.market_hours import get_market_status
from utils.ui import (
    render_csv_download,
    render_metric_card,
    render_section_header,
    style_change_dataframe,
)


@st.cache_data(ttl=60, show_spinner=False)
def _load_indian_indices() -> tuple[List[Dict[str, Any]], bool, str]:
    return fetch_yfinance_quotes(INDIAN_INDICES, cache_key="home_indian_indices", ttl_seconds=60)


@st.cache_data(ttl=60, show_spinner=False)
def _load_macro_commodities() -> tuple[List[Dict[str, Any]], bool, str]:
    items = [(name, sym) for name, sym, _ in MACRO_COMMODITIES]
    rows, is_stale, ts_ist = fetch_yfinance_quotes(
        items, cache_key="home_macro_commodities", ttl_seconds=60
    )
    # If USD/INR failed from yfinance, fall back to Frankfurter ECB reference rate
    has_fx = any(r["symbol"] == "INR=X" for r in rows)
    if not has_fx:
        fx_fallback = fetch_usd_inr_frankfurter()
        if fx_fallback:
            rows.insert(0, fx_fallback)
    return rows, is_stale, ts_ist


@st.cache_data(ttl=60, show_spinner=False)
def _load_global_indices() -> tuple[List[Dict[str, Any]], bool, str]:
    return fetch_yfinance_quotes(GLOBAL_INDICES, cache_key="home_global_indices", ttl_seconds=60)


@st.cache_data(ttl=180, show_spinner=False)
def _load_breadth_and_movers() -> tuple[Dict[str, Any], bool, str]:
    return fetch_nse_nifty50_breadth_and_movers(ttl_seconds=180)


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
        style_change_dataframe(df, ["Chg", "% Chg"]),
        width="stretch",
        hide_index=True,
    )
    render_csv_download(df, csv_name, label="CSV")


def _render_dashboard_body() -> None:
    """Render all live overview panels (called inside optional auto-refresh fragment)."""
    # 1. Market Status Banner (IST)
    status = get_market_status()
    pill_class = (
        "bb-pill-open"
        if status.state == "OPEN"
        else ("bb-pill-pre" if status.state == "PRE-OPEN" else "bb-pill-closed")
    )
    next_open_str = (
        f" | Next open: {status.next_open_ist.strftime('%a %d %b, %I:%M %p IST')}"
        if status.next_open_ist
        else ""
    )
    st.markdown(
        f"""
        <div style="display:flex; flex-wrap:wrap; align-items:center; gap:10px;
                    background:#0D0F12; border:1px solid #22262C; padding:8px 12px;
                    border-radius:3px; margin-bottom:10px; font-size:0.82rem;">
            <span class="{pill_class}">NSE {status.state}</span>
            <span>{status.reason}</span>
            <span style="color:#FF8C00; margin-left:auto;">{status.timestamp_str}{next_open_str}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Active security quick banner if user ran "<TICKER> GO"
    active_ticker = st.session_state.get("active_ticker")
    if active_ticker:
        st.caption(f"Active security from Command Bar: **{active_ticker}** (type `{active_ticker.replace('.NS', '')} GP` for Charting in Stage 2 or `FA` for Fundamentals in Stage 3)")

    # 2. Indian Benchmark Indices
    render_section_header("Indian Benchmark Indices (NSE / BSE — ~15 min delayed via yfinance)")
    with st.spinner("Loading Indian benchmarks..."):
        ind_rows, ind_stale, ind_ts = _load_indian_indices()

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
    macro_rows, macro_stale, macro_ts = _load_macro_commodities()
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
    with st.spinner("Loading Nifty 50 breadth and movers..."):
        breadth, breadth_stale, breadth_ts = _load_breadth_and_movers()

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
        st.markdown(
            f"""
            <div style="margin-bottom:6px; font-size:0.82rem;">
                <span style="color:{COLOR_UP}; font-weight:700;">Advances: {adv} ({adv_pct:.0f}%)</span>
                &nbsp;|&nbsp;
                <span style="color:{COLOR_DOWN}; font-weight:700;">Declines: {dec} ({dec_pct:.0f}%)</span>
                &nbsp;|&nbsp;
                <span style="color:{COLOR_FLAT};">Unchanged: {unc}</span>
                <span style="color:#7A8089; float:right;">Source: {breadth.get('source', 'N/A')} | Updated: {breadth_ts}</span>
            </div>
            <div style="display:flex; height:10px; width:100%; border-radius:2px; overflow:hidden; margin-bottom:12px;">
                <div style="width:{adv_pct:.1f}%; background:{COLOR_UP};"></div>
                <div style="width:{unc_pct:.1f}%; background:{COLOR_FLAT};"></div>
                <div style="width:{dec_pct:.1f}%; background:{COLOR_DOWN};"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col_gain, col_lose = st.columns(2)
    with col_gain:
        st.markdown(f"<strong style='color:{COLOR_UP};'>TOP 5 GAINERS (NIFTY 50)</strong>", unsafe_allow_html=True)
        _render_movers_table(breadth.get("gainers", []), "nifty50_top_gainers.csv")
    with col_lose:
        st.markdown(f"<strong style='color:{COLOR_DOWN};'>TOP 5 LOSERS (NIFTY 50)</strong>", unsafe_allow_html=True)
        _render_movers_table(breadth.get("losers", []), "nifty50_top_losers.csv")

    # 5. Global Indices Table
    render_section_header("Global Markets Snapshot")
    glob_rows, glob_stale, glob_ts = _load_global_indices()
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
            style_change_dataframe(g_df, ["Chg", "% Chg"]),
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
