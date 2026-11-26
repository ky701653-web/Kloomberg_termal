"""Module 7: F&O / Options Chain, PCR, Max Pain, and Open Interest Analysis."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.market_data import fetch_yfinance_quotes
from data.nse_data import fetch_option_chain
from utils.formatting import format_indian_commas, format_number
from utils.ui import get_plotly_theme, render_csv_download, render_metric_card, render_plotly, render_section_header


def render_options_fno() -> None:
    """Render NSE Option Chain, PCR, Max Pain, and OI bar chart."""
    render_section_header("F&O / Option Chain, PCR & Max Pain (NSE + nselib Fallback)")

    active = (st.session_state.get("active_ticker") or "NIFTY").replace("^NSEI", "NIFTY").replace("^NSEBANK", "BANKNIFTY")
    default_sym = active.replace(".NS", "").replace(".BO", "")

    c1, c2, c3 = st.columns([2.5, 2, 1])
    with c1:
        symbol = st.text_input("F&O Symbol (e.g. NIFTY, BANKNIFTY, FINNIFTY, RELIANCE)", value=default_sym, key="opt_sym").strip().upper()
    with c2:
        strike_window = st.slider("Strikes around ATM (+/-)", min_value=5, max_value=25, value=12, key="opt_window")
    with c3:
        if st.button("Load Chain", width="stretch", type="primary"):
            st.rerun()

    # Always show India VIX context
    vix_rows, _, _ = fetch_yfinance_quotes([("India VIX", "^INDIAVIX")], cache_key="opt_vix", ttl_seconds=120)
    vix_val = vix_rows[0]["price"] if vix_rows else None

    with st.spinner(f"Fetching NSE option chain for {symbol}..."):
        bundle, is_stale, ts_ist = fetch_option_chain(symbol, ttl_seconds=120)

    if is_stale:
        st.warning(f"Showing cached option chain from {ts_ist}.")

    rows = bundle.get("rows", [])
    if not rows:
        st.warning(
            f"NSE option chain for `{symbol}` is currently blocked or unavailable ({bundle.get('error', 'No data')}). "
            "NSE frequently throttles automated requests outside browser sessions; check **Data Source Status** or retry shortly."
        )
        if vix_val is not None:
            render_metric_card("India VIX (^INDIAVIX)", format_number(vix_val))
        return

    expiries = bundle.get("expiries", [])
    if len(expiries) > 1:
        sel_exp = st.selectbox("Expiry Date", options=expiries, index=0, key="opt_expiry")
        if sel_exp != bundle.get("selected_expiry"):
            bundle, is_stale, ts_ist = fetch_option_chain(symbol, expiry=sel_exp, ttl_seconds=120)
            rows = bundle.get("rows", [])

    spot = bundle.get("spot")
    pcr_oi = bundle.get("pcr_oi")
    pcr_vol = bundle.get("pcr_vol")
    max_pain = bundle.get("max_pain")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        render_metric_card("Underlying Spot", format_number(spot))
    with m2:
        render_metric_card("PCR (OI)", f"{pcr_oi:.3f}" if pcr_oi is not None else "N/A")
    with m3:
        render_metric_card("PCR (Volume)", f"{pcr_vol:.3f}" if pcr_vol is not None else "N/A")
    with m4:
        render_metric_card("Max Pain Strike", format_number(max_pain, decimals=0))
    with m5:
        render_metric_card("India VIX", format_number(vix_val))

    st.caption(f"Source: {bundle.get('source', 'NSE')} | Expiry: **{bundle.get('selected_expiry', 'N/A')}** | Updated: {ts_ist}")

    df = pd.DataFrame(rows).sort_values("strike")
    if spot and not df.empty:
        atm_idx = (df["strike"] - float(spot)).abs().idxmin()
        atm_pos = df.index.get_loc(atm_idx)
        lo = max(0, int(atm_pos) - strike_window)
        hi = min(len(df), int(atm_pos) + strike_window + 1)
        df_view = df.iloc[lo:hi].copy()
    else:
        df_view = df.head(strike_window * 2 + 1).copy()

    tab_oi, tab_chain, tab_mp = st.tabs(["Open Interest Chart", "Option Chain Table", "Max Pain Curve"])

    with tab_oi:
        ptheme = get_plotly_theme()
        fig_oi = go.Figure()
        fig_oi.add_trace(go.Bar(x=df_view["strike"], y=df_view["ce_oi"], name="Call OI", marker_color=ptheme["down"]))
        fig_oi.add_trace(go.Bar(x=df_view["strike"], y=df_view["pe_oi"], name="Put OI", marker_color=ptheme["up"]))
        if spot:
            fig_oi.add_vline(x=float(spot), line_dash="dash", line_color=ptheme["accent"], annotation_text=f"Spot {spot}")
        if max_pain:
            fig_oi.add_vline(x=float(max_pain), line_dash="dot", line_color="#38BDF8", annotation_text=f"Max Pain {max_pain:.0f}")
        fig_oi.update_layout(
            barmode="group",
            template=ptheme["template"],
            paper_bgcolor=ptheme["paper_bgcolor"],
            plot_bgcolor=ptheme["plot_bgcolor"],
            font=dict(family="Inter, sans-serif", color=ptheme["font_color"]),
            height=420,
            xaxis_title="Strike Price",
            yaxis_title="Open Interest",
        )
        fig_oi.update_xaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
        fig_oi.update_yaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
        render_plotly(fig_oi)

    with tab_chain:
        chain_disp = pd.DataFrame(
            {
                "Call OI": df_view["ce_oi"].apply(lambda v: format_indian_commas(v, 0)),
                "Call Chg OI": df_view["ce_chg_oi"].apply(lambda v: format_indian_commas(v, 0)),
                "Call IV": df_view["ce_iv"].round(2),
                "Call LTP": df_view["ce_ltp"].round(2),
                "STRIKE": df_view["strike"].round(2),
                "Put LTP": df_view["pe_ltp"].round(2),
                "Put IV": df_view["pe_iv"].round(2),
                "Put Chg OI": df_view["pe_chg_oi"].apply(lambda v: format_indian_commas(v, 0)),
                "Put OI": df_view["pe_oi"].apply(lambda v: format_indian_commas(v, 0)),
            }
        )
        st.dataframe(chain_disp, width="stretch", hide_index=True)
        render_csv_download(df_view, f"{symbol}_option_chain.csv", label="Download Option Chain CSV")

    with tab_mp:
        mp_curve = bundle.get("max_pain_curve", [])
        if mp_curve:
            ptheme = get_plotly_theme()
            mp_df = pd.DataFrame(mp_curve)
            fig_mp = go.Figure()
            fig_mp.add_trace(
                go.Scatter(
                    x=mp_df["strike"],
                    y=mp_df["total_payout"],
                    mode="lines+markers",
                    name="Option Buyer Payout",
                    line=dict(color=ptheme["accent"], width=2),
                )
            )
            if max_pain:
                fig_mp.add_vline(x=float(max_pain), line_dash="dash", line_color=ptheme["up"], annotation_text=f"Max Pain: {max_pain:.0f}")
            fig_mp.update_layout(
                template=ptheme["template"],
                paper_bgcolor=ptheme["paper_bgcolor"],
                plot_bgcolor=ptheme["plot_bgcolor"],
                font=dict(family="Inter, sans-serif", color=ptheme["font_color"]),
                height=380,
                xaxis_title="Expiry Settlement Strike",
                yaxis_title="Total Intrinsic Payout",
            )
            fig_mp.update_xaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
            fig_mp.update_yaxes(showgrid=True, gridcolor=ptheme["gridcolor"], zeroline=False)
            render_plotly(fig_mp)
        else:
            st.info("Max pain curve unavailable.")
