"""Theme palettes (CSS variables), typography, cards, sanitized HTML, and styled DataFrames."""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from utils.formatting import delta_color, format_pct

THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        "bg": "#0E1117",
        "surface": "#161B22",
        "surface_alt": "#1C2128",
        "border": "#2A313C",
        "text": "#E6EDF3",
        "muted": "#8B949E",
        "accent": "#F5A524",
        "accent_contrast": "#0E1117",
        "up": "#26A69A",
        "down": "#EF5350",
        "grid": "rgba(139, 148, 158, 0.14)",
        "pill_open_bg": "#0F2D2A",
        "pill_pre_bg": "#2D220D",
        "pill_closed_bg": "#311618",
        "plotly_template": "plotly_dark",
    },
    "light": {
        "bg": "#F6F8FA",
        "surface": "#FFFFFF",
        "surface_alt": "#EAEEF2",
        "border": "#D0D7DE",
        "text": "#1F2328",
        "muted": "#57606A",
        "accent": "#B45309",
        "accent_contrast": "#FFFFFF",
        "up": "#0E7A6D",
        "down": "#C62828",
        "grid": "rgba(87, 96, 106, 0.12)",
        "pill_open_bg": "#E6F4F1",
        "pill_pre_bg": "#FEF3C7",
        "pill_closed_bg": "#FDECEC",
        "plotly_template": "plotly_white",
    },
}


def sanitize_http_url(url: str) -> str:
    """Allow only http/https links to prevent javascript:/data: XSS in markdown HTML."""
    raw = (url or "").strip()
    if not raw:
        return "#"
    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https"):
        return html.escape(raw, quote=True)
    return "#"


def get_active_theme() -> str:
    """Return 'light' or 'dark' from Streamlit session state."""
    return "light" if st.session_state.get("theme_mode") == "light" else "dark"


def get_theme_palette(theme: Optional[str] = None) -> Dict[str, str]:
    """Return the active WCAG AA color palette dictionary."""
    mode = theme if theme in THEMES else get_active_theme()
    return THEMES[mode]


def get_plotly_theme(theme: Optional[str] = None) -> Dict[str, str]:
    """Return Plotly layout colors matching active Dark/Light theme."""
    pal = get_theme_palette(theme)
    return {
        "template": pal["plotly_template"],
        "paper_bgcolor": pal["bg"],
        "plot_bgcolor": pal["surface"],
        "font_color": pal["text"],
        "gridcolor": pal["grid"],
        "up": pal["up"],
        "down": pal["down"],
        "accent": pal["accent"],
        "muted": pal["muted"],
        "border": pal["border"],
    }


