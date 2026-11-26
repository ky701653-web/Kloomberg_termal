"""Module 17: Bloomberg-style Command Bar parser, keyboard shortcut (/ or Ctrl+K), and UI component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

INDEX_ALIASES: Dict[str, str] = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "SENSEX": "^BSESN",
    "BANKNIFTY": "^NSEBANK",
    "INDIAVIX": "^INDIAVIX",
    "VIX": "^INDIAVIX",
}

COMMAND_HELP: List[Dict[str, str]] = [
    {"Command": "RELIANCE GO", "Action": "Set active security to RELIANCE.NS & open Market Overview"},
    {"Command": "WL", "Action": "Open NSE/BSE Watchlist"},
    {"Command": "INFY GP", "Action": "Open Interactive Charting for INFY.NS"},
    {"Command": "TCS FA", "Action": "Open Fundamentals & Financial Statements for TCS.NS"},
    {"Command": "RELIANCE BT", "Action": "Open Strategy Backtester for RELIANCE.NS"},
    {"Command": "SCREEN", "Action": "Open Nifty 500 Stock Screener"},
    {"Command": "HEATMAP", "Action": "Open Sector & Nifty 50 Treemap Heatmaps"},
    {"Command": "NIFTY OPT", "Action": "Open NSE Option Chain, PCR & Max Pain"},
    {"Command": "FII / DII", "Action": "Open FII/DII Institutional Flows"},
    {"Command": "MACRO", "Action": "Open India & Global Macro Dashboard"},
    {"Command": "NEWS HDFCBANK", "Action": "Open Market News Feed with VADER Sentiment"},
    {"Command": "RELIANCE CORP", "Action": "Open Corporate Actions & Exchange Filings"},
    {"Command": "IPO", "Action": "Open Indian IPO Tracker"},
    {"Command": "MF", "Action": "Open Mutual Funds Explorer & SIP Calculator"},
    {"Command": "PORT", "Action": "Open Portfolio Tracker (XIRR, Risk, Capital Gains)"},
    {"Command": "FX / CRYPTO", "Action": "Open Crypto & Global FX (INR) Panels"},
    {"Command": "ALERTS", "Action": "Open Alerts Engine (Price, RSI, MA Cross)"},
    {"Command": "BROKER", "Action": "Open Real-Time Broker APIs (Zerodha, Upstox, Angel One)"},
    {"Command": "HOME", "Action": "Return to Home / Market Overview"},
    {"Command": "STATUS", "Action": "Open Data Source Status & Cache Diagnostics"},
    {"Command": "HELP", "Action": "Toggle this command reference table"},
]


@dataclass(frozen=True)
class ParsedCommand:
    """Structured routing instruction parsed from the Bloomberg command bar."""

    target_module: Optional[str]
    ticker: Optional[str]
    query: Optional[str]
    show_help: bool
    message: str
    is_valid: bool


def normalize_indian_ticker(raw_symbol: str) -> str:
    """Normalize an NSE/BSE ticker or index alias (defaults to .NS for Indian equities)."""
    sym = raw_symbol.strip().upper()
    if sym in INDEX_ALIASES:
        return INDEX_ALIASES[sym]
    if sym.startswith("^") or sym.endswith(".NS") or sym.endswith(".BO") or "=" in sym:
        return sym
    return f"{sym}.NS"


def parse_command(raw_input: str) -> ParsedCommand:
    """Parse a Bloomberg-style command string into a module route and optional ticker."""
    cleaned = raw_input.strip()
    if not cleaned:
        return ParsedCommand(None, None, None, False, "", True)

    tokens = cleaned.upper().split()
    first = tokens[0]

    single_routes: Dict[str, str] = {
        "HOME": "Home / Market Overview",
        "OVERVIEW": "Home / Market Overview",
        "WL": "Watchlist",
        "WATCH": "Watchlist",
        "WATCHLIST": "Watchlist",
        "GP": "Charting",
        "CHART": "Charting",
        "FA": "Fundamentals",
        "BT": "Backtesting",
        "BACKTEST": "Backtesting",
        "SCREEN": "Screener",
        "SCREENER": "Screener",
        "HEATMAP": "Sector & Nifty Heatmap",
        "MAP": "Sector & Nifty Heatmap",
        "OPT": "F&O / Options",
        "FNO": "F&O / Options",
        "FII": "FII/DII Flows",
        "DII": "FII/DII Flows",
        "FIIDII": "FII/DII Flows",
        "MACRO": "Macro Dashboard",
        "CORP": "Corporate Actions & Filings",
        "FILINGS": "Corporate Actions & Filings",
        "IPO": "IPO Tracker",
        "MF": "Mutual Funds",
        "PORT": "Portfolio Tracker",
        "PORTFOLIO": "Portfolio Tracker",
        "FX": "Crypto & FX (INR)",
        "CRYPTO": "Crypto & FX (INR)",
        "ALERTS": "Alerts",
        "ALERT": "Alerts",
        "BROKER": "Broker Feeds (Real-Time)",
        "BROKERS": "Broker Feeds (Real-Time)",
        "STATUS": "Data Source Status",
    }

    if first in ("HELP", "?"):
        return ParsedCommand(None, None, None, True, "Showing command reference.", True)

    if first == "NEWS":
        ticker = normalize_indian_ticker(tokens[1]) if len(tokens) > 1 else None
        query = tokens[1] if len(tokens) > 1 else None
        msg = f"Routed to News Feed (filter: {query})" if query else "Routed to News Feed"
        return ParsedCommand("News Feed", ticker, query, False, msg, True)

    if first in single_routes and len(tokens) == 1:
        mod = single_routes[first]
        return ParsedCommand(mod, None, None, False, f"Routed to {mod}", True)

    if len(tokens) >= 2:
        ticker_raw, fn = tokens[0], tokens[1]
        ticker = normalize_indian_ticker(ticker_raw)

        fn_routes: Dict[str, str] = {
            "GO": "Home / Market Overview",
            "GP": "Charting",
            "CHART": "Charting",
            "FA": "Fundamentals",
            "BT": "Backtesting",
            "BACKTEST": "Backtesting",
            "OPT": "F&O / Options",
            "FNO": "F&O / Options",
            "NEWS": "News Feed",
            "WL": "Watchlist",
            "CORP": "Corporate Actions & Filings",
            "ALERT": "Alerts",
            "ALERTS": "Alerts",
        }
        if fn in fn_routes:
            mod = fn_routes[fn]
            return ParsedCommand(mod, ticker, ticker_raw, False, f"{ticker} → {mod}", True)

    if len(tokens) == 1 and first.replace("-", "").replace(".", "").isalnum():
        ticker = normalize_indian_ticker(first)
        return ParsedCommand(
            "Home / Market Overview",
            ticker,
            first,
            False,
            f"Active security set to {ticker} (try '{first} GP', '{first} FA', or '{first} BT')",
            True,
        )

    return ParsedCommand(
        None,
        None,
        None,
        False,
        f"Unrecognized command: '{cleaned}'. Type HELP to view supported commands.",
        False,
    )


def render_command_bar() -> None:
    """Render the persistent Bloomberg-style command bar with '/' or Ctrl+K focus shortcut."""
    import streamlit as st

    col_input, col_btn, col_help = st.columns([6, 1, 1])
    with col_input:
        raw_cmd = st.text_input(
            label="Command Bar",
            placeholder="Press / or Ctrl+K — RELIANCE GO | INFY GP | TCS FA | RELIANCE BT | SCREEN | BROKER | HELP",
            label_visibility="collapsed",
            key="bb_command_input",
        )
    with col_btn:
        run_clicked = st.button("GO", width="stretch", type="primary")
    with col_help:
        help_clicked = st.button("HELP", width="stretch")

    # Bind '/' (when outside inputs) and 'Ctrl+K' / 'Cmd+K' to focus the Command Bar
    shortcut_html = """
        <script>
        (function() {
            const doc = window.parent.document;
            if (doc.__indTerminalShortcutBound) return;
            doc.__indTerminalShortcutBound = true;
            doc.addEventListener('keydown', function(e) {
                const tag = (doc.activeElement && doc.activeElement.tagName || '').toLowerCase();
                const isInput = tag === 'input' || tag === 'textarea' || (doc.activeElement && doc.activeElement.isContentEditable);
                const isShortcut = (e.key === '/' && !isInput && !e.ctrlKey && !e.metaKey && !e.altKey) ||
                                   ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k');
                if (isShortcut) {
                    const el = doc.querySelector('input[aria-label="Command Bar"]');
                    if (el) {
                        e.preventDefault();
                        el.focus();
                        el.select();
                    }
                }
            });
        })();
        </script>
    """
    if hasattr(st, "iframe"):
        st.iframe(shortcut_html, height=1)
    else:
        import streamlit.components.v1 as components

        components.html(shortcut_html, height=0)

    if help_clicked:
        st.session_state["show_cmd_help"] = not st.session_state.get("show_cmd_help", False)

    if run_clicked or (raw_cmd and raw_cmd != st.session_state.get("last_executed_cmd", "")):
        st.session_state["last_executed_cmd"] = raw_cmd
        parsed = parse_command(raw_cmd)
        if parsed.show_help:
            st.session_state["show_cmd_help"] = True
        elif parsed.is_valid:
            if parsed.ticker:
                st.session_state["active_ticker"] = parsed.ticker
            if parsed.query:
                st.session_state["active_query"] = parsed.query
            if parsed.target_module:
                prev_mod = st.session_state.get("active_module")
                st.session_state["active_module"] = parsed.target_module
                if parsed.message:
                    st.session_state["cmd_feedback"] = ("ok", parsed.message)
                if prev_mod != parsed.target_module:
                    st.rerun()
            elif parsed.message:
                st.session_state["cmd_feedback"] = ("ok", parsed.message)
        else:
            st.session_state["cmd_feedback"] = ("error", parsed.message)

    feedback = st.session_state.get("cmd_feedback")
    if feedback:
        level, msg = feedback
        if level == "ok":
            st.caption(f"▸ {msg}")
        else:
            st.warning(msg)

    if st.session_state.get("show_cmd_help", False):
        with st.expander("Bloomberg Command Bar Reference (click to collapse)", expanded=True):
            st.table(COMMAND_HELP)
