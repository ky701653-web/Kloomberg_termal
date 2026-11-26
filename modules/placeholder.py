"""Placeholder view for modules scheduled in Stages 2 through 6."""

from __future__ import annotations

import streamlit as st

from utils.ui import render_section_header

STAGE_MAP = {
    "Watchlist": ("Stage 2", "User-defined NSE/BSE watchlist persisted in SQLite with sparklines and 52-week ranges."),
    "Charting": ("Stage 2", "Plotly candlesticks, volume, SMA/EMA 20/50/200, RSI, MACD, Bollinger Bands, Supertrend, VWAP, and Nifty rebased-to-100 comparison."),
    "Fundamentals": ("Stage 3", "Income statement, balance sheet, cash flow, quarterly results, ratios (P/E, P/B, ROE, ROCE, D/E), and peer comparison."),
    "Screener": ("Stage 3", "Filter NSE stocks by valuation, momentum, RSI, 52W proximity, volume spikes, plus prebuilt and saved screens."),
    "Sector & Nifty Heatmap": ("Stage 3", "Interactive treemap heatmaps colored by % change for Nifty 50 and NSE sectors."),
    "F&O / Options": ("Stage 4", "Option chain for Nifty, Bank Nifty, and stocks with PCR, max pain, OI charts, and India VIX trend."),
    "FII/DII Flows": ("Stage 4", "Daily and monthly FII/DII net buy/sell flows with charts."),
    "Macro Dashboard": ("Stage 5", "RBI repo rate, India CPI, IIP, GDP, 10Y G-Sec, forex reserves, US 10Y, DXY, and Fed funds rate."),
    "News Feed": ("Stage 5", "Aggregated Indian & global financial RSS feeds with ticker/sector filtering and VADER sentiment tags."),
    "Corporate Actions & Filings": ("Stage 5", "Results calendar, dividends, splits, bonuses, board meetings, and BSE/NSE announcements."),
    "IPO Tracker": ("Stage 5", "Upcoming, open, and recently listed Indian IPOs with subscription status and listing gains."),
    "Mutual Funds": ("Stage 6", "Search any Indian mutual fund scheme via AMFI / mfapi.in with NAV history, CAGR, and SIP calculator."),
    "Portfolio Tracker": ("Stage 6", "Holdings entry/CSV import, P&L, XIRR, sector allocation, beta vs Nifty, Sharpe, max drawdown, and capital-gains tax estimate."),
    "Crypto & FX (INR)": ("Stage 6", "Top cryptocurrencies quoted in INR (CoinGecko) and major FX pairs against INR."),
    "Alerts": ("Stage 6", "Price, % move, RSI, and MA crossover alerts in-app plus optional Telegram/email delivery."),
}


def render_placeholder(module_name: str) -> None:
    """Render an honest 'Scheduled for Stage X' screen for upcoming modules."""
    stage, desc = STAGE_MAP.get(module_name, ("Upcoming Stage", "Module scheduled in a later stage."))
    render_section_header(f"{module_name} — {stage}")

    active_ticker = st.session_state.get("active_ticker")
    if active_ticker:
        st.info(f"Command Bar routed successfully with active security: **{active_ticker}**")

    st.markdown(
        f"""
        **Status:** Not built yet — scheduled for **{stage}**.

        **Planned scope:** {desc}
        """
    )
    if st.button("← Back to Home / Market Overview"):
        st.session_state["active_module"] = "Home / Market Overview"
        st.rerun()
