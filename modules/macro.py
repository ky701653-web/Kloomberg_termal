"""Module 9: India & Global Macro Dashboard (RBI, MOSPI, World Bank, FRED, yfinance)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.macro_news_mf import fetch_macro_dashboard
from data.market_data import fetch_yfinance_quotes
from utils.formatting import format_number
from utils.ui import render_csv_download, render_metric_card, render_section_header


def render_macro() -> None:
    """Render India & Global Macro Dashboard."""
    render_section_header("India & Global Macro Dashboard (RBI / MOSPI / World Bank / FRED)")

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
        st.info(
            "Optional: Add a free `FRED_API_KEY` to `.env` (or Streamlit Secrets) to enable live FRED series "
            "(US Fed Funds, US 10Y, India CPI index, India 10Y rate, FRED USD/INR)."
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
        render_section_header("India Macro Indicators (World Bank Open Data)")
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
        fig_wb = go.Figure()
        fig_wb.add_trace(
            go.Bar(
                x=[p["date"] for p in pts],
                y=[p["value"] for p in pts],
                marker_color="#FF8C00",
                name=wb[sel_wb]["label"],
            )
        )
        fig_wb.update_layout(
            template="plotly_dark",
            paper_bgcolor="#000000",
            plot_bgcolor="#0D0F12",
            height=320,
        )
        st.plotly_chart(fig_wb, width="stretch")

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
        fig_f = go.Figure()
        fig_f.add_trace(
            go.Scatter(
                x=[p["date"] for p in f_pts],
                y=[p["value"] for p in f_pts],
                mode="lines+markers",
                line=dict(color="#00C805", width=2),
            )
        )
        fig_f.update_layout(template="plotly_dark", paper_bgcolor="#000000", plot_bgcolor="#0D0F12", height=320)
        st.plotly_chart(fig_f, width="stretch")

    # RBI & MOSPI Reference
    render_section_header("RBI & MOSPI Policy Benchmarks")
    ref_df = pd.DataFrame(bundle.get("reference", []))
    if not ref_df.empty:
        st.dataframe(ref_df, width="stretch", hide_index=True)
        render_csv_download(ref_df, "india_macro_reference.csv", label="Download Macro Reference CSV")
    st.caption("Official portals: [RBI Database on Indian Economy](https://dbie.rbi.org.in) • [MOSPI](https://mospi.gov.in)")
