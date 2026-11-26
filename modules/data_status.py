"""Module 18: Data Source Status panel showing freshness, delays, and errors."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.cache import terminal_cache
from utils.ui import render_csv_download, render_section_header

EXPECTED_SOURCES = [
    {
        "source_name": "Yahoo Finance (yfinance)",
        "delay_note": "~15 min delayed (NSE/BSE); EOD for some indices",
    },
    {
        "source_name": "NSE India Public API",
        "delay_note": "Near real-time (auto-falls back to yfinance / nselib if blocked)",
    },
    {
        "source_name": "Frankfurter FX API",
        "delay_note": "Daily ECB reference rate (free, no key)",
    },
    {
        "source_name": "FRED Macro API",
        "delay_note": "St. Louis Fed macro series (optional FRED_API_KEY)",
    },
    {
        "source_name": "World Bank Macro API",
        "delay_note": "Annual India GDP, CPI, Forex Reserves (free, no key)",
    },
    {
        "source_name": "Indian Financial RSS + VADER",
        "delay_note": "Live RSS from ET, Moneycontrol, Mint, BS, Google News",
    },
    {
        "source_name": "AMFI / mfapi.in Mutual Funds",
        "delay_note": "Daily end-of-day AMFI NAVs",
    },
    {
        "source_name": "CoinGecko Crypto API",
        "delay_note": "Near real-time INR crypto prices (free, rate-limited)",
    },
]


def render_data_status() -> None:
    """Display health, last successful IST fetch time, delay notes, and errors for all sources."""
    render_section_header("Data Source Status & Cache Diagnostics")

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.caption(
            "Every external API call is logged below. If a live feed fails or rate-limits, "
            "the terminal serves the last cached SQLite snapshot and records the error here."
        )
    with col_b:
        if st.button("Clear SQLite Cache", width="stretch"):
            terminal_cache.clear_kv_cache()
            st.cache_data.clear()
            st.success("Cache cleared. Switch to Home or any module to fetch fresh data.")

    recorded = {row["source_name"]: row for row in terminal_cache.get_all_source_statuses()}

    rows = []
    for default in EXPECTED_SOURCES:
        name = default["source_name"]
        rec = recorded.pop(name, None)
        if rec:
            rows.append(
                {
                    "Data Source": name,
                    "Status": rec["status"],
                    "Last Successful Fetch (IST)": rec["last_success_ist"],
                    "Last Attempt (IST)": rec["last_attempt_ist"],
                    "Delay / Freshness": rec["delay_note"],
                    "Last Error / Rate Limit": rec["last_error"] or "None",
                }
            )
        else:
            rows.append(
                {
                    "Data Source": name,
                    "Status": "NOT YET QUERIED",
                    "Last Successful Fetch (IST)": "Never",
                    "Last Attempt (IST)": "Never",
                    "Delay / Freshness": default["delay_note"],
                    "Last Error / Rate Limit": "None",
                }
            )

    for name, rec in recorded.items():
        rows.append(
            {
                "Data Source": name,
                "Status": rec["status"],
                "Last Successful Fetch (IST)": rec["last_success_ist"],
                "Last Attempt (IST)": rec["last_attempt_ist"],
                "Delay / Freshness": rec["delay_note"],
                "Last Error / Rate Limit": rec["last_error"] or "None",
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)
    render_csv_download(df, "data_source_status.csv", label="Download Status CSV")
