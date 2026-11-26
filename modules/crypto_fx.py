"""Module 15: Crypto & FX Panels Quoted in INR (CoinGecko + Frankfurter)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.macro_news_mf import fetch_crypto_inr, fetch_fx_inr
from utils.formatting import format_inr, format_pct
from utils.ui import render_csv_download, render_metric_card, render_section_header, style_change_dataframe


def render_crypto_fx() -> None:
    """Render INR Crypto leaderboard (CoinGecko) and Global FX pairs vs INR (Frankfurter)."""
    render_section_header("Crypto & Global FX Quoted in INR")

    tab_fx, tab_crypto = st.tabs(["Global FX vs INR (Frankfurter)", "Cryptocurrencies in INR (CoinGecko)"])

    with tab_fx:
        with st.spinner("Loading ECB/Frankfurter FX reference rates..."):
            fx_rows, fx_stale, fx_ts = fetch_fx_inr(ttl_seconds=1800)
        if fx_stale:
            st.warning(f"Showing cached FX rates from {fx_ts}.")
        else:
            st.caption(f"Source: Frankfurter ECB Reference API | Updated: {fx_ts}")

        if fx_rows:
            top4 = fx_rows[:4]
            cols = st.columns(len(top4))
            for col, item in zip(cols, top4):
                with col:
                    render_metric_card(
                        label=item["pair"],
                        value_str=f"₹{item['inr_per_unit']:.4f}",
                        subtext=f"₹100 = {item['units_per_100_inr']:.2f} {item['currency']}",
                    )

            # Interactive INR Converter
            c1, c2, c3 = st.columns([2, 1.5, 2])
            amt = c1.number_input("Amount in Foreign Currency", min_value=1.0, value=1000.0, step=100.0, key="fx_conv_amt")
            cur_sel = c2.selectbox("Currency", options=[r["currency"] for r in fx_rows], key="fx_conv_cur")
            rate_row = next(r for r in fx_rows if r["currency"] == cur_sel)
            inr_val = amt * rate_row["inr_per_unit"]
            c3.metric(f"Converted Value ({cur_sel} → INR)", format_inr(inr_val))

            df_fx = pd.DataFrame(fx_rows)
            df_fx.columns = ["Pair", "Currency", "1 Unit in INR (₹)", "Units per ₹100", "ECB Date"]
            st.dataframe(df_fx, width="stretch", hide_index=True)
            render_csv_download(df_fx, "fx_inr_rates.csv", label="Download FX Rates CSV")
        else:
            st.info("FX rates unavailable right now.")

    with tab_crypto:
        with st.spinner("Loading CoinGecko INR crypto market data..."):
            c_rows, c_stale, c_ts = fetch_crypto_inr(ttl_seconds=180)
        if c_stale:
            st.warning(f"Showing cached crypto quotes from {c_ts}.")
        else:
            st.caption(f"Source: CoinGecko Free API (INR) | Updated: {c_ts}")

        if c_rows:
            df_c = pd.DataFrame(
                [
                    {
                        "Rank": r["rank"],
                        "Asset": f"{r['name']} ({r['symbol']})",
                        "Price (₹)": format_inr(r["price_inr"]),
                        "24h %": format_pct(r["chg_24h"]),
                        "7d %": format_pct(r["chg_7d"]),
                        "Market Cap": format_inr(r["market_cap_inr"], compact=True),
                        "24h Vol": format_inr(r["volume_24h_inr"], compact=True),
                        "7D Trend": r["sparkline"],
                    }
                    for r in c_rows
                ]
            )
            st.dataframe(
                style_change_dataframe(df_c, ["24h %", "7d %"]),
                width="stretch",
                hide_index=True,
                column_config={
                    "7D Trend": st.column_config.LineChartColumn("7D Sparkline", width="medium"),
                },
            )
            render_csv_download(df_c.drop(columns=["7D Trend"]), "crypto_inr.csv", label="Download Crypto INR CSV")
        else:
            st.info("CoinGecko quotes temporarily unavailable or rate-limited.")
