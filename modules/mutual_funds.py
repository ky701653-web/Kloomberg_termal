"""Module 13: Indian Mutual Funds Explorer (AMFI / mfapi.in, CAGR, and SIP Calculator)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.macro_news_mf import fetch_mf_nav_history, search_mutual_funds
from utils.formatting import format_inr, format_pct
from utils.ui import render_csv_download, render_metric_card, render_section_header


def compute_sip_projection(monthly_sip: float, years: int, annual_return_pct: float) -> dict:
    """Compute SIP invested capital, estimated wealth, and gain using monthly compounding."""
    months = int(years) * 12
    r_m = (annual_return_pct / 100.0) / 12.0
    invested = monthly_sip * months
    if r_m == 0:
        future_value = invested
    else:
        future_value = monthly_sip * (((1.0 + r_m) ** months - 1.0) / r_m) * (1.0 + r_m)
    return {
        "invested": round(invested, 2),
        "future_value": round(future_value, 2),
        "wealth_gain": round(future_value - invested, 2),
    }


def render_mutual_funds() -> None:
    """Render AMFI / mfapi.in Mutual Fund search, NAV chart, trailing CAGR, and SIP Calculator."""
    render_section_header("Indian Mutual Funds Explorer (AMFI / mfapi.in) & SIP Calculator")

    c1, c2 = st.columns([4, 1])
    with c1:
        mf_query = st.text_input(
            "Search Indian Mutual Fund Scheme",
            value="Nifty 50 Index",
            placeholder="e.g. Parag Parikh Flexi Cap, Nifty 50, SBI Small Cap, HDFC Mid-Cap",
            key="mf_search_input",
        )
    with c2:
        if st.button("Search Schemes", width="stretch", type="primary"):
            st.rerun()

    with st.spinner("Searching AMFI schemes via mfapi.in..."):
        schemes, _ = search_mutual_funds(mf_query, ttl_seconds=3600)

    if not schemes:
        st.warning("No matching mutual fund schemes found or mfapi.in is temporarily unreachable.")
    else:
        sel_scheme = st.selectbox(
            "Select Scheme",
            options=schemes,
            format_func=lambda s: f"{s['schemeName']} (Code: {s['schemeCode']})",
            key="mf_selected_scheme",
        )
        if sel_scheme:
            with st.spinner("Loading NAV history..."):
                nav_bundle, is_stale, ts_ist = fetch_mf_nav_history(sel_scheme["schemeCode"], ttl_seconds=3600)
            if is_stale:
                st.warning(f"Showing cached NAV history from {ts_ist}.")

            meta = nav_bundle.get("meta", {})
            cagr = nav_bundle.get("cagr", {})
            hist = nav_bundle.get("history", [])

            st.caption(
                f"Fund House: **{meta.get('fund_house', 'N/A')}** | "
                f"Category: **{meta.get('scheme_category', 'N/A')}** | "
                f"Latest NAV Date: **{nav_bundle.get('latest_date', 'N/A')}**"
            )

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                render_metric_card("Latest NAV", format_inr(nav_bundle.get("latest_nav")))
            with m2:
                render_metric_card("1Y CAGR", format_pct(cagr.get("1Y")) if "1Y" in cagr else "N/A")
            with m3:
                render_metric_card("3Y CAGR", format_pct(cagr.get("3Y")) if "3Y" in cagr else "N/A")
            with m4:
                render_metric_card("5Y CAGR", format_pct(cagr.get("5Y")) if "5Y" in cagr else "N/A")

            if hist:
                df_nav = pd.DataFrame(hist)
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=df_nav["date"],
                        y=df_nav["nav"],
                        mode="lines",
                        name="NAV (₹)",
                        line=dict(color="#FF8C00", width=2),
                    )
                )
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#000000",
                    plot_bgcolor="#0D0F12",
                    height=360,
                    yaxis_title="NAV (₹)",
                )
                st.plotly_chart(fig, width="stretch")
                render_csv_download(df_nav, f"mf_{sel_scheme['schemeCode']}_nav.csv", label="Download NAV History CSV")

    # SIP Calculator
    render_section_header("SIP Wealth Calculator (INR)")
    s1, s2, s3 = st.columns(3)
    monthly_sip = s1.number_input("Monthly SIP (₹)", min_value=500.0, value=15000.0, step=1000.0, key="sip_amt")
    years = s2.slider("Horizon (Years)", min_value=1, max_value=35, value=10, key="sip_yrs")
    exp_ret = s3.number_input("Expected Annual Return (%)", min_value=1.0, max_value=30.0, value=12.0, step=0.5, key="sip_ret")

    sip_res = compute_sip_projection(monthly_sip, years, exp_ret)
    r1, r2, r3 = st.columns(3)
    with r1:
        render_metric_card("Total Invested", format_inr(sip_res["invested"], compact=True))
    with r2:
        render_metric_card("Estimated Wealth", format_inr(sip_res["future_value"], compact=True))
    with r3:
        render_metric_card("Wealth Gained", format_inr(sip_res["wealth_gain"], compact=True))