def inject_bloomberg_css(theme: Optional[str] = None) -> None:
    """Inject CSS-variable-driven Dark/Light theme with Inter + JetBrains Mono typography."""
    pal = get_theme_palette(theme)

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        :root {{
            --bg: {pal["bg"]};
            --surface: {pal["surface"]};
            --surface-alt: {pal["surface_alt"]};
            --border: {pal["border"]};
            --text: {pal["text"]};
            --muted: {pal["muted"]};
            --accent: {pal["accent"]};
            --accent-contrast: {pal["accent_contrast"]};
            --up: {pal["up"]};
            --down: {pal["down"]};
            --grid: {pal["grid"]};
            --pill-open-bg: {pal["pill_open_bg"]};
            --pill-pre-bg: {pal["pill_pre_bg"]};
            --pill-closed-bg: {pal["pill_closed_bg"]};
            --font-ui: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            --font-mono: 'JetBrains Mono', 'Consolas', monospace;
            --radius: 12px;
            --space: 8px;
        }}

        /* App shell & typography */
        html, body, .stApp {{
            background-color: var(--bg) !important;
            color: var(--text) !important;
            font-family: var(--font-ui) !important;
        }}
        header[data-testid="stHeader"] {{
            background-color: var(--bg) !important;
            border-bottom: 1px solid var(--border) !important;
        }}
        header[data-testid="stHeader"] button,
        header[data-testid="stHeader"] svg {{
            color: var(--text) !important;
            fill: var(--text) !important;
        }}
        section[data-testid="stSidebar"] {{
            background-color: var(--surface) !important;
            border-right: 1px solid var(--border) !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: var(--text);
        }}
        /* Preserve Streamlit Material Symbols icon font (prevents literal 'keyboard_double...' text) */
        [data-testid="stIconMaterial"],
        .material-symbols-rounded,
        .material-icons {{
            font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
            font-weight: normal !important;
            font-style: normal !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
            color: var(--muted) !important;
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.06em !important;
            text-transform: uppercase !important;
            margin-top: calc(var(--space) * 1.5) !important;
            margin-bottom: calc(var(--space) * 0.5) !important;
        }}
        .block-container {{
            padding-top: 4rem !important;
            padding-bottom: calc(var(--space) * 4) !important;
            max-width: 100%;
        }}

        /* Global readable text across Streamlit widgets (excluding icon spans) */
        .stApp p, .stApp li, .stApp label,
        .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        [data-testid="stWidgetLabel"] p,
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] span {{
            color: var(--text);
            font-family: var(--font-ui);
        }}
        [data-testid="stCaptionContainer"] p {{
            color: var(--muted) !important;
            font-size: 0.82rem !important;
        }}

        /* Buttons: fix light/dark contrast cleanly */
        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {{
            border-radius: 8px !important;
            font-family: var(--font-ui) !important;
            font-weight: 500 !important;
            transition: border-color 0.15s ease, background-color 0.15s ease;
        }}
        .stButton > button[kind="secondary"],
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button[kind="secondary"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
        }}
        .stButton > button[kind="secondary"]:hover,
        .stDownloadButton > button:hover {{
            background-color: var(--surface-alt) !important;
            border-color: var(--accent) !important;
            color: var(--text) !important;
        }}
        .stButton > button[kind="primary"],
        [data-testid="stFormSubmitButton"] > button[kind="primary"] {{
            background-color: var(--accent) !important;
            color: var(--accent-contrast) !important;
            border: 1px solid var(--accent) !important;
            font-weight: 600 !important;
        }}

        /* Inputs, selects, sliders, popovers */
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
            font-family: var(--font-ui) !important;
        }}
        div[data-testid="stTextInput"] input::placeholder,
        div[data-testid="stNumberInput"] input::placeholder {{
            color: var(--muted) !important;
            opacity: 0.9 !important;
        }}
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stNumberInput"] input:focus {{
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 1px var(--accent) !important;
        }}
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
        div[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        div[data-testid="stMultiSelect"] [data-baseweb="select"] > div > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] > div > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="base-input"],
        div[data-baseweb="base-input"] > input {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border-color: var(--border) !important;
            border-radius: 8px !important;
        }}
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div,
        div[data-baseweb="select"] svg {{
            color: var(--text) !important;
            fill: var(--text) !important;
        }}
        div[data-baseweb="popover"],
        ul[role="listbox"] {{
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
        }}
        ul[role="listbox"] li {{
            color: var(--text) !important;
            background-color: var(--surface) !important;
        }}
        ul[role="listbox"] li:hover {{
            background-color: var(--surface-alt) !important;
        }}

        /* Inline code & option_menu iframe rounding */
        .stApp code {{
            background-color: var(--surface-alt) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 4px !important;
            padding: 1px 5px !important;
            font-family: var(--font-mono) !important;
            font-size: 0.85em !important;
        }}
        iframe[title="streamlit_option_menu.option_menu"] {{
            background-color: var(--surface) !important;
            border-radius: var(--radius) !important;
        }}

        /* Radio, checkbox, expander, container cards */
        [data-testid="stRadio"] label span,
        [data-testid="stCheckbox"] label span {{
            color: var(--text) !important;
        }}
        [data-testid="stRadio"] div[role="radiogroup"] > label > div:first-child {{
            background-color: var(--surface-alt) !important;
            border: 1px solid var(--muted) !important;
        }}
        div[data-testid="stExpander"] {{
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: var(--radius) !important;
        }}
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p {{
            color: var(--text) !important;
            font-weight: 500 !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: var(--radius) !important;
        }}

        /* Tabs */
        button[data-baseweb="tab"] {{
            font-family: var(--font-ui) !important;
            font-size: 0.88rem !important;
            font-weight: 500 !important;
            color: var(--muted) !important;
            background-color: transparent !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: var(--accent) !important;
            font-weight: 600 !important;
        }}

        /* Alerts / info banners */
        div[data-testid="stAlert"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: var(--radius) !important;
        }}

        /* DataFrames & Tables */
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {{
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: var(--radius) !important;
            overflow: hidden;
        }}
        div[data-testid="stTable"] table {{
            color: var(--text) !important;
        }}
        div[data-testid="stTable"] thead th {{
            background-color: var(--surface-alt) !important;
            color: var(--text) !important;
            position: sticky;
            top: 0;
        }}

        /* Monospace utility for numbers & tickers ONLY */
        .it-mono {{
            font-family: var(--font-mono) !important;
            font-variant-numeric: tabular-nums;
        }}

        /* Top bar & Section headers */
        .it-topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: calc(var(--space) * 1.25) calc(var(--space) * 2);
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            margin-bottom: calc(var(--space) * 1.5);
        }}
        .it-brand {{
            color: var(--text);
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }}
        .it-brand-dot {{
            color: var(--accent);
            margin-right: 6px;
        }}
        .it-subtitle {{
            color: var(--muted);
            font-size: 0.8rem;
            font-weight: 500;
        }}
        .it-section-header {{
            color: var(--text);
            font-size: 0.92rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            border-bottom: 1px solid var(--border);
            padding-bottom: 6px;
            margin-top: calc(var(--space) * 2);
            margin-bottom: calc(var(--space) * 1.5);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .it-section-header::before {{
            content: "";
            display: inline-block;
            width: 3px;
            height: 14px;
            background-color: var(--accent);
            border-radius: 2px;
        }}

        /* Card-based metric panels (12px radius, thin borders, 8px spacing) */
        .it-card {{
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 14px 16px;
            margin-bottom: var(--space);
        }}
        .it-card-label {{
            color: var(--muted);
            font-size: 0.76rem;
            font-weight: 500;
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .it-card-value {{
            color: var(--text);
            font-family: var(--font-mono);
            font-variant-numeric: tabular-nums;
            font-size: 1.25rem;
            font-weight: 600;
            line-height: 1.3;
        }}
        .it-card-delta {{
            font-family: var(--font-mono);
            font-variant-numeric: tabular-nums;
            font-size: 0.82rem;
            font-weight: 500;
            margin-top: 4px;
        }}

        /* Market status & list cards */
        .it-status-bar {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 10px;
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 10px 14px;
            margin-bottom: calc(var(--space) * 1.5);
            font-size: 0.84rem;
            color: var(--text);
        }}
        .it-pill-open {{
            background-color: var(--pill-open-bg);
            color: var(--up);
            border: 1px solid var(--up);
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 600;
        }}
        .it-pill-pre {{
            background-color: var(--pill-pre-bg);
            color: var(--accent);
            border: 1px solid var(--accent);
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 600;
        }}
        .it-pill-closed {{
            background-color: var(--pill-closed-bg);
            color: var(--down);
            border: 1px solid var(--down);
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 600;
        }}
        .it-feed-card {{
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 12px 16px;
            margin-bottom: var(--space);
        }}
        .it-feed-meta {{
            font-size: 0.76rem;
            color: var(--muted);
            display: flex;
            justify-content: space-between;
            gap: 8px;
        }}
        .it-feed-title {{
            margin-top: 4px;
            font-size: 0.92rem;
            font-weight: 500;
        }}
        .it-feed-title a {{
            color: var(--text) !important;
            text-decoration: none;
        }}
        .it-feed-title a:hover {{
            color: var(--accent) !important;
            text-decoration: underline;
        }}

        /* Disclaimer footer */
        .it-disclaimer {{
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 12px 16px;
            margin-top: calc(var(--space) * 3);
            font-size: 0.78rem;
            line-height: 1.5;
            color: var(--muted);
        }}
        .it-disclaimer strong {{
            color: var(--text);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str) -> None:
    """Render a clean themed section header."""
    st.markdown(
        f'<div class="it-section-header">{html.escape(str(title))}</div>',
        unsafe_allow_html=True,
    )


def render_metric_card(
    label: str,
    value_str: str,
    change: float | None = None,
    pct_change: float | None = None,
    subtext: str = "",
) -> None:
    """Render a 12px-radius card metric tile with tabular JetBrains Mono numbers."""
    pal = get_theme_palette()
    ref_val = pct_change if pct_change is not None else change
    if ref_val is None or ref_val == 0:
        color = pal["muted"]
    elif ref_val > 0:
        color = pal["up"]
    else:
        color = pal["down"]

    delta_parts = []
    if change is not None:
        sign = "+" if change > 0 else ""
        delta_parts.append(f"{sign}{change:,.2f}")
    if pct_change is not None:
        delta_parts.append(f"({format_pct(pct_change)})")
    delta_text = " ".join(delta_parts) if delta_parts else subtext

    st.markdown(
        f"""
        <div class="it-card">
            <div class="it-card-label">{html.escape(str(label))}</div>
            <div class="it-card-value">{html.escape(str(value_str))}</div>
            <div class="it-card-delta" style="color: {color};">{html.escape(str(delta_text))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_plotly(fig: Any) -> None:
    """Render a Plotly figure with explicit Dark/Light colors and theme=None (bypasses config.toml dark override)."""
    pt = get_plotly_theme()
    fig.update_layout(
        template=pt["template"],
        paper_bgcolor=pt["paper_bgcolor"],
        plot_bgcolor=pt["plot_bgcolor"],
        font=dict(family="Inter, sans-serif", color=pt["font_color"]),
        legend=dict(font=dict(color=pt["font_color"])),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=pt["gridcolor"],
        zeroline=False,
        tickfont=dict(color=pt["muted"]),
        title_font=dict(color=pt["font_color"]),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=pt["gridcolor"],
        zeroline=False,
        tickfont=dict(color=pt["muted"]),
        title_font=dict(color=pt["font_color"]),
    )
    st.plotly_chart(fig, width="stretch", theme=None)


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


def _is_numeric_like_series(s: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(s):
        return True
    sample = s.dropna().astype(str).head(5)
    if sample.empty:
        return False
    return all(any(ch.isdigit() for ch in val) and ("₹" in val or "%" in val or val.lstrip("+-").replace(",", "").replace(".", "").replace("x", "").isdigit()) for val in sample)


def style_change_dataframe(
    df: pd.DataFrame,
    change_cols: List[str],
    numeric_cols: Optional[List[str]] = None,
) -> pd.io.formats.style.Styler:
    """Apply theme-aware green/red text on change columns and right-aligned monospace numbers."""
    pal = get_theme_palette()

    def _color_cell(val: object) -> str:
        if isinstance(val, (int, float)):
            if val > 0:
                return f"color: {pal['up']}; font-weight: 600;"
            if val < 0:
                return f"color: {pal['down']}; font-weight: 600;"
            return f"color: {pal['muted']};"
        text = str(val).strip()
        if text.startswith("+"):
            return f"color: {pal['up']}; font-weight: 600;"
        if text.startswith("-"):
            return f"color: {pal['down']}; font-weight: 600;"
        return f"color: {pal['muted']};"

    valid_change = [c for c in change_cols if c in df.columns]
    inferred_num = numeric_cols if numeric_cols is not None else [c for c in df.columns if _is_numeric_like_series(df[c])]
    valid_num = [c for c in inferred_num if c in df.columns]

    styler = df.style.map(_color_cell, subset=valid_change)
    if valid_num:
        styler = styler.set_properties(
            subset=valid_num,
            **{
                "text-align": "right",
                "font-family": "'JetBrains Mono', monospace",
                "font-variant-numeric": "tabular-nums",
            },
        )
    return styler


def render_disclaimer() -> None:
    """Render the mandatory educational, delay, terms, and limitations disclaimer."""
    pal = get_theme_palette()
    st.markdown(
        f"""
        <div class="it-disclaimer">
            <strong style="color:{pal['accent']};">RESEARCH DISCLAIMER &amp; DATA NOTES:</strong>
            For <strong>personal education and research only</strong> — not investment advice. Always verify prices,
            financials, and tax numbers with official NSE/BSE filings before risking real money.<br>
            • <strong>Delays &amp; Unofficial Feeds:</strong> Free sources (<code>yfinance</code>, NSE public feeds, Frankfurter)
            are typically <strong>~15 min delayed or EOD</strong> and use unofficial endpoints that can break or rate-limit;
            Indian fundamentals on Yahoo Finance may be incomplete.<br>
            • <strong>Real-Time &amp; Scope:</strong> True tick-by-tick data requires a paid/account broker API
            (Zerodha, Upstox, Angel One, Fyers). Free tools cover ~70–80% of individual-investor workflows (not Bloomberg
            messaging or institutional bond/derivatives pricing). Respect website ToS &amp; rate limits; do not redistribute data.
        </div>
        """,
        unsafe_allow_html=True,
    )
