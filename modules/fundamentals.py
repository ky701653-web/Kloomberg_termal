"""Module 4: Company Fundamentals (Statements, Quarterly Results, Ratios, Peers)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.market_data import fetch_fundamentals
from modules.command_bar import normalize_indian_ticker
from utils.formatting import format_inr, format_number, format_pct
from utils.ui import render_csv_download, render_metric_card, render_section_header


def _render_statement_table(table_dict: dict, title: str, csv_name: str) -> None:
    cols = table_dict.get("columns", [])
    rows = table_dict.get("rows", [])
    if not rows:
        st.info(f"{title} unavailable from Yahoo Finance for this ticker.")
        return
    df = pd.DataFrame(rows)
    # Scale large financial numbers into ₹ Crores for Indian readability
    num_cols = [c for c in cols if c != "Line Item" and c in df.columns]
    disp = df.copy()
    for c in num_cols:
        disp[c] = disp[c].apply(lambda v: f"{v / 1e7:,.2f} Cr" if pd.notna(v) else "—")
    st.dataframe(disp, width="stretch", hide_index=True)
    render_csv_download(df, csv_name, label=f"Export {title} CSV")


def render_fundamentals() -> None:
    """Render Fundamentals view: ratios, statements, quarterly results, and peers."""
    render_section_header("Fundamentals, Financial Statements & Peer Comparison")

    default_sym = st.session_state.get("active_ticker") or "TCS.NS"
    col_in, col_btn = st.columns([4, 1])
    with col_in:
        raw_t = st.text_input("Ticker", value=default_sym, key="fa_ticker_input")
        ticker = normalize_indian_ticker(raw_t or "TCS.NS")
        st.session_state["active_ticker"] = ticker
    with col_btn:
        if st.button("Load FA", width="stretch", type="primary"):
            st.rerun()

    with st.spinner(f"Fetching fundamentals & peers for {ticker}..."):
        bundle, is_stale, ts_ist = fetch_fundamentals(ticker, ttl_seconds=1800)

    if is_stale:
        st.warning(f"Showing cached fundamentals from {ts_ist}.")
    else:
        st.caption(f"Source: Yahoo Finance | Cached at: {ts_ist}")

    r = bundle.get("ratios", {})
    if not r or r.get("current_price") is None and not bundle.get("income_annual", {}).get("rows"):
        st.error(f"Could not load fundamental data for `{ticker}`.")
        return

    st.subheader(f"{r.get('short_name', ticker)} ({ticker})")
    st.caption(f"Sector: **{r.get('sector', 'N/A')}** | Industry: **{r.get('industry', 'N/A')}**")

    # Key Ratios Row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        render_metric_card("Price", format_inr(r.get("current_price")))
    with m2:
        render_metric_card("Market Cap", format_inr(r.get("market_cap"), compact=True))
    with m3:
        render_metric_card("Trailing P/E", format_number(r.get("pe")))
    with m4:
        render_metric_card("Price / Book", format_number(r.get("pb")))
    with m5:
        render_metric_card("ROE %", format_pct(r.get("roe_pct"), show_sign=False) if r.get("roe_pct") is not None else "N/A")
    with m6:
        render_metric_card("Div Yield", format_pct(r.get("div_yield_pct"), show_sign=False) if r.get("div_yield_pct") is not None else "N/A")

    m7, m8, m9, m10 = st.columns(4)
    with m7:
        render_metric_card("EPS (TTM)", format_inr(r.get("eps")))
    with m8:
        render_metric_card("Debt / Equity", format_number(r.get("debt_to_equity")))
    with m9:
        render_metric_card("Profit Margin", format_pct(r.get("profit_margin_pct"), show_sign=False) if r.get("profit_margin_pct") is not None else "N/A")
    with m10:
        render_metric_card("52W Range", f"{format_inr(r.get('low_52w'))} – {format_inr(r.get('high_52w'))}")

    if r.get("summary"):
        with st.expander("Business Overview", expanded=False):
            st.write(r["summary"])

    tab_q, tab_is, tab_bs, tab_cf, tab_peers = st.tabs(
        ["Quarterly Results", "Annual Income Statement", "Balance Sheet", "Cash Flow", "Sector Peers"]
    )
    with tab_q:
        _render_statement_table(bundle.get("income_quarterly", {}), "Quarterly Results", f"{ticker}_quarterly.csv")
    with tab_is:
        _render_statement_table(bundle.get("income_annual", {}), "Annual Income Statement", f"{ticker}_income.csv")
    with tab_bs:
        _render_statement_table(bundle.get("balance_sheet", {}), "Balance Sheet", f"{ticker}_balance_sheet.csv")
    with tab_cf:
        _render_statement_table(bundle.get("cashflow", {}), "Cash Flow", f"{ticker}_cashflow.csv")
    with tab_peers:
        peers = bundle.get("peers", [])
        if peers:
            p_df = pd.DataFrame(
                [
                    {
                        "Symbol": p.get("symbol"),
                        "Name": p.get("short_name"),
                        "Price (₹)": p.get("current_price"),
                        "Mkt Cap": format_inr(p.get("market_cap"), compact=True),
                        "P/E": round(p["pe"], 2) if p.get("pe") is not None else None,
                        "P/B": round(p["pb"], 2) if p.get("pb") is not None else None,
                        "ROE %": p.get("roe_pct"),
                        "Div Yield %": p.get("div_yield_pct"),
                    }
                    for p in peers
                ]
            )
            st.dataframe(p_df, width="stretch", hide_index=True)
            render_csv_download(p_df, f"{ticker}_peers.csv", label="Export Peers CSV")
        else:
            st.info("No peer comparison data available.")
