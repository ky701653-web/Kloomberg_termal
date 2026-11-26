"""Module 11: Corporate Actions & NSE Exchange Filings."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.nse_data import fetch_corporate_actions_and_filings
from modules.command_bar import normalize_indian_ticker
from utils.ui import render_csv_download, render_section_header


def render_corporate_actions() -> None:
    """Render NSE corporate actions, exchange filings, and Yahoo dividend/split history."""
    render_section_header("Corporate Actions & Exchange Filings (Dividends • Splits • Bonuses • Announcements)")

    default_sym = (st.session_state.get("active_ticker") or "").replace(".NS", "").replace(".BO", "")
    c1, c2 = st.columns([4, 1])
    with c1:
        ticker_filter = st.text_input(
            "Filter by NSE Symbol (leave blank for market-wide NSE actions & filings)",
            value=default_sym,
            placeholder="e.g. RELIANCE, TCS, INFY",
            key="corp_ticker_filter",
        ).strip().upper()
    with c2:
        if st.button("Load Actions", width="stretch", type="primary"):
            if ticker_filter:
                st.session_state["active_ticker"] = normalize_indian_ticker(ticker_filter)
            st.rerun()

    with st.spinner("Fetching corporate actions and exchange filings..."):
        bundle, is_stale, ts_ist = fetch_corporate_actions_and_filings(ticker=ticker_filter or None, ttl_seconds=1800)

    if is_stale:
        st.warning(f"Showing cached corporate actions from {ts_ist}.")
    else:
        st.caption(f"Updated: {ts_ist}")

    tab_act, tab_ann, tab_div = st.tabs(["NSE Corporate Actions", "NSE Announcements / Filings", "Dividend & Split History (yfinance)"])

    with tab_act:
        actions = bundle.get("actions", [])
        if actions:
            df_act = pd.DataFrame(actions)
            st.dataframe(df_act, width="stretch", hide_index=True)
            render_csv_download(df_act, "nse_corporate_actions.csv", label="Download Actions CSV")
        else:
            st.info("No NSE corporate actions returned (NSE may be blocking requests or no records match the filter).")

    with tab_ann:
        anns = bundle.get("announcements", [])
        if anns:
            df_ann = pd.DataFrame(anns)
            st.dataframe(df_ann, width="stretch", hide_index=True)
            render_csv_download(df_ann, "nse_announcements.csv", label="Download Announcements CSV")
        else:
            st.info("No NSE corporate announcements returned.")

    with tab_div:
        divs = bundle.get("yf_dividends", [])
        splits = bundle.get("yf_splits", [])
        if not ticker_filter:
            st.info("Enter an NSE symbol above (e.g., `TCS` or `ITC`) to view historical dividends and stock splits.")
        else:
            col_d, col_s = st.columns(2)
            with col_d:
                st.subheader(f"{ticker_filter} Dividends (₹/share)")
                if divs:
                    df_d = pd.DataFrame(divs)
                    st.dataframe(df_d, width="stretch", hide_index=True)
                    render_csv_download(df_d, f"{ticker_filter}_dividends.csv", label="Dividends CSV")
                else:
                    st.info("No dividend history found.")
            with col_s:
                st.subheader(f"{ticker_filter} Splits / Bonuses")
                if splits:
                    df_s = pd.DataFrame(splits)
                    st.dataframe(df_s, width="stretch", hide_index=True)
                else:
                    st.info("No split events found.")
