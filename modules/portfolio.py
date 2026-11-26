"""Module 14: Portfolio Tracker (Manual/CSV, P&L, XIRR, Beta, Sharpe, Drawdown, Indian Capital Gains)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

from data.market_data import fetch_multi_close, fetch_watchlist_quotes
from modules.command_bar import normalize_indian_ticker
from utils.cache import terminal_cache
from utils.formatting import format_inr, format_pct
from utils.portfolio_math import compute_portfolio_metrics, compute_xirr, estimate_indian_capital_gains
from utils.ui import render_csv_download, render_metric_card, render_section_header, style_change_dataframe

SAMPLE_CSV = (
    "symbol,qty,buy_price,buy_date,notes\n"
    "RELIANCE.NS,10,1250.00,2024-06-15,Core energy & retail\n"
    "TCS.NS,5,3650.00,2025-09-10,IT core\n"
    "HDFCBANK.NS,15,1580.00,2025-12-01,Banking\n"
)


def render_portfolio() -> None:
    """Render Portfolio Tracker with XIRR, risk metrics, allocation, and capital-gains estimate."""
    render_section_header("Portfolio Tracker (P&L • XIRR • Risk Metrics • Indian Capital Gains Estimate)")

    tab_add, tab_csv, tab_manage = st.tabs(["Add Lot Manually", "Import CSV", "Manage / Clear"])

    with tab_add:
        with st.form("port_add_form", clear_on_submit=True):
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1.3, 1.5, 2])
            sym_in = c1.text_input("Ticker", placeholder="RELIANCE or TCS.BO")
            qty_in = c2.number_input("Qty", min_value=0.01, value=10.0, step=1.0)
            price_in = c3.number_input("Buy Price (₹)", min_value=0.01, value=1000.0, step=10.0)
            date_in = c4.date_input("Buy Date", value=date(2025, 1, 15))
            notes_in = c5.text_input("Notes (optional)", placeholder="Long term")
            if st.form_submit_button("Add Holding", type="primary"):
                if sym_in.strip():
                    norm = normalize_indian_ticker(sym_in)
                    terminal_cache.add_holding(norm, qty_in, price_in, date_in.isoformat(), notes_in)
                    st.success(f"Added {qty_in:g} × {norm} @ ₹{price_in:,.2f}")
                    st.rerun()

    with tab_csv:
        st.download_button(
            "Download Sample Portfolio CSV",
            data=SAMPLE_CSV.encode("utf-8"),
            file_name="sample_india_portfolio.csv",
            mime="text/csv",
        )
        uploaded = st.file_uploader("Upload CSV (columns: symbol, qty, buy_price, buy_date)", type=["csv"])
        if uploaded is not None:
            try:
                imp_df = pd.read_csv(uploaded)
                required = {"symbol", "qty", "buy_price", "buy_date"}
                if not required.issubset({c.strip().lower() for c in imp_df.columns}):
                    st.error("CSV must contain columns: `symbol`, `qty`, `buy_price`, `buy_date`.")
                else:
                    imp_df.columns = [c.strip().lower() for c in imp_df.columns]
                    added = 0
                    for _, row in imp_df.iterrows():
                        sym = normalize_indian_ticker(str(row["symbol"]))
                        terminal_cache.add_holding(
                            sym,
                            float(row["qty"]),
                            float(row["buy_price"]),
                            str(row["buy_date"])[:10],
                            str(row.get("notes", "") or ""),
                        )
                        added += 1
                    st.success(f"Imported {added} holding lots.")
                    st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"CSV import failed: {exc}")

    holdings = terminal_cache.get_holdings()
    with tab_manage:
        if holdings:
            del_opts = {f"#{h['id']} — {h['symbol']} ({h['qty']} @ ₹{h['buy_price']}, {h['buy_date']})": h["id"] for h in holdings}
            c_del, c_btn1, c_btn2 = st.columns([3, 1, 1])
            sel_del = c_del.selectbox("Select lot to delete", options=list(del_opts.keys()))
            if c_btn1.button("Delete Lot", width="stretch"):
                terminal_cache.delete_holding(del_opts[sel_del])
                st.rerun()
            if c_btn2.button("Clear All", width="stretch"):
                terminal_cache.clear_holdings()
                st.rerun()
        else:
            st.info("No saved holdings yet.")

    if not holdings:
        st.info("Your portfolio is empty. Add a stock lot above or import a CSV to see live valuation, XIRR, risk metrics, and capital-gains estimates.")
        return

    tickers = sorted({h["symbol"] for h in holdings})
    with st.spinner("Valuing portfolio against live NSE/BSE prices and Nifty 50..."):
        quotes, is_stale, ts_ist = fetch_watchlist_quotes(tickers, ttl_seconds=60)
        hist_closes, _, _ = fetch_multi_close(tickers + ["^NSEI"], period="1y", ttl_seconds=300)

    if is_stale:
        st.warning(f"Using cached prices from {ts_ist}.")

    price_map = {q["symbol"]: q for q in quotes}

    enriched_lots: List[Dict[str, Any]] = []
    cashflows = []
    total_invested = 0.0
    total_current = 0.0
    total_day_pnl = 0.0

    for h in holdings:
        sym = h["symbol"]
        qty = float(h["qty"])
        buy_p = float(h["buy_price"])
        q = price_map.get(sym, {})
        cur_p = float(q.get("price") or buy_p)
        day_chg = float(q.get("change") or 0.0)

        invested = qty * buy_p
        current = qty * cur_p
        pnl = current - invested
        pnl_pct = (pnl / invested * 100.0) if invested > 0 else 0.0

        total_invested += invested
        total_current += current
        total_day_pnl += qty * day_chg
        cashflows.append((h["buy_date"], -invested))

        enriched_lots.append(
            {
                "symbol": sym,
                "qty": qty,
                "buy_price": buy_p,
                "current_price": cur_p,
                "buy_date": h["buy_date"],
                "invested": round(invested, 2),
                "current_value": round(current, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )

    cashflows.append((date.today(), total_current))
    xirr = compute_xirr(cashflows)
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100.0) if total_invested > 0 else 0.0

    # Portfolio Risk Metrics from current weights over 1Y history
    risk_metrics: Dict[str, Any] = {}
    if not hist_closes.empty and total_current > 0:
        avail_syms = [s for s in tickers if s in hist_closes.columns]
        if avail_syms:
            weights = {}
            for lot in enriched_lots:
                if lot["symbol"] in avail_syms:
                    weights[lot["symbol"]] = weights.get(lot["symbol"], 0.0) + lot["current_value"] / total_current
            stock_rets = hist_closes[avail_syms].ffill().pct_change().dropna(how="all").fillna(0.0)
            port_rets = sum(stock_rets[s] * w for s, w in weights.items())
            bench_rets = hist_closes["^NSEI"].ffill().pct_change().dropna() if "^NSEI" in hist_closes.columns else None
            risk_metrics = compute_portfolio_metrics(port_rets, bench_rets, risk_free_rate=0.065)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        render_metric_card("Total Invested", format_inr(total_invested, compact=True))
    with m2:
        render_metric_card("Current Value", format_inr(total_current, compact=True), change=total_day_pnl, subtext="1D P&L")
    with m3:
        render_metric_card("Unrealized P&L", format_inr(total_pnl, compact=True), change=total_pnl, pct_change=total_pnl_pct)
    with m4:
        render_metric_card("Portfolio XIRR", format_pct(xirr * 100.0) if xirr is not None else "N/A")
    with m5:
        beta = risk_metrics.get("beta")
        render_metric_card("Beta vs Nifty 50", f"{beta:.2f}" if beta is not None else "N/A")

    r1, r2, r3 = st.columns(3)
    with r1:
        vol = risk_metrics.get("annualized_volatility")
        render_metric_card("Ann. Volatility (1Y)", format_pct(vol * 100.0, show_sign=False) if vol is not None else "N/A")
    with r2:
        sharpe = risk_metrics.get("sharpe_ratio")
        render_metric_card("Sharpe Ratio (Rf=6.5%)", f"{sharpe:.2f}" if sharpe is not None else "N/A")
    with r3:
        mdd = risk_metrics.get("max_drawdown")
        render_metric_card("Max Drawdown (1Y)", format_pct(mdd * 100.0) if mdd is not None else "N/A")

    df_lots = pd.DataFrame(enriched_lots)
    disp = pd.DataFrame(
        {
            "Symbol": df_lots["symbol"],
            "Qty": df_lots["qty"],
            "Buy Date": df_lots["buy_date"],
            "Buy Price": df_lots["buy_price"].apply(format_inr),
            "LTP": df_lots["current_price"].apply(format_inr),
            "Invested": df_lots["invested"].apply(format_inr),
            "Current": df_lots["current_value"].apply(format_inr),
            "P&L": df_lots["pnl"].apply(lambda v: f"{v:+,.2f}"),
            "P&L %": df_lots["pnl_pct"].apply(format_pct),
        }
    )
    st.dataframe(style_change_dataframe(disp, ["P&L", "P&L %"]), width="stretch", hide_index=True)
    render_csv_download(df_lots, "india_portfolio_holdings.csv", label="Download Holdings CSV")

    col_alloc, col_tax = st.columns(2)
    with col_alloc:
        render_section_header("Allocation Breakdown")
        alloc_df = df_lots.groupby("symbol", as_index=False)["current_value"].sum()
        fig_pie = px.pie(alloc_df, names="symbol", values="current_value", hole=0.45)
        fig_pie.update_layout(template="plotly_dark", paper_bgcolor="#000000", height=340, margin=dict(l=8, r=8, t=12, b=8))
        st.plotly_chart(fig_pie, width="stretch")

    with col_tax:
        render_section_header("Indian Capital Gains Tax Estimate (Unrealized)")
        cg = estimate_indian_capital_gains(enriched_lots)
        st.caption(
            f"**Rates applied (Finance Act 2024):** Listed Equity **STCG = {cg['stcg_rate_pct']:.1f}%** (u/s 111A, held ≤ 12 months) | "
            f"**LTCG = {cg['ltcg_rate_pct']:.1f}%** (u/s 112A, held > 12 months, after **₹1.25 lakh** annual exemption). "
            "Educational estimate only — consult a CA before filing."
        )
        tax_df = pd.DataFrame(
            [
                {"Bucket": "STCG (≤ 12 Months)", "Net Gain": format_inr(cg["stcg_gain"]), "Taxable": format_inr(cg["taxable_stcg"]), "Est. Tax (20%)": format_inr(cg["estimated_stcg_tax"])},
                {"Bucket": "LTCG (> 12 Months)", "Net Gain": format_inr(cg["ltcg_gain"]), "Taxable (after ₹1.25L)": format_inr(cg["taxable_ltcg"]), "Est. Tax (12.5%)": format_inr(cg["estimated_ltcg_tax"])},
                {"Bucket": "TOTAL ESTIMATED TAX", "Net Gain": format_inr(cg["stcg_gain"] + cg["ltcg_gain"]), "Taxable": "—", "Est. Tax (20%/12.5%)": format_inr(cg["total_estimated_tax"])},
            ]
        )
        st.dataframe(tax_df, width="stretch", hide_index=True)
