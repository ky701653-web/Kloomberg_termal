"""Module 5: Nifty 500 Screener with Prebuilt Screens, Saved Screens, and Batched Caching."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import streamlit as st

from data.market_data import fetch_screener_data, load_nifty500_universe
from utils.cache import terminal_cache
from utils.formatting import format_pct
from utils.ui import render_csv_download, render_section_header, style_change_dataframe

PREBUILT_SCREENS: Dict[str, Dict[str, Any]] = {
    "Custom / All": {},
    "1. Quality Compounders (ROE ≥ 15%, P/E ≤ 35)": {
        "min_roe": 15.0,
        "max_pe": 35.0,
        "min_mcap": 5000.0,
    },
    "2. Momentum Near 52W High (Within 5%, RSI ≥ 55)": {
        "min_pct_from_high": -5.0,
        "min_rsi": 55.0,
        "min_vol_spike": 1.0,
    },
    "3. Value & Dividend Yield (P/B ≤ 3.5, Div ≥ 1.5%)": {
        "max_pb": 3.5,
        "min_div": 1.5,
        "max_pe": 25.0,
    },
}


def render_screener() -> None:
    """Render Nifty 500 Screener with batched yfinance caching and saved presets."""
    render_section_header("Nifty 500 Stock Screener (Batched & Cached)")

    universe = load_nifty500_universe()
    sectors = sorted({u["sector"] for u in universe})

    # Prebuilt & Saved screens bar
    saved_screens = terminal_cache.get_saved_screens()
    all_presets = list(PREBUILT_SCREENS.keys()) + [f"[Saved] {k}" for k in saved_screens.keys()]

    p_col1, p_col2, p_col3 = st.columns([2.5, 1.5, 1])
    with p_col1:
        preset_choice = st.selectbox("Screen Preset", options=all_presets, key="scr_preset")
    with p_col2:
        universe_limit = st.selectbox(
            "Scan Universe Size",
            options=[50, 100, 200, 500],
            index=0,
            help="Batch-fetches 50 tickers at a time with 15-min SQLite caching.",
            key="scr_limit",
        )
    with p_col3:
        include_fund = st.checkbox("Fetch P/E, P/B, ROE", value=True, key="scr_fund_chk")

    active_preset: Dict[str, Any] = {}
    if preset_choice in PREBUILT_SCREENS:
        active_preset = PREBUILT_SCREENS[preset_choice]
    elif preset_choice.startswith("[Saved] "):
        sname = preset_choice.replace("[Saved] ", "", 1)
        active_preset = saved_screens.get(sname, {})

    with st.expander("Screener Filters", expanded=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        sel_sectors = f1.multiselect("Sector", options=sectors, default=active_preset.get("sectors", []))
        min_mcap = f2.number_input("Min Mkt Cap (₹ Cr)", value=float(active_preset.get("min_mcap", 0.0)), step=1000.0)
        max_pe = f3.number_input("Max P/E (0 = off)", value=float(active_preset.get("max_pe", 0.0)), step=5.0)
        max_pb = f4.number_input("Max P/B (0 = off)", value=float(active_preset.get("max_pb", 0.0)), step=0.5)
        min_roe = f5.number_input("Min ROE %", value=float(active_preset.get("min_roe", 0.0)), step=2.0)

        g1, g2, g3, g4, g5 = st.columns(5)
        min_div = g1.number_input("Min Div Yield %", value=float(active_preset.get("min_div", 0.0)), step=0.5)
        min_rsi = g2.number_input("Min RSI (14)", value=float(active_preset.get("min_rsi", 0.0)), step=5.0)
        max_rsi = g3.number_input("Max RSI (14)", value=float(active_preset.get("max_rsi", 100.0)), step=5.0)
        min_pct_from_high = g4.number_input(
            "Min % from 52W High",
            value=float(active_preset.get("min_pct_from_high", -100.0)),
            min_value=-100.0,
            max_value=0.0,
            step=5.0,
        )
        min_vol_spike = g5.number_input("Min Vol Spike (x 20D)", value=float(active_preset.get("min_vol_spike", 0.0)), step=0.2)

    # Save / Delete Screen Controls
    s1, s2, s3 = st.columns([3, 1, 1])
    with s1:
        save_name = st.text_input("Save current filter as preset", placeholder="My Nifty Screen", key="scr_save_name")
    with s2:
        if st.button("Save Screen", width="stretch"):
            if save_name.strip():
                terminal_cache.save_screen(
                    save_name.strip(),
                    {
                        "sectors": sel_sectors,
                        "min_mcap": min_mcap,
                        "max_pe": max_pe,
                        "max_pb": max_pb,
                        "min_roe": min_roe,
                        "min_div": min_div,
                        "min_rsi": min_rsi,
                        "max_rsi": max_rsi,
                        "min_pct_from_high": min_pct_from_high,
                        "min_vol_spike": min_vol_spike,
                    },
                )
                st.success(f"Saved screen '{save_name.strip()}'.")
                st.rerun()
    with s3:
        if preset_choice.startswith("[Saved] "):
            if st.button("Delete Preset", width="stretch"):
                terminal_cache.delete_screen(preset_choice.replace("[Saved] ", "", 1))
                st.rerun()

    filtered_universe = [u for u in universe if not sel_sectors or u["sector"] in sel_sectors][: int(universe_limit)]

    with st.spinner(f"Scanning {len(filtered_universe)} Nifty 500 stocks in batches..."):
        rows, is_stale, ts_ist = fetch_screener_data(
            filtered_universe,
            include_fundamentals=include_fund,
            ttl_seconds=900,
        )

    if is_stale:
        st.warning(f"Showing cached screener snapshot from {ts_ist}.")
    else:
        st.caption(f"Universe: {len(universe)} Nifty 500 symbols loaded locally | Scanned: {len(rows)} | Updated: {ts_ist}")

    if not rows:
        st.info("No screener data available right now.")
        return

    df = pd.DataFrame(rows)
    if sel_sectors:
        df = df[df["sector"].isin(sel_sectors)]
    if min_mcap > 0 and "market_cap_cr" in df.columns:
        df = df[df["market_cap_cr"].fillna(0) >= min_mcap]
    if max_pe > 0:
        df = df[df["pe"].notna() & (df["pe"] <= max_pe) & (df["pe"] > 0)]
    if max_pb > 0:
        df = df[df["pb"].notna() & (df["pb"] <= max_pb) & (df["pb"] > 0)]
    if min_roe > 0:
        df = df[df["roe_pct"].notna() & (df["roe_pct"] >= min_roe)]
    if min_div > 0:
        df = df[df["div_yield_pct"].notna() & (df["div_yield_pct"] >= min_div)]
    if min_rsi > 0:
        df = df[df["rsi_14"].notna() & (df["rsi_14"] >= min_rsi)]
    if max_rsi < 100:
        df = df[df["rsi_14"].notna() & (df["rsi_14"] <= max_rsi)]
    if min_pct_from_high > -100.0:
        df = df[df["pct_from_52w_high"] >= min_pct_from_high]
    if min_vol_spike > 0:
        df = df[df["vol_spike_x"] >= min_vol_spike]

    st.write(f"**Matched {len(df)} stocks**")
    if not df.empty:
        disp = pd.DataFrame(
            {
                "Symbol": df["symbol"],
                "Name": df["name"],
                "Sector": df["sector"],
                "Price (₹)": df["price"],
                "% Chg": df["pct_change"].apply(format_pct),
                "52W High %": df["pct_from_52w_high"].apply(format_pct),
                "RSI (14)": df["rsi_14"],
                "Vol Spike": df["vol_spike_x"].apply(lambda x: f"{x:.2f}x"),
                "Mkt Cap (Cr)": df["market_cap_cr"],
                "P/E": df["pe"],
                "P/B": df["pb"],
                "ROE %": df["roe_pct"],
                "Div %": df["div_yield_pct"],
            }
        )
        st.dataframe(style_change_dataframe(disp, ["% Chg"]), width="stretch", hide_index=True)
        render_csv_download(df, "nifty500_screener_results.csv", label="Download Screener CSV")
