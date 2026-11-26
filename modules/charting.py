"""Module 3: Technical Charting (Clean Candles + SMA 20/50 Default, Sub-Panels & Rebased)."""

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
from utils.ui import get_plotly_theme, render_csv_download, render_plotly, render_section_header

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
    """Render clean Plotly candlestick chart (Candles + SMA 20/50 by default) with optional sub-panels."""
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

    # Default: Candles + SMA 20/50 only; all other overlays & oscillators collapsed behind toggle
    c_sm1, c_sm2, c_sm3 = st.columns([1, 1, 4])
    show_sma20 = c_sm1.checkbox("SMA 20", value=True, key="chk_sma20")
    show_sma50 = c_sm2.checkbox("SMA 50", value=True, key="chk_sma50")

    with st.expander("More Indicators, Volume & Benchmark Comparison", expanded=False):
        i1, i2, i3, i4, i5 = st.columns(5)
        show_volume = i1.checkbox("Volume", value=False, key="chk_vol")
        show_sma200 = i2.checkbox("SMA 200", value=False, key="chk_sma200")
        show_ema20 = i3.checkbox("EMA 20", value=False, key="chk_ema20")
        show_bb = i4.checkbox("Bollinger (20,2)", value=False, key="chk_bb")
        show_st = i5.checkbox("Supertrend (10,3)", value=False, key="chk_st")

        j1, j2, j3, j4 = st.columns(4)
        show_vwap = j1.checkbox("VWAP", value=False, key="chk_vwap")
        show_rsi = j2.checkbox("RSI (14) Panel", value=False, key="chk_rsi")
        show_macd = j3.checkbox("MACD (12,26,9) Panel", value=False, key="chk_macd")
        rebase_nifty = j4.checkbox("Rebase vs Nifty 50", value=False, key="chk_rebase")

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
    st.markdown(
        f"<div style='margin-bottom:8px; font-size:0.86rem;'>"
        f"<span class='it-mono' style='font-weight:600;'>{ticker}</span> &nbsp;|&nbsp; "
        f"Last Close: <span class='it-mono' style='font-weight:600;'>{format_inr(last_close)}</span> "
        f"(<span class='it-mono'>{format_pct(pct)}</span>) &nbsp;|&nbsp; "
        f"<span style='color:var(--muted);'>Bars: {len(df)} • Cached: {ts_ist}</span></div>",
        unsafe_allow_html=True,
    )

    ptheme = get_plotly_theme()
    sub_panels: list[str] = []
    if show_volume:
        sub_panels.append("volume")
    if show_rsi:
        sub_panels.append("rsi")
    if show_macd:
        sub_panels.append("macd")

    total_rows = 1 + len(sub_panels)
    if total_rows == 1:
        row_heights = [1.0]
    elif total_rows == 2:
        row_heights = [0.74, 0.26]
    elif total_rows == 3:
        row_heights = [0.60, 0.20, 0.20]
    else:
        row_heights = [0.52, 0.14, 0.17, 0.17]

    fig = make_subplots(
        rows=total_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=row_heights,
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=ticker,
            increasing_line_color=ptheme["up"],
            increasing_fillcolor=ptheme["up"],
            decreasing_line_color=ptheme["down"],
            decreasing_fillcolor=ptheme["down"],
        ),
        row=1,
        col=1,
    )

    if show_sma20:
        fig.add_trace(
            go.Scatter(x=df.index, y=compute_sma(df["Close"], 20), name="SMA 20", line=dict(color=ptheme["accent"], width=1.5)),
            row=1,
            col=1,
        )
    if show_sma50:
        fig.add_trace(
            go.Scatter(x=df.index, y=compute_sma(df["Close"], 50), name="SMA 50", line=dict(color="#38BDF8", width=1.5)),
            row=1,
            col=1,
        )
    if show_sma200:
        fig.add_trace(
            go.Scatter(x=df.index, y=compute_sma(df["Close"], 200), name="SMA 200", line=dict(color="#A855F7", width=1.5)),
            row=1,
            col=1,
        )
    if show_ema20:
        fig.add_trace(
            go.Scatter(x=df.index, y=compute_ema(df["Close"], 20), name="EMA 20", line=dict(color="#EAB308", width=1.3, dash="dot")),
            row=1,
            col=1,
        )
    if show_bb:
        ub, _, lb = compute_bollinger_bands(df["Close"], 20, 2.0)
        fig.add_trace(go.Scatter(x=df.index, y=ub, name="BB Upper", line=dict(color=ptheme["muted"], width=1, dash="dash")), row=1, col=1)
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=lb,
                name="BB Lower",
                line=dict(color=ptheme["muted"], width=1, dash="dash"),
                fill="tonexty",
                fillcolor="rgba(139, 148, 158, 0.10)",
            ),
            row=1,
            col=1,
        )
    if show_st:
        st_line, st_dir = compute_supertrend(df, 10, 3.0)
        fig.add_trace(go.Scatter(x=df.index, y=st_line.where(st_dir > 0), name="Supertrend (+)", line=dict(color=ptheme["up"], width=1.6)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=st_line.where(st_dir < 0), name="Supertrend (-)", line=dict(color=ptheme["down"], width=1.6)), row=1, col=1)
    if show_vwap:
        fig.add_trace(go.Scatter(x=df.index, y=compute_vwap(df), name="VWAP", line=dict(color="#EC4899", width=1.4)), row=1, col=1)

    cur_row = 2
    for panel in sub_panels:
        if panel == "volume":
            vol_colors = [ptheme["up"] if c >= o else ptheme["down"] for o, c in zip(df["Open"], df["Close"])]
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume", marker_color=vol_colors, opacity=0.7), row=cur_row, col=1)
            fig.update_yaxes(title_text="Vol", row=cur_row, col=1)
        elif panel == "rsi":
            rsi = compute_rsi(df["Close"], 14)
            fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI (14)", line=dict(color=ptheme["accent"], width=1.5)), row=cur_row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color=ptheme["down"], line_width=0.9, row=cur_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color=ptheme["up"], line_width=0.9, row=cur_row, col=1)
            fig.update_yaxes(range=[0, 100], title_text="RSI", row=cur_row, col=1)
        elif panel == "macd":
            macd_line, sig_line, hist = compute_macd(df["Close"])
            hist_colors = [ptheme["up"] if v >= 0 else ptheme["down"] for v in hist.fillna(0)]
            fig.add_trace(go.Bar(x=df.index, y=hist, name="MACD Hist", marker_color=hist_colors, opacity=0.65), row=cur_row, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD", line=dict(color="#38BDF8", width=1.4)), row=cur_row, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=sig_line, name="Signal", line=dict(color=ptheme["accent"], width=1.4)), row=cur_row, col=1)
            fig.update_yaxes(title_text="MACD", row=cur_row, col=1)
        cur_row += 1

    fig.update_layout(
        template=ptheme["template"],
        paper_bgcolor=ptheme["paper_bgcolor"],
        plot_bgcolor=ptheme["plot_bgcolor"],
        font=dict(family="Inter, sans-serif", color=ptheme["font_color"]),
        height=540 if total_rows == 1 else (660 if total_rows == 2 else 780),
        margin=dict(l=12, r=12, t=28, b=12),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    render_plotly(fig)

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
                    template=ptheme["template"],
                    paper_bgcolor=ptheme["paper_bgcolor"],
                    plot_bgcolor=ptheme["plot_bgcolor"],
                    font=dict(family="Inter, sans-serif", color=ptheme["font_color"]),
                    height=340,
                    margin=dict(l=12, r=12, t=20, b=12),
                    yaxis_title="Indexed (Base = 100)",
                )
                fig_cmp.update_xaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
                fig_cmp.update_yaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
                render_plotly(fig_cmp)

    export_df = df.reset_index()
    render_csv_download(export_df, f"{ticker}_ohlcv.csv", label="Download OHLCV CSV")
