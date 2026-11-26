"""
IND TERMINAL — India Bloomberg-Style Financial Terminal
Run locally with: streamlit run app.py
"""

from __future__ import annotations

from typing import Callable, Dict

import streamlit as st
from dotenv import load_dotenv

from modules.alerts import render_alerts
from modules.charting import render_charting
from modules.command_bar import render_command_bar
from modules.corporate_actions import render_corporate_actions
from modules.crypto_fx import render_crypto_fx
from modules.data_status import render_data_status
from modules.fii_dii import render_fii_dii
from modules.fundamentals import render_fundamentals
from modules.heatmap import render_heatmap
from modules.home import render_home
from modules.ipo import render_ipo
from modules.macro import render_macro
from modules.mutual_funds import render_mutual_funds
from modules.news import render_news
from modules.options_fno import render_options_fno
from modules.portfolio import render_portfolio
from modules.screener import render_screener
from modules.watchlist import render_watchlist
from utils.ui import inject_bloomberg_css, render_disclaimer

load_dotenv()

st.set_page_config(
    page_title="IND TERMINAL // Free Indian Market Terminal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

MODULE_GROUPS: Dict[str, list[str]] = {
    "MARKETS & SCREENING": [
        "Home / Market Overview",
        "Watchlist",
        "Charting",
        "Fundamentals",
        "Screener",
        "Sector & Nifty Heatmap",
    ],
    "NSE DERIVATIVES & FLOWS": [
        "F&O / Options",
        "FII/DII Flows",
    ],
    "MACRO, NEWS & FUNDS": [
        "Macro Dashboard",
        "News Feed",
        "Corporate Actions & Filings",
        "IPO Tracker",
        "Mutual Funds",
    ],
    "PORTFOLIO, FX & SYSTEM": [
        "Portfolio Tracker",
        "Crypto & FX (INR)",
        "Alerts",
        "Data Source Status",
    ],
}

MODULE_RENDERERS: Dict[str, Callable[[], None]] = {
    "Home / Market Overview": render_home,
    "Watchlist": render_watchlist,
    "Charting": render_charting,
    "Fundamentals": render_fundamentals,
    "Screener": render_screener,
    "Sector & Nifty Heatmap": render_heatmap,
    "F&O / Options": render_options_fno,
    "FII/DII Flows": render_fii_dii,
    "Macro Dashboard": render_macro,
    "News Feed": render_news,
    "Corporate Actions & Filings": render_corporate_actions,
    "IPO Tracker": render_ipo,
    "Mutual Funds": render_mutual_funds,
    "Portfolio Tracker": render_portfolio,
    "Crypto & FX (INR)": render_crypto_fx,
    "Alerts": render_alerts,
    "Data Source Status": render_data_status,
}


def main() -> None:
    """Render the terminal shell, command bar, sidebar navigation, and active module."""
    inject_bloomberg_css()

    if "active_module" not in st.session_state:
        st.session_state["active_module"] = "Home / Market Overview"

    # Top Title Bar
    st.markdown(
        """
        <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:6px;">
            <span style="color:#FF8C00; font-size:1.35rem; font-weight:800; letter-spacing:0.1em;">
                IND TERMINAL
            </span>
            <span style="color:#8A9099; font-size:0.78rem;">
                NSE / BSE / INR • Free Open-Source Edition • 17 Live Modules
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Persistent Bloomberg-style Command Bar
    render_command_bar()

    # Sidebar Navigation
    with st.sidebar:
        st.markdown(
            "<div style='color:#FF8C00; font-weight:800; font-size:1rem; letter-spacing:0.08em; margin-bottom:6px;'>"
            "TERMINAL MODULES</div>",
            unsafe_allow_html=True,
        )
        for group_name, mod_list in MODULE_GROUPS.items():
            st.caption(group_name)
            for mod in mod_list:
                is_active = st.session_state["active_module"] == mod
                if st.button(
                    f"▸ {mod}" if is_active else mod,
                    key=f"nav_{mod}",
                    width="stretch",
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state["active_module"] = mod
                    st.rerun()

    # Route Active Module
    active = st.session_state["active_module"]
    renderer = MODULE_RENDERERS.get(active, render_home)
    renderer()

    render_disclaimer()


if __name__ == "__main__":
    main()
