"""
IND TERMINAL — India Financial Research Terminal
Run locally with: streamlit run app.py
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import streamlit as st
from dotenv import load_dotenv
from streamlit_option_menu import option_menu

from modules.alerts import render_alerts
from modules.backtesting import render_backtesting
from modules.broker_feeds import render_broker_feeds
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
from utils.ui import get_theme_palette, inject_bloomberg_css, render_disclaimer

load_dotenv()

st.set_page_config(
    page_title="IND TERMINAL // Indian Market Research Terminal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

MODULE_GROUPS: Dict[str, List[Tuple[str, str]]] = {
    "MARKETS & SCREENING": [
        ("Home / Market Overview", "house"),
        ("Watchlist", "bookmark-star"),
        ("Charting", "graph-up-arrow"),
        ("Backtesting", "arrow-repeat"),
        ("Fundamentals", "file-earmark-bar-graph"),
        ("Screener", "funnel"),
        ("Sector & Nifty Heatmap", "grid-1x2"),
    ],
    "NSE DERIVATIVES & FLOWS": [
        ("F&O / Options", "layers"),
        ("FII/DII Flows", "arrow-left-right"),
    ],
    "MACRO, NEWS & FUNDS": [
        ("Macro Dashboard", "globe2"),
        ("News Feed", "newspaper"),
        ("Corporate Actions & Filings", "building"),
        ("IPO Tracker", "rocket-takeoff"),
        ("Mutual Funds", "piggy-bank"),
    ],
    "PORTFOLIO, FX & SYSTEM": [
        ("Portfolio Tracker", "briefcase"),
        ("Crypto & FX (INR)", "currency-bitcoin"),
        ("Alerts", "bell"),
        ("Broker Feeds (Real-Time)", "plug"),
        ("Data Source Status", "activity"),
    ],
}

MODULE_RENDERERS: Dict[str, Callable[[], None]] = {
    "Home / Market Overview": render_home,
    "Watchlist": render_watchlist,
    "Charting": render_charting,
    "Backtesting": render_backtesting,
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
    "Broker Feeds (Real-Time)": render_broker_feeds,
    "Data Source Status": render_data_status,
}


def _build_flat_menu() -> Tuple[List[str], List[Optional[str]]]:
    """Build a single unified option_menu list with '---' dividers between module groups."""
    options: List[str] = []
    icons: List[Optional[str]] = []
    group_list = list(MODULE_GROUPS.values())
    for g_idx, mod_items in enumerate(group_list):
        for name, ic in mod_items:
            options.append(name)
            icons.append(ic)
        if g_idx < len(group_list) - 1:
            options.append("---")
            icons.append(None)
    return options, icons


def _on_menu_select(menu_key: str) -> None:
    chosen = st.session_state.get(menu_key)
    if chosen and chosen != "---" and chosen in MODULE_RENDERERS:
        st.session_state["active_module"] = chosen


def main() -> None:
    """Render the terminal shell, theme switcher, unified option_menu sidebar, and active view."""
    if "active_module" not in st.session_state:
        st.session_state["active_module"] = "Home / Market Overview"
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "dark"

    with st.sidebar:
        theme_choice = st.radio(
            "Appearance",
            options=["Dark", "Light"],
            index=0 if st.session_state["theme_mode"] == "dark" else 1,
            horizontal=True,
            key="theme_radio",
        )
        st.session_state["theme_mode"] = theme_choice.lower()
        pal = get_theme_palette(st.session_state["theme_mode"])

        st.markdown(
            f"<div style='color:{pal['text']}; font-weight:700; font-size:1.05rem; "
            f"letter-spacing:0.02em; margin:8px 0 8px 0;'>"
            f"<span style='color:{pal['accent']};'>●</span> IND TERMINAL</div>",
            unsafe_allow_html=True,
        )

        menu_styles = {
            "container": {
                "padding": "6px",
                "background-color": pal["surface"],
                "border": f"1px solid {pal['border']}",
                "border-radius": "12px",
            },
            "icon": {"color": pal["muted"], "font-size": "14px"},
            "nav-link": {
                "font-family": "Inter, sans-serif",
                "font-size": "13px",
                "font-weight": "500",
                "text-align": "left",
                "margin": "2px 0",
                "padding": "7px 10px",
                "border-radius": "8px",
                "color": pal["text"],
                "--hover-color": pal["surface_alt"],
            },
            "nav-link-selected": {
                "background-color": pal["surface_alt"],
                "color": pal["accent"],
                "font-weight": "600",
                "border": f"1px solid {pal['border']}",
            },
        }

        all_options, all_icons = _build_flat_menu()
        active = st.session_state["active_module"]
        active_idx = all_options.index(active) if active in all_options else 0

        option_menu(
            menu_title=None,
            options=all_options,
            icons=all_icons,
            default_index=active_idx,
            manual_select=active_idx,
            styles=menu_styles,
            key=f"main_nav_{st.session_state['theme_mode']}",
            on_change=_on_menu_select,
        )

    inject_bloomberg_css(st.session_state["theme_mode"])

    # Clean Top Header Card
    st.markdown(
        """
        <div class="it-topbar">
            <div class="it-brand"><span class="it-brand-dot">●</span>IND TERMINAL</div>
            <div class="it-subtitle">NSE / BSE / INR • Free Open-Source Edition • Press <span class="it-mono">/</span> or <span class="it-mono">Ctrl+K</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Persistent Command Bar
    render_command_bar()

    # Route Active Module
    active = st.session_state["active_module"]
    renderer = MODULE_RENDERERS.get(active, render_home)
    renderer()

    render_disclaimer()


if __name__ == "__main__":
    main()
