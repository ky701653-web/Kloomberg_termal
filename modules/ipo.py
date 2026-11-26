"""Module 12: Indian IPO Tracker (NSE Public API + IPO News RSS Fallback)."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from data.nse_data import fetch_ipo_data
from utils.ui import get_theme_palette, render_csv_download, render_section_header, sanitize_http_url


def render_ipo() -> None:
    """Render Current, Upcoming, and IPO News tracker."""
    render_section_header("Indian IPO Tracker (NSE Mainboard & SME)")
    pal = get_theme_palette()

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
                safe_pub = html.escape(str(item["published"]))
                safe_title = html.escape(str(item["title"]))
                safe_link = sanitize_http_url(str(item["link"]))
                st.markdown(
                    f"""
                    <div class="it-feed-card" style="border-left: 3px solid {pal['accent']};">
                        <div class="it-feed-meta"><span>{safe_pub}</span></div>
                        <div class="it-feed-title">
                            <a href="{safe_link}" target="_blank" rel="noopener noreferrer">{safe_title}</a>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No IPO news updates available.")
