"""Module 3: Technical Charting (Candlesticks, Indicators, Multi-Ticker & Nifty Rebased)."""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from data.market_data import fetch_multi_close, fetch_ohlcv
from modules.command_bar import normalize_indian_ticker
from utils.formatting import format_inr, format_pct
from utils.indicators import (
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
    compute_supertrend,
    compute_vwap,
)
from utils.ui import render_csv_download, render_section_header

TIMEFRAMES = {
    "5D (15m)": ("5d", "15m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
    "3Y": ("3y", "1d"),
    "5Y": ("5y", "1d"),
    "MAX": ("max", "1wk"),
}


def render_charting() -> None:
    """Render interactive Plotly candlestick + indicator + rebased comparison view."""
    render_section_header("Technical Charting & Rebased Benchmark Comparison")

    default_sym = st.session_state.get("active_ticker") or "RELIANCE.NS"

    top_c1, top_c2, top_c3 = st.columns([2.5, 2.5, 2])
    with top_c1:
        raw_ticker = st.text_input("Primary Ticker", value=default_sym, key="chart_ticker_input")
        ticker = normalize_indian_ticker(raw_ticker or "RELIANCE.NS")
        st.session_state["active_ticker"] = ticker
    with top_c2:
        compare_raw = st.text_input(
            "Compare Tickers (comma-separated, optional)",
            placeholder="e.g. TCS, INFY",
            key="chart_compare_input",
        )
    with top_c3:
        tf_label = st.selectbox("Timeframe", options=list(TIMEFRAMES.keys()), index=3, key="chart_tf")

    period, interval = TIMEFRAMES[tf_label]

    # Indicator Toggles
    with st.expander("Technical Overlays & Oscillators", expanded=True):
        i1, i2, i3, i4, i5, i6, i7 = st.columns(7)
        show_sma20 = i1.checkbox("SMA 20", value=True)
        show_sma50 = i2.checkbox("SMA 50", value=False)
        show_ema20 = i3.checkbox("EMA 20", value=False)
        show_bb = i4.checkbox("Bollinger (20,2)", value=False)
        show_st = i5.checkbox("Supertrend (10,3)", value=False)
        show_vwap = i6.checkbox("VWAP", value=False)
        show_rsi = i7.checkbox("RSI (14)", value=True)

        j1, j2, j3 = st.columns(3)
        show_macd = j1.checkbox("MACD (12,26,9)", value=False)
        show_sma200 = j2.checkbox("SMA 200", value=False)
        rebase_nifty = j3.checkbox("Rebase vs Nifty 50 (^NSEI = 100)", value=False)

    with st.spinner(f"Loading OHLCV for {ticker}..."):
        df, is_stale, ts_ist = fetch_ohlcv(ticker, period=period, interval=interval, ttl_seconds=120)

    if df is None or df.empty:
        st.error(f"No price history found for `{ticker}`. Verify the symbol (e.g., `RELIANCE.NS` or `TCS.BO`).")
        return

    if is_stale:
        st.warning(f"Showing cached bars from {ts_ist}.")

    last_close = float(df["Close"].iloc[-1])
    prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else last_close
    pct = (last_close - prev_close) / prev_close * 100.0 if prev_close else 0.0
    st.caption(f"**{ticker}** | Last Close: **{format_inr(last_close)}** ({format_pct(pct)}) | Bars: {len(df)} | Cached: {ts_ist}")

    # Build subplot rows dynamically
    extra_panels = int(show_rsi) + int(show_macd)
    total_rows = 2 + extra_panels
    if total_rows == 2:
        row_heights = [0.76, 0.24]
    elif total_rows == 3:
        row_heights = [0.60, 0.18, 0.22]
    else:
        row_heights = [0.50, 0.14, 0.18, 0.18]

    fig = make_subplots(
        rows=total_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    # Row 1: Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=ticker,
            increasing_line_color="#00C805",
            decreasing_line_color="#FF3B30",
        ),
        row=1,
        col=1,
    )

    if show_sma20:
        fig.add_trace(go.Scatter(x=df.index, y=compute_sma(df["Close"], 20), name="SMA 20", line=dict(color="#FF8C00", width=1.4)), row=1, col=1)
    if show_sma50:
        fig.add_trace(go.Scatter(x=df.index, y=compute_sma(df["Close"], 50), name="SMA 50", line=dict(color="#38BDF8", width=1.4)), row=1, col=1)
    if show_sma200:
        fig.add_trace(go.Scatter(x=df.index, y=compute_sma(df["Close"], 200), name="SMA 200", line=dict(color="#C084FC", width=1.6)), row=1, col=1)
    if show_ema20:
        fig.add_trace(go.Scatter(x=df.index, y=compute_ema(df["Close"], 20), name="EMA 20", line=dict(color="#FACC15", width=1.3, dash="dot")), row=1, col=1)
    if show_bb:
        ub, mb, lb = compute_bollinger_bands(df["Close"], 20, 2.0)
        fig.add_trace(go.Scatter(x=df.index, y=ub, name="BB Upper", line=dict(color="#64748B", width=1, dash="dash")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=lb, name="BB Lower", line=dict(color="#64748B", width=1, dash="dash"), fill="tonexty", fillcolor="rgba(100,116,139,0.12)"), row=1, col=1)
    if show_st:
        st_line, st_dir = compute_supertrend(df, 10, 3.0)
        st_bull = st_line.where(st_dir > 0)
        st_bear = st_line.where(st_dir < 0)
        fig.add_trace(go.Scatter(x=df.index, y=st_bull, name="Supertrend (+)", line=dict(color="#00C805", width=1.6)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=st_bear, name="Supertrend (-)", line=dict(color="#FF3B30", width=1.6)), row=1, col=1)
    if show_vwap:
        fig.add_trace(go.Scatter(x=df.index, y=compute_vwap(df), name="VWAP", line=dict(color="#F472B6", width=1.4)), row=1, col=1)

    # Row 2: Volume
    vol_colors = ["#00C805" if c >= o else "#FF3B30" for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["Volume"], name="Volume", marker_color=vol_colors, opacity=0.75),
        row=2,
        col=1,
    )

    cur_row = 3
    if show_rsi:
        rsi = compute_rsi(df["Close"], 14)
        fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI (14)", line=dict(color="#FF8C00", width=1.5)), row=cur_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#FF3B30", line_width=0.8, row=cur_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#00C805", line_width=0.8, row=cur_row, col=1)
        fig.update_yaxes(range=[0, 100], title_text="RSI", row=cur_row, col=1)
        cur_row += 1

    if show_macd:
        macd_line, sig_line, hist = compute_macd(df["Close"])
        hist_colors = ["#00C805" if v >= 0 else "#FF3B30" for v in hist.fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=hist, name="MACD Hist", marker_color=hist_colors, opacity=0.65), row=cur_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD", line=dict(color="#38BDF8", width=1.3)), row=cur_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=sig_line, name="Signal", line=dict(color="#FF8C00", width=1.3)), row=cur_row, col=1)
        fig.update_yaxes(title_text="MACD", row=cur_row, col=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#0D0F12",
        height=640 if extra_panels == 0 else (760 if extra_panels == 1 else 860),
        margin=dict(l=12, r=12, t=28, b=12),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
    )
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="Vol", row=2, col=1)
    st.plotly_chart(fig, width="stretch")

    # Multi-ticker / Nifty 50 Rebased Comparison
    compare_list = [normalize_indian_ticker(t) for t in compare_raw.split(",") if t.strip()]
    if rebase_nifty or compare_list:
        comp_tickers = [ticker] + compare_list
        if rebase_nifty and "^NSEI" not in comp_tickers:
            comp_tickers.append("^NSEI")
        comp_period = "6mo" if period in ("5d", "1mo", "3mo") else period
        close_df, _, _ = fetch_multi_close(comp_tickers, period=comp_period, ttl_seconds=180)
        if not close_df.empty:
            render_section_header("Rebased Performance Comparison (Start = 100)")
            rebased = close_df.ffill().dropna()
            if not rebased.empty:
                rebased = (rebased / rebased.iloc[0]) * 100.0
                fig_cmp = go.Figure()
                for col_name in rebased.columns:
                    fig_cmp.add_trace(go.Scatter(x=rebased.index, y=rebased[col_name], name=str(col_name), mode="lines"))
                fig_cmp.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#000000",
                    plot_bgcolor="#0D0F12",
                    height=340,
                    margin=dict(l=12, r=12, t=20, b=12),
                    yaxis_title="Indexed (Base = 100)",
                )
                st.plotly_chart(fig_cmp, width="stretch")

    export_df = df.reset_index()
    render_csv_download(export_df, f"{ticker}_ohlcv.csv", label="Download OHLCV CSV")
