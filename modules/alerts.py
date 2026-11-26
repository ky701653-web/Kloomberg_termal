"""Module 16: Alerts Engine (Price, % Move, RSI, MA Crossover + Telegram / SMTP Email)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

from data.market_data import fetch_ohlcv
from modules.command_bar import normalize_indian_ticker
from utils.cache import terminal_cache
from utils.indicators import compute_rsi, compute_sma
from utils.secrets import get_secret
from utils.ui import render_csv_download, render_section_header

ALERT_CONDITIONS = [
    "Price >=",
    "Price <=",
    "Daily % Move >=",
    "Daily % Move <=",
    "RSI (14) >=",
    "RSI (14) <=",
    "SMA 20 > SMA 50 (Bullish Cross)",
    "SMA 20 < SMA 50 (Bearish Cross)",
]


def _send_telegram(message: str) -> Tuple[bool, str]:
    token = get_secret("TELEGRAM_BOT_TOKEN")
    chat_id = get_secret("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False, "Telegram keys not configured"
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        resp.raise_for_status()
        return True, "Telegram sent"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _send_email(subject: str, body: str) -> Tuple[bool, str]:
    host = get_secret("SMTP_HOST")
    port = int(get_secret("SMTP_PORT", "587") or 587)
    user = get_secret("SMTP_USER")
    pwd = get_secret("SMTP_PASSWORD")
    to_addr = get_secret("ALERT_EMAIL_TO")
    if not all([host, user, pwd, to_addr]):
        return False, "SMTP email keys not configured"
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to_addr
        msg.set_content(body)
        with smtplib.SMTP(host, port, timeout=12) as server:
            server.starttls()
            server.login(user, pwd)
            server.send_message(msg)
        return True, "Email sent"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def evaluate_rule_against_ohlcv(rule: Dict, df: pd.DataFrame) -> Optional[str]:
    """Evaluate a single alert rule against OHLCV DataFrame; returns message if triggered."""
    if df is None or df.empty or len(df) < 2:
        return None
    closes = df["Close"].dropna()
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2])
    pct = (price - prev) / prev * 100.0 if prev else 0.0
    cond = rule["condition"]
    thresh = float(rule["threshold"])
    sym = rule["symbol"]

    if cond == "Price >=" and price >= thresh:
        return f"{sym} Price ₹{price:,.2f} >= ₹{thresh:,.2f}"
    if cond == "Price <=" and price <= thresh:
        return f"{sym} Price ₹{price:,.2f} <= ₹{thresh:,.2f}"
    if cond == "Daily % Move >=" and pct >= thresh:
        return f"{sym} Daily Move {pct:+.2f}% >= {thresh:+.2f}%"
    if cond == "Daily % Move <=" and pct <= thresh:
        return f"{sym} Daily Move {pct:+.2f}% <= {thresh:+.2f}%"
    if cond.startswith("RSI"):
        rsi_s = compute_rsi(closes, 14).dropna()
        if not rsi_s.empty:
            rsi = float(rsi_s.iloc[-1])
            if cond == "RSI (14) >=" and rsi >= thresh:
                return f"{sym} RSI(14) {rsi:.1f} >= {thresh:.1f}"
            if cond == "RSI (14) <=" and rsi <= thresh:
                return f"{sym} RSI(14) {rsi:.1f} <= {thresh:.1f}"
    if cond.startswith("SMA 20") and len(closes) >= 51:
        sma20 = compute_sma(closes, 20)
        sma50 = compute_sma(closes, 50)
        if pd.notna(sma20.iloc[-1]) and pd.notna(sma50.iloc[-1]) and pd.notna(sma20.iloc[-2]) and pd.notna(sma50.iloc[-2]):
            if cond.startswith("SMA 20 >") and sma20.iloc[-2] <= sma50.iloc[-2] and sma20.iloc[-1] > sma50.iloc[-1]:
                return f"{sym} Bullish Golden Cross (SMA20 {sma20.iloc[-1]:.2f} > SMA50 {sma50.iloc[-1]:.2f})"
            if cond.startswith("SMA 20 <") and sma20.iloc[-2] >= sma50.iloc[-2] and sma20.iloc[-1] < sma50.iloc[-1]:
                return f"{sym} Bearish Death Cross (SMA20 {sma20.iloc[-1]:.2f} < SMA50 {sma50.iloc[-1]:.2f})"
    return None


def render_alerts() -> None:
    """Render Alerts Engine UI with rule builder, evaluation, and optional Telegram/Email delivery."""
    render_section_header("Alerts Engine (Price • % Move • RSI • MA Crossover • Telegram / Email)")

    tg_ready = bool(get_secret("TELEGRAM_BOT_TOKEN") and get_secret("TELEGRAM_CHAT_ID"))
    email_ready = bool(get_secret("SMTP_HOST") and get_secret("SMTP_USER") and get_secret("SMTP_PASSWORD") and get_secret("ALERT_EMAIL_TO"))
    st.caption(
        f"Delivery channels: **In-App Log (Active)** • "
        f"Telegram: **{'Configured' if tg_ready else 'Not configured (.env)'}** • "
        f"Email SMTP: **{'Configured' if email_ready else 'Not configured (.env)'}**"
    )

    with st.form("alert_add_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 2.5, 1.5, 1])
        sym_in = c1.text_input("Ticker", value=(st.session_state.get("active_ticker") or "RELIANCE.NS"))
        cond_in = c2.selectbox("Condition", options=ALERT_CONDITIONS)
        thresh_in = c3.number_input("Threshold (ignored for MA cross)", value=1500.0, step=10.0)
        if c4.form_submit_button("Add Rule", type="primary"):
            if sym_in.strip():
                norm = normalize_indian_ticker(sym_in)
                terminal_cache.add_alert_rule(norm, cond_in, thresh_in)
                st.success(f"Alert added: {norm} {cond_in} {thresh_in}")
                st.rerun()

    rules = terminal_cache.get_alert_rules()
    c_eval, c_test_tg, c_test_em = st.columns([2, 1.5, 1.5])
    if c_eval.button("Evaluate All Enabled Rules Now", type="primary", width="stretch"):
        enabled_rules = [r for r in rules if r["enabled"]]
        if not enabled_rules:
            st.info("No enabled alert rules to evaluate.")
        else:
            triggered: List[str] = []
            with st.spinner("Evaluating rules against live OHLCV..."):
                for r in enabled_rules:
                    df, _, _ = fetch_ohlcv(r["symbol"], period="6mo", interval="1d", ttl_seconds=60)
                    msg = evaluate_rule_against_ohlcv(r, df)
                    if msg:
                        channels = ["In-App"]
                        if tg_ready and _send_telegram(f"[IND TERMINAL ALERT] {msg}")[0]:
                            channels.append("Telegram")
                        if email_ready and _send_email(f"IND TERMINAL Alert: {r['symbol']}", msg)[0]:
                            channels.append("Email")
                        terminal_cache.log_alert_trigger(r["id"], r["symbol"], msg, ", ".join(channels))
                        triggered.append(msg)
            if triggered:
                for t in triggered:
                    st.warning(f"TRIGGERED: {t}")
            else:
                st.success("Evaluated all enabled rules — no conditions triggered right now.")

    if c_test_tg.button("Test Telegram", width="stretch", disabled=not tg_ready):
        ok, info = _send_telegram("[IND TERMINAL] Test alert notification connected successfully.")
        (st.success if ok else st.error)(info)

    if c_test_em.button("Test Email", width="stretch", disabled=not email_ready):
        ok, info = _send_email("IND TERMINAL Test Alert", "Test alert notification connected successfully.")
        (st.success if ok else st.error)(info)

    render_section_header("Configured Rules")
    if rules:
        df_rules = pd.DataFrame(rules)
        st.dataframe(df_rules, width="stretch", hide_index=True)
        r_del_c1, r_del_c2, r_del_c3 = st.columns([3, 1, 1])
        rule_map = {f"#{r['id']} {r['symbol']} — {r['condition']} {r['threshold']} ({'ON' if r['enabled'] else 'OFF'})": r for r in rules}
        sel_rule_lbl = r_del_c1.selectbox("Manage Rule", options=list(rule_map.keys()))
        sel_rule = rule_map[sel_rule_lbl]
        if r_del_c2.button("Toggle ON/OFF", width="stretch"):
            terminal_cache.toggle_alert_rule(sel_rule["id"], not bool(sel_rule["enabled"]))
            st.rerun()
        if r_del_c3.button("Delete Rule", width="stretch"):
            terminal_cache.delete_alert_rule(sel_rule["id"])
            st.rerun()
    else:
        st.info("No alert rules created yet.")

    render_section_header("Triggered Alert Log")
    hist = terminal_cache.get_alert_history()
    if hist:
        df_hist = pd.DataFrame(hist)
        st.dataframe(df_hist, width="stretch", hide_index=True)
        render_csv_download(df_hist, "alerts_history.csv", label="Download Alert Log CSV")
    else:
        st.caption("No triggered alerts logged yet.")
