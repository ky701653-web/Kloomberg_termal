"""Daily AI Market Summary generator (optional Gemini/OpenAI LLM + built-in zero-key NLP brief)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import requests

from utils.cache import terminal_cache
from utils.secrets import get_secret


def build_deterministic_market_summary(
    indices: List[Dict[str, Any]],
    macro: List[Dict[str, Any]],
    breadth: Dict[str, Any],
    headlines: List[Dict[str, Any]],
) -> str:
    """Create a structured, data-grounded Indian market brief without needing any paid LLM key."""
    idx_map = {r.get("name", ""): r for r in (indices or [])}
    nifty = idx_map.get("Nifty 50")
    sensex = idx_map.get("Sensex")
    banknifty = idx_map.get("Bank Nifty")
    vix = idx_map.get("India VIX")

    # Determine market tone from Nifty + Breadth + VADER headlines
    nifty_pct = float(nifty["pct_change"]) if nifty else 0.0
    adv = int(breadth.get("advances", 0))
    dec = int(breadth.get("declines", 0))
    total_b = adv + dec + int(breadth.get("unchanged", 0))

    avg_sent = (
        sum(float(a.get("sentiment_score", 0.0)) for a in headlines) / len(headlines)
        if headlines
        else 0.0
    )
    if nifty_pct >= 0.4 and (adv >= dec or avg_sent >= 0.05):
        tone = "Risk-On / Constructive"
    elif nifty_pct <= -0.4 and (dec > adv or avg_sent <= -0.05):
        tone = "Risk-Off / Cautious"
    else:
        tone = "Range-Bound / Mixed"

    parts: List[str] = [f"**Market Tone:** {tone}"]

    idx_bits = []
    for lbl, row in [("Nifty 50", nifty), ("Sensex", sensex), ("Bank Nifty", banknifty)]:
        if row:
            idx_bits.append(f"{lbl} at **{row['price']:,.2f}** ({row['pct_change']:+.2f}%)")
    if vix:
        idx_bits.append(f"India VIX at **{vix['price']:.2f}** ({vix['pct_change']:+.2f}%)")
    if idx_bits:
        parts.append("• **Benchmarks:** " + " | ".join(idx_bits) + ".")

    if total_b > 0:
        gainers = breadth.get("gainers", [])
        losers = breadth.get("losers", [])
        g_str = f"{gainers[0]['name']} ({gainers[0]['pct_change']:+.2f}%)" if gainers else "N/A"
        l_str = f"{losers[0]['name']} ({losers[0]['pct_change']:+.2f}%)" if losers else "N/A"
        parts.append(
            f"• **Nifty 50 Breadth:** {adv} advances vs {dec} declines. "
            f"Top leader: **{g_str}**; laggard: **{l_str}**."
        )

    macro_map = {r.get("name", ""): r for r in (macro or [])}
    usdinr = macro_map.get("USD / INR") or macro_map.get("USD / INR (ECB Ref)")
    brent = macro_map.get("Brent Crude")
    gold = macro_map.get("Gold (COMEX)")
    m_bits = []
    if usdinr:
        m_bits.append(f"USD/INR ₹{usdinr['price']:.2f}")
    if brent:
        m_bits.append(f"Brent ${brent['price']:.2f} ({brent['pct_change']:+.2f}%)")
    if gold:
        m_bits.append(f"Gold ${gold['price']:,.2f} ({gold['pct_change']:+.2f}%)")
    if m_bits:
        parts.append("• **FX & Commodities:** " + " | ".join(m_bits) + ".")

    if headlines:
        bulls = sum(1 for h in headlines if h.get("sentiment") == "Bullish")
        bears = sum(1 for h in headlines if h.get("sentiment") == "Bearish")
        top_titles = "; ".join(h["title"] for h in headlines[:3])
        parts.append(
            f"• **News Flow ({len(headlines)} headlines, avg VADER {avg_sent:+.2f}):** "
            f"{bulls} bullish / {bears} bearish. Key stories: _{top_titles}_."
        )

    return "\n\n".join(parts)


def generate_ai_market_summary(
    indices: List[Dict[str, Any]],
    macro: List[Dict[str, Any]],
    breadth: Dict[str, Any],
    headlines: List[Dict[str, Any]],
    ttl_seconds: int = 300,
) -> Tuple[str, str, str]:
    """
    Generate daily Indian market summary using Gemini/OpenAI if configured, else built-in NLP.

    Returns:
        (markdown_summary, engine_label, generated_at_ist)
    """
    cache_key = "daily_ai_market_summary"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None and isinstance(cached.data, dict):
        return cached.data["summary"], cached.data["engine"], cached.fetched_at_ist

    fallback_summary = build_deterministic_market_summary(indices, macro, breadth, headlines)

    gemini_key = get_secret("GEMINI_API_KEY")
    openai_key = get_secret("OPENAI_API_KEY")

    prompt = (
        "Write a concise, objective 4-bullet Indian equity market daily brief (Nifty/Sensex, breadth, "
        "FX/crude, and top news drivers) strictly from these numbers and headlines:\n\n"
        f"{fallback_summary}"
    )

    summary_text = fallback_summary
    engine = "Built-in NLP & VADER Engine (Free)"

    if gemini_key:
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=12,
            )
            resp.raise_for_status()
            cand = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if cand:
                summary_text = cand
                engine = "Gemini AI Summary"
        except Exception:
            pass
    elif openai_key:
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 320,
                },
                timeout=12,
            )
            resp.raise_for_status()
            cand = resp.json()["choices"][0]["message"]["content"].strip()
            if cand:
                summary_text = cand
                engine = "OpenAI AI Summary"
        except Exception:
            pass

    ts_ist = terminal_cache.set(cache_key, {"summary": summary_text, "engine": engine}, ttl_seconds=ttl_seconds)
    return summary_text, engine, ts_ist
