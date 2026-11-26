"""Module 12: Indian IPO Tracker (NSE Public API + IPO News RSS Fallback)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.nse_data import fetch_ipo_data
from utils.ui import render_csv_download, render_section_header


def render_ipo() -> None:
    """Render Current, Upcoming, and IPO News tracker."""
    render_section_header("Indian IPO Tracker (NSE Mainboard & SME)")

    if st.button("Refresh IPO Feed", key="ipo_refresh"):
        st.rerun()

    with st.spinner("Loading NSE IPO issues and updates..."):
        bundle, is_stale, ts_ist = fetch_ipo_data(ttl_seconds=1800)

    if is_stale:
        st.warning(f"Showing cached IPO data from {ts_ist}.")
    else:
        st.caption(f"Updated: {ts_ist}")

    tab_cur, tab_upc, tab_news = st.tabs(["Active / Current IPOs", "Upcoming IPOs", "Latest Indian IPO Updates (RSS)"])

    with tab_cur:
        cur = bundle.get("current", [])
        if cur:
            df_cur = pd.DataFrame(cur)
            st.dataframe(df_cur, width="stretch", hide_index=True)
            render_csv_download(df_cur, "nse_current_ipos.csv", label="Download Current IPOs CSV")
        else:
            st.info("No active IPO issues returned by NSE right now (NSE may have no open issues today or throttled the API).")

    with tab_upc:
        upc = bundle.get("upcoming", [])
        if upc:
            df_upc = pd.DataFrame(upc)
            st.dataframe(df_upc, width="stretch", hide_index=True)
            render_csv_download(df_upc, "nse_upcoming_ipos.csv", label="Download Upcoming IPOs CSV")
        else:
            st.info("No upcoming IPO filings returned by NSE endpoint right now.")

    with tab_news:
        news = bundle.get("news", [])
        if news:
            for item in news:
                st.markdown(
                    f"""
                    <div style="background:#0D0F12; border:1px solid #22262C; border-left:3px solid #FF8C00;
                                padding:8px 12px; border-radius:3px; margin-bottom:6px;">
                        <div style="font-size:0.74rem; color:#9AA0A6;">{item['published']}</div>
                        <div style="margin-top:2px; font-size:0.88rem;">
                            <a href="{item['link']}" target="_blank" style="color:#E8E8E8; text-decoration:none;">{item['title']}</a>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No IPO news updates available.")
