"""Bloomberg-inspired dark theme CSS, metric cards, CSV exports, and disclaimers."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.formatting import COLOR_DOWN, COLOR_FLAT, COLOR_UP, delta_color, format_pct


def inject_bloomberg_css() -> None:
    """Inject compact, dark Bloomberg-style CSS into the Streamlit app."""
    st.markdown(
        """
        <style>
        /* Core terminal background & typography */
        .stApp {
            background-color: #000000;
            color: #E8E8E8;
            font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
        }
        section[data-testid="stSidebar"] {
            background-color: #090B0E;
            border-right: 1px solid #22262C;
        }
        /* Compact padding */
        .block-container {
            padding-top: 1rem;
            padding-bottom: 2rem;
            max-width: 100%;
        }
        /* Orange Bloomberg headers */
        .bb-header {
            color: #FF8C00;
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            border-bottom: 1px solid #FF8C00;
            padding-bottom: 4px;
            margin-top: 0.75rem;
            margin-bottom: 0.6rem;
        }
        /* Metric tiles */
        .bb-card {
            background-color: #0D0F12;
            border: 1px solid #22262C;
            border-left: 3px solid #FF8C00;
            border-radius: 3px;
            padding: 10px 12px;
            margin-bottom: 8px;
        }
        .bb-card-label {
            color: #9AA0A6;
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .bb-card-value {
            color: #FFFFFF;
            font-size: 1.25rem;
            font-weight: 700;
            margin-top: 2px;
        }
        .bb-card-delta {
            font-size: 0.82rem;
            font-weight: 600;
            margin-top: 2px;
        }
        /* Status pills */
        .bb-pill-open {
            background-color: #082E12;
            color: #00C805;
            border: 1px solid #00C805;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: 700;
        }
        .bb-pill-pre {
            background-color: #2E2208;
            color: #FF8C00;
            border: 1px solid #FF8C00;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: 700;
        }
        .bb-pill-closed {
            background-color: #2E0C0C;
            color: #FF3B30;
            border: 1px solid #FF3B30;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: 700;
        }
        /* Command bar styling */
        div[data-testid="stTextInput"] input {
            background-color: #0D0F12 !important;
            color: #FF8C00 !important;
            border: 1px solid #FF8C00 !important;
            font-family: 'JetBrains Mono', 'Consolas', monospace !important;
            font-weight: 600 !important;
        }
        /* Tabs & button polish */
        button[data-baseweb="tab"] {
            font-family: 'JetBrains Mono', 'Consolas', monospace !important;
            font-size: 0.82rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.04em;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #22262C;
            border-radius: 3px;
        }
        /* Disclaimer footer */
        .bb-disclaimer {
            background-color: #0D0F12;
            border: 1px solid #2A2E35;
            border-left: 3px solid #FF8C00;
            padding: 8px 12px;
            margin-top: 1.5rem;
            font-size: 0.75rem;
            color: #A0A4AB;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str) -> None:
    """Render an uppercase orange Bloomberg-style section header."""
    st.markdown(f'<div class="bb-header">{title}</div>', unsafe_allow_html=True)


def render_metric_card(
    label: str,
    value_str: str,
    change: float | None = None,
    pct_change: float | None = None,
    subtext: str = "",
) -> None:
    """Render a compact dark metric card with green/red delta coloring."""
    color = delta_color(pct_change if pct_change is not None else change)
    delta_parts = []
    if change is not None:
        sign = "+" if change > 0 else ""
        delta_parts.append(f"{sign}{change:,.2f}")
    if pct_change is not None:
        delta_parts.append(f"({format_pct(pct_change)})")
    delta_text = " ".join(delta_parts) if delta_parts else subtext

    st.markdown(
        f"""
        <div class="bb-card">
            <div class="bb-card-label">{label}</div>
            <div class="bb-card-value">{value_str}</div>
            <div class="bb-card-delta" style="color: {color};">{delta_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_csv_download(df: pd.DataFrame, filename: str, label: str = "Export CSV") -> None:
    """Render a compact CSV download button for any DataFrame."""
    if df is None or df.empty:
        return
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=label,
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
        key=f"csv_{filename}_{len(df)}",
    )


def style_change_dataframe(df: pd.DataFrame, change_cols: list[str]) -> pd.io.formats.style.Styler:
    """Apply green/red text coloring to numeric or formatted % change columns."""
    def _color_cell(val: object) -> str:
        if isinstance(val, (int, float)):
            if val > 0:
                return f"color: {COLOR_UP}; font-weight: 600;"
            if val < 0:
                return f"color: {COLOR_DOWN}; font-weight: 600;"
            return f"color: {COLOR_FLAT};"
        text = str(val).strip()
        if text.startswith("+"):
            return f"color: {COLOR_UP}; font-weight: 600;"
        if text.startswith("-"):
            return f"color: {COLOR_DOWN}; font-weight: 600;"
        return f"color: {COLOR_FLAT};"

    valid_cols = [c for c in change_cols if c in df.columns]
    return df.style.map(_color_cell, subset=valid_cols)


def render_disclaimer() -> None:
    """Render the mandatory educational and delayed-data disclaimer."""
    st.markdown(
        """
        <div class="bb-disclaimer">
            <strong style="color:#FF8C00;">DISCLAIMER:</strong>
            For education and research only — not investment advice. Free market data
            (including Yahoo Finance, NSE public feeds, and FX APIs) may be delayed
            (typically 15 minutes or end-of-day), incomplete, or temporarily unavailable.
            Always verify prices and corporate data with official exchange sources before trading.
        </div>
        """,
        unsafe_allow_html=True,
    )
