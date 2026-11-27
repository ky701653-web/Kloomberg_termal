"""Module 9: India & Global Macro Dashboard (RBI, MOSPI, World Bank, FRED, yfinance)."""

from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.macro_news_mf import fetch_macro_dashboard
from data.market_data import fetch_yfinance_quotes
from utils.formatting import format_number
from utils.ui import (
    get_plotly_theme,
    get_theme_palette,
    render_csv_download,
    render_metric_card,
    render_plotly,
    render_section_header,
    sanitize_http_url,
)


def render_macro() -> None:
    """Render India & Global Macro Dashboard with live sources & setup guide."""
    render_section_header("India & Global Macro Dashboard (RBI / MOSPI / World Bank / FRED)")
    pal = get_theme_palette()

    with st.spinner("Loading macro indicators..."):
        bundle, is_stale, ts_ist = fetch_macro_dashboard(ttl_seconds=3600)
        live_macro, _, _ = fetch_yfinance_quotes(
            [
                ("USD / INR", "INR=X"),
                ("US 10Y Yield", "^TNX"),
                ("US Dollar Index (DXY)", "DX-Y.NYB"),
                ("Brent Crude ($)", "BZ=F"),
                ("Gold ($)", "GC=F"),
            ],
            cache_key="macro_page_live",
            ttl_seconds=180,
        )

    if is_stale:
        st.warning(f"Showing cached macro data from {ts_ist}.")
    else:
        st.caption(f"Updated: {ts_ist}")

    if not bundle.get("fred_enabled"):
        with st.expander("How to Enable Live FRED Macro Series (Free — Takes 2 Minutes)", expanded=False):
            st.markdown(
                """
                1. Go to **[fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)** and create a free account.
                2. Click **Request API Key** and copy your 32-character key.
                3. **Locally**: open `.env` in your project folder and set `FRED_API_KEY=your_key_here`.
                4. **Streamlit Cloud**: open **App Settings → Secrets** and add `FRED_API_KEY = "your_key_here"`.
                5. Click **Clear SQLite Cache** in *Data Source Status* (or refresh) to load US Fed Funds, US 10Y, India 10Y, India CPI, and FRED USD/INR.
                """
            )

    if live_macro:
        cols = st.columns(len(live_macro))
        for col, item in zip(cols, live_macro):
            with col:
                render_metric_card(
                    label=item["name"],
                    value_str=format_number(item["price"]),
                    change=item["change"],
                    pct_change=item["pct_change"],
                )

    # World Bank India Macro Series
    wb = bundle.get("world_bank", {})
    if wb:
        render_section_header("India Macro Indicators (World Bank Open Data — Free, No Key)")
        wb_cols = st.columns(len(wb))
        for col, (_, info) in zip(wb_cols, wb.items()):
            latest = info["latest"]
            val = latest["value"]
            val_str = f"${val / 1e9:,.1f}B" if "Reserves" in info["label"] else f"{val:.2f}%"
            with col:
                render_metric_card(label=f"{info['label']} ({latest['date']})", value_str=val_str)

        sel_wb = st.selectbox(
            "Chart World Bank Indicator",
            options=list(wb.keys()),
            format_func=lambda k: wb[k]["label"],
            key="macro_wb_sel",
        )
        pts = wb[sel_wb]["history"]
        ptheme = get_plotly_theme()
        fig_wb = go.Figure()
        fig_wb.add_trace(
            go.Bar(
                x=[p["date"] for p in pts],
                y=[p["value"] for p in pts],
                marker_color=ptheme["accent"],
                name=wb[sel_wb]["label"],
            )
        )
        fig_wb.update_layout(height=320)
        render_plotly(fig_wb)

    # FRED Series (when FRED_API_KEY is configured)
    fred_series = bundle.get("fred_series", {})
    if fred_series:
        render_section_header("FRED Live Macro Series")
        f_cols = st.columns(min(4, len(fred_series)))
        for idx, (sid, info) in enumerate(fred_series.items()):
            with f_cols[idx % len(f_cols)]:
                render_metric_card(
                    label=f"{info['label']} ({info['latest']['date']})",
                    value_str=f"{info['latest']['value']}",
                )
        sel_fred = st.selectbox(
            "Plot FRED Series",
            options=list(fred_series.keys()),
            format_func=lambda k: fred_series[k]["label"],
            key="macro_fred_sel",
        )
        f_pts = fred_series[sel_fred]["history"]
        ptheme_f = get_plotly_theme()
        fig_f = go.Figure()
        fig_f.add_trace(
            go.Scatter(
                x=[p["date"] for p in f_pts],
                y=[p["value"] for p in f_pts],
                mode="lines+markers",
                line=dict(color=ptheme_f["up"], width=2),
            )
        )
        fig_f.update_layout(height=320)
        render_plotly(fig_f)

    # Official RBI Press Releases RSS (live, no key)
    rbi_releases = bundle.get("rbi_releases", [])
    if rbi_releases:
        render_section_header("Latest RBI Official Press Releases (Live RSS)")
        for item in rbi_releases[:6]:
            safe_title = html.escape(str(item["title"]))
            safe_pub = html.escape(str(item["published"]))
            safe_link = sanitize_http_url(str(item["link"]))
            st.markdown(
                f"""
                <div class="it-feed-card" style="border-left: 3px solid {pal['accent']};">
                    <div class="it-feed-meta"><span>Reserve Bank of India</span><span class="it-mono">{safe_pub}</span></div>
                    <div class="it-feed-title"><a href="{safe_link}" target="_blank" rel="noopener noreferrer">{safe_title}</a></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # RBI & MOSPI Reference with clickable source links
    render_section_header("Official Macro Data Sources & Portals")
    ref_df = pd.DataFrame(bundle.get("reference", []))
    if not ref_df.empty:
        st.dataframe(
            ref_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Source URL": st.column_config.LinkColumn("Open Source", display_text="Open Portal ↗")
            },
        )
        render_csv_download(ref_df, "india_macro_reference.csv", label="Download Macro Reference CSV")
