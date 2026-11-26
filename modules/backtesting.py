"""Module 20: Strategy Backtesting (MA Crossover & RSI Mean Reversion)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from data.market_data import fetch_ohlcv
from modules.command_bar import normalize_indian_ticker
from utils.backtester import run_ma_crossover_backtest, run_rsi_backtest
from utils.formatting import format_inr, format_pct
from utils.ui import get_plotly_theme, render_csv_download, render_metric_card, render_section_header


def render_backtesting() -> None:
    """Render strategy backtester with equity curve, drawdown, and trade log."""
    render_section_header("Strategy Backtester (MA Crossover & RSI Mean Reversion)")

    default_sym = st.session_state.get("active_ticker") or "RELIANCE.NS"

    c1, c2, c3, c4 = st.columns([2, 2, 1.5, 1.5])
    with c1:
        raw_t = st.text_input("NSE/BSE Ticker", value=default_sym, key="bt_ticker")
        ticker = normalize_indian_ticker(raw_t or "RELIANCE.NS")
        st.session_state["active_ticker"] = ticker
    with c2:
        strategy = st.selectbox("Strategy", options=["MA Crossover", "RSI Mean Reversion"], key="bt_strategy")
    with c3:
        period = st.selectbox("History", options=["1y", "3y", "5y", "max"], index=2, key="bt_period")
    with c4:
        capital = st.number_input("Initial Capital (₹)", min_value=10_000.0, value=100_000.0, step=25_000.0, key="bt_cap")

    p1, p2, p3, p4 = st.columns(4)
    fee_bps = p4.number_input("Cost per Trade (bps)", min_value=0.0, max_value=100.0, value=10.0, step=5.0, key="bt_fee")

    if strategy == "MA Crossover":
        ma_type = p1.selectbox("MA Type", options=["SMA", "EMA"], key="bt_matype")
        fast_w = int(p2.number_input("Fast Window", min_value=3, max_value=100, value=20, key="bt_fast"))
        slow_w = int(p3.number_input("Slow Window", min_value=10, max_value=300, value=50, key="bt_slow"))
    else:
        rsi_period = int(p1.number_input("RSI Period", min_value=5, max_value=50, value=14, key="bt_rsi_p"))
        rsi_buy = float(p2.number_input("Buy when RSI ≤", min_value=5.0, max_value=50.0, value=30.0, key="bt_rsi_buy"))
        rsi_sell = float(p3.number_input("Exit when RSI ≥", min_value=50.0, max_value=95.0, value=70.0, key="bt_rsi_sell"))

    with st.spinner(f"Loading historical OHLCV for {ticker} ({period})..."):
        df, is_stale, ts_ist = fetch_ohlcv(ticker, period=period, interval="1d", ttl_seconds=300)

    if df is None or df.empty or len(df) < 30:
        st.error(f"Insufficient historical data for `{ticker}`.")
        return

    if is_stale:
        st.warning(f"Showing cached bars from {ts_ist}.")

    try:
        if strategy == "MA Crossover":
            if fast_w >= slow_w:
                st.error("Fast MA window must be strictly smaller than Slow MA window.")
                return
            result = run_ma_crossover_backtest(df, fast_window=fast_w, slow_window=slow_w, ma_type=ma_type, initial_capital=capital, fee_bps=fee_bps)
        else:
            if rsi_buy >= rsi_sell:
                st.error("Buy RSI threshold must be strictly lower than Exit RSI threshold.")
                return
            result = run_rsi_backtest(df, period=rsi_period, oversold=rsi_buy, overbought=rsi_sell, initial_capital=capital, fee_bps=fee_bps)
    except ValueError as exc:
        st.error(str(exc))
        return

    m = result["metrics"]
    eq_df = result["equity_df"]
    trades = result["trades"]

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        render_metric_card("Strategy Final", format_inr(m["final_capital"], compact=True), pct_change=m["total_return_pct"])
    with k2:
        render_metric_card("Buy & Hold Final", format_inr(m["bh_final_capital"], compact=True), pct_change=m["bh_return_pct"])
    with k3:
        render_metric_card("Strategy CAGR", format_pct(m["cagr_pct"]))
    with k4:
        sharpe = m["sharpe_ratio"]
        render_metric_card("Sharpe (Rf=6.5%)", f"{sharpe:.2f}" if sharpe is not None else "N/A")
    with k5:
        render_metric_card("Max Drawdown", format_pct(m["max_drawdown_pct"]), subtext=f"B&H: {format_pct(m['bh_max_drawdown_pct'])}")
    with k6:
        render_metric_card("Trades / Win %", f"{m['num_trades']} / {m['win_rate_pct']:.1f}%")

    ptheme = get_plotly_theme()
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.66, 0.34],
        subplot_titles=(f"{ticker} Equity Curve (₹)", "Drawdown (%)"),
    )
    fig.add_trace(go.Scatter(x=eq_df.index, y=eq_df["Strategy"], name="Strategy", line=dict(color=ptheme["accent"], width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=eq_df.index, y=eq_df["Buy_Hold"], name="Buy & Hold", line=dict(color="#38BDF8", width=1.6, dash="dot")), row=1, col=1)

    fig.add_trace(go.Scatter(x=eq_df.index, y=eq_df["Strategy_DD_Pct"], name="Strategy DD %", fill="tozeroy", line=dict(color=ptheme["down"], width=1.4)), row=2, col=1)
    fig.add_trace(go.Scatter(x=eq_df.index, y=eq_df["Buy_Hold_DD_Pct"], name="Buy & Hold DD %", line=dict(color=ptheme["muted"], width=1.1, dash="dot")), row=2, col=1)

    fig.update_layout(
        template=ptheme["template"],
        paper_bgcolor=ptheme["paper_bgcolor"],
        plot_bgcolor=ptheme["plot_bgcolor"],
        font=dict(family="Inter, sans-serif", color=ptheme["font_color"]),
        height=600,
        margin=dict(l=12, r=12, t=36, b=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
    st.plotly_chart(fig, width="stretch")

    render_section_header("Executed Trade Log (1-Bar Lagged Execution • No Lookahead)")
    if trades:
        t_df = pd.DataFrame(trades)
        st.dataframe(t_df, width="stretch", hide_index=True)
        render_csv_download(t_df, f"{ticker}_backtest_trades.csv", label="Download Trade Log CSV")
    else:
        st.info("No closed/open trades generated under current parameters.")
