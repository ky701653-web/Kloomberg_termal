"""Module 2: Persistent NSE/BSE Watchlist with 52W range, sparklines, and 60s TTL cache."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.market_data import DEFAULT_WATCHLIST, fetch_watchlist_quotes
from modules.command_bar import normalize_indian_ticker
from utils.cache import terminal_cache
from utils.formatting import format_indian_commas, format_inr, format_pct
from utils.ui import render_csv_download, render_section_header, style_change_dataframe


def render_watchlist() -> None:
    """Render the persistent NSE/BSE Watchlist tab."""
    render_section_header("NSE / BSE Watchlist (60s SQLite Cache • Local Persistence)")

    col_add, col_btn, col_ref = st.columns([4, 1, 1])
    with col_add:
        new_ticker_raw = st.text_input(
            "Add NSE/BSE Ticker",
            placeholder="e.g. RELIANCE, TCS, TATAPOWER, TCS.BO, NIFTY",
            label_visibility="collapsed",
            key="wl_add_input",
        )
    with col_btn:
        if st.button("Add Ticker", width="stretch", type="primary"):
            if new_ticker_raw.strip():
                norm = normalize_indian_ticker(new_ticker_raw)
                terminal_cache.add_watchlist_ticker(norm)
                st.success(f"Added {norm} to watchlist.")
                st.rerun()
    with col_ref:
        if st.button("Refresh", width="stretch", key="wl_refresh"):
            st.cache_data.clear()
            st.rerun()

    tickers = terminal_cache.get_watchlist(default_tickers=DEFAULT_WATCHLIST)
    if not tickers:
        st.info("Your watchlist is empty. Add an NSE or BSE ticker above (e.g. `RELIANCE` or `TCS.BO`).")
        return

    with st.spinner("Fetching 60s cached watchlist quotes..."):
        rows, is_stale, ts_ist = fetch_watchlist_quotes(tickers, ttl_seconds=60)

    if is_stale:
        st.warning(f"Showing cached watchlist snapshot from {ts_ist}.")
    else:
        st.caption(f"Last updated: {ts_ist} (TTL: 60s)")

    if rows:
        df_display = pd.DataFrame(
            [
                {
                    "Symbol": r["symbol"],
                    "LTP (₹)": format_inr(r["price"]),
                    "Chg": f"{r['change']:+.2f}",
                    "% Chg": format_pct(r["pct_change"]),
                    "Volume": format_indian_commas(r["volume"], decimals=0),
                    "52W Low": format_inr(r["low_52w"]),
                    "52W High": format_inr(r["high_52w"]),
                    "52W Pos %": r["pos_52w_pct"],
                    "25D Trend": r["sparkline"],
                }
                for r in rows
            ]
        )
        st.dataframe(
            style_change_dataframe(df_display, ["Chg", "% Chg"]),
            width="stretch",
            hide_index=True,
            column_config={
                "52W Pos %": st.column_config.ProgressColumn(
                    "52W Range",
                    help="Position between 52-week low (0%) and 52-week high (100%)",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
                "25D Trend": st.column_config.LineChartColumn(
                    "25D Sparkline",
                    width="medium",
                ),
            },
        )
        csv_df = df_display.drop(columns=["25D Trend"])
        render_csv_download(csv_df, "india_terminal_watchlist.csv", label="Download Watchlist CSV")
    else:
        st.warning("Could not load quotes for current watchlist tickers.")

    # Quick actions: open Chart / Fundamentals or remove ticker
    st.markdown("---")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        selected = st.selectbox("Select ticker for action", options=tickers, key="wl_action_ticker")
    with c2:
        if st.button("Open Chart (GP)", width="stretch", key="wl_to_gp"):
            st.session_state["active_ticker"] = selected
            st.session_state["active_module"] = "Charting"
            st.rerun()
    with c3:
        if st.button("Fundamentals (FA)", width="stretch", key="wl_to_fa"):
            st.session_state["active_ticker"] = selected
            st.session_state["active_module"] = "Fundamentals"
            st.rerun()
    with c4:
        if st.button("Remove", width="stretch", key="wl_remove"):
            terminal_cache.remove_watchlist_ticker(selected)
            st.rerun()
