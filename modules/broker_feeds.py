"""Module 19: Real-Time Indian Broker API Connector (Zerodha Kite, Upstox v2, Angel One) & Disclosures."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.broker_data import fetch_angel_quote, fetch_upstox_quote, fetch_zerodha_quote
from utils.formatting import format_indian_commas, format_inr, format_pct
from utils.secrets import get_secret
from utils.ui import render_metric_card, render_section_header

BROKER_OPTIONS = [
    {
        "Broker": "Zerodha (Kite Connect)",
        "Real-Time Ticks": "Yes (REST + WebSocket)",
        "Typical API Cost": "Paid monthly subscription (check Zerodha personal tier)",
        "Env Keys": "ZERODHA_API_KEY, ZERODHA_ACCESS_TOKEN",
        "Notes": "Pass NSE symbol like RELIANCE or NSE:RELIANCE.",
    },
    {
        "Broker": "Upstox (v2 API)",
        "Real-Time Ticks": "Yes (REST + WebSocket)",
        "Typical API Cost": "Free with active Upstox demat account",
        "Env Keys": "UPSTOX_ACCESS_TOKEN",
        "Notes": "Pass instrument key like NSE_EQ|INE002A01018.",
    },
    {
        "Broker": "Angel One (SmartAPI)",
        "Real-Time Ticks": "Yes (REST + SmartWebSocket)",
        "Typical API Cost": "Free with Angel One trading account",
        "Env Keys": "ANGEL_API_KEY, ANGEL_ACCESS_TOKEN",
        "Notes": "Pass NSE symbol token (e.g. 2885 for RELIANCE, 3045 for SBIN).",
    },
]


def render_broker_feeds() -> None:
    """Render live broker quote tester (when keys set in .env) and disclosures."""
    render_section_header("Real-Time Broker APIs (Zerodha • Upstox • Angel One)")

    z_ready = bool(get_secret("ZERODHA_API_KEY") and get_secret("ZERODHA_ACCESS_TOKEN"))
    u_ready = bool(get_secret("UPSTOX_ACCESS_TOKEN"))
    a_ready = bool(get_secret("ANGEL_API_KEY") and get_secret("ANGEL_ACCESS_TOKEN"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zerodha Kite", "Configured" if z_ready else "Not Set (.env)")
    c2.metric("Upstox v2", "Configured" if u_ready else "Not Set (.env)")
    c3.metric("Angel One SmartAPI", "Configured" if a_ready else "Not Set (.env)")
    c4.metric("FRED Macro Key", "Configured" if get_secret("FRED_API_KEY") else "Not Set")

    render_section_header("Fetch Real-Time Quote via Configured Broker")
    b1, b2, b3 = st.columns([2, 3, 1])
    broker = b1.selectbox(
        "Select Broker",
        options=["Zerodha Kite Connect", "Upstox v2", "Angel One SmartAPI"],
        key="broker_sel",
    )
    default_ident = (
        "RELIANCE.NS"
        if broker == "Zerodha Kite Connect"
        else ("NSE_EQ|INE002A01018" if broker == "Upstox v2" else "2885")
    )
    ident = b2.text_input(
        "Symbol / Instrument Key / Token",
        value=default_ident,
        help="Zerodha: RELIANCE or NSE:RELIANCE | Upstox: NSE_EQ|INE002A01018 | Angel One: 2885",
        key="broker_ident",
    )
    fetch_clicked = b3.button("Fetch Live", width="stretch", type="primary")

    if fetch_clicked:
        with st.spinner(f"Querying {broker}..."):
            if broker == "Zerodha Kite Connect":
                quote, err = fetch_zerodha_quote(ident)
            elif broker == "Upstox v2":
                quote, err = fetch_upstox_quote(ident)
            else:
                quote, err = fetch_angel_quote(ident)

        if err:
            st.warning(f"{broker}: {err}")
        elif quote:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                render_metric_card(
                    f"{quote['symbol']} ({quote['broker']})",
                    format_inr(quote["ltp"]),
                    change=quote["change"],
                    pct_change=quote["pct_change"],
                )
            with m2:
                render_metric_card("Day High / Low", f"{format_inr(quote.get('high'))} / {format_inr(quote.get('low'))}")
            with m3:
                render_metric_card("Prev Close", format_inr(quote.get("prev_close")))
            with m4:
                render_metric_card("Volume", format_indian_commas(quote.get("volume"), 0))
            st.caption(f"Exchange timestamp: {quote.get('timestamp') or 'N/A'}")

    render_section_header("Supported Indian Broker APIs & Keys")
    st.dataframe(pd.DataFrame(BROKER_OPTIONS), width="stretch", hide_index=True)

    st.markdown(
        """
        ### Important Data, Legal & Coverage Notes
        - **Delay:** Without a broker API key, `yfinance` and free feeds are delayed (~15 minutes) or end-of-day.
        - **Unofficial Endpoints:** `yfinance` and NSE public endpoints are unofficial and can change or rate-limit without notice. Cached SQLite fallbacks keep the terminal usable during outages.
        - **Fundamentals Accuracy:** Yahoo Finance fundamental coverage for Indian stocks can be incomplete or inconsistent — cross-check key numbers against official **BSE/NSE corporate filings**.
        - **What Is Not Available Free:** Institutional Bloomberg features (proprietary credit/bond/derivatives pricing, Bloomberg messaging/IB chat, full historical tick archives) are excluded; free sources cover roughly **70–80%** of individual-investor workflows.
        - **Legality & Terms:** Respect every provider's Terms of Service and rate limits. Use this app strictly for **personal research** — do not redistribute or resell data.
        - **Not Investment Advice:** All indicators, screens, backtests, and VADER sentiment tags are research tools only. Always verify before trading with real money.
        """
    )
