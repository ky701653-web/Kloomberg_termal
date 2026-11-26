"""Polite NSE India public JSON & nselib fetchers with automatic fallbacks."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import requests

from data.market_data import fetch_nifty50_breadth_fallback
from utils.cache import terminal_cache

NSE_BASE_URL = "https://www.nseindia.com"
NSE_NIFTY50_URL = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"
NSE_OPTION_INDEX_URL = "https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
NSE_OPTION_EQUITY_URL = "https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
NSE_FIIDII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
NSE_CORP_ACTIONS_URL = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
NSE_ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"
NSE_IPO_CURRENT_URL = "https://www.nseindia.com/api/ipo-current-issue"
NSE_IPO_UPCOMING_URL = "https://www.nseindia.com/api/all-upcoming-issues?category=ipo"

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/live-equity-market",
}


def _nse_get_json(url: str, timeout: int = 10) -> Any:
    """Perform polite NSE session cookie handshake and fetch JSON."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    session.get(NSE_BASE_URL, timeout=8)
    time.sleep(0.4)
    resp = session.get(url, timeout=timeout)
    if resp.status_code in (401, 403, 429):
        raise RuntimeError(f"HTTP {resp.status_code} (NSE anti-bot / rate limit)")
    resp.raise_for_status()
    return resp.json()


def _log_nse_status(status: str, success: bool, error_msg: str = "") -> None:
    terminal_cache.record_source_status(
        source_name="NSE India Public API",
        status=status,
        delay_note="Near real-time (auto-falls back to yfinance / nselib if blocked)",
        success=success,
        error_msg=error_msg,
    )


def fetch_nse_nifty50_breadth_and_movers(
    ttl_seconds: int = 180,
) -> Tuple[Dict[str, Any], bool, str]:
    """Fetch Nifty 50 advance/decline breadth and top 5 gainers/losers."""
    cache_key = "nse_nifty50_breadth_movers"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    last_error = ""
    for attempt in range(2):
        try:
            payload = _nse_get_json(NSE_NIFTY50_URL)
            raw_items: List[Dict[str, Any]] = payload.get("data", [])
            constituents = [
                row for row in raw_items
                if row.get("symbol") and row.get("symbol") != "NIFTY 50"
            ]
            if not constituents:
                last_error = "NSE returned empty constituent list."
                break

            parsed: List[Dict[str, Any]] = []
            for row in constituents:
                try:
                    parsed.append(
                        {
                            "name": str(row.get("symbol", "")),
                            "symbol": f"{row.get('symbol', '')}.NS",
                            "price": round(float(row.get("lastPrice", 0.0)), 2),
                            "prev_close": round(float(row.get("previousClose", 0.0)), 2),
                            "change": round(float(row.get("change", 0.0)), 2),
                            "pct_change": round(float(row.get("pChange", 0.0)), 2),
                            "high": round(float(row.get("dayHigh", 0.0)), 2),
                            "low": round(float(row.get("dayLow", 0.0)), 2),
                            "volume": int(float(row.get("totalTradedVolume", 0))),
                        }
                    )
                except (TypeError, ValueError):
                    continue

            advances = sum(1 for r in parsed if r["pct_change"] > 0)
            declines = sum(1 for r in parsed if r["pct_change"] < 0)
            unchanged = sum(1 for r in parsed if r["pct_change"] == 0)

            gainers = sorted(parsed, key=lambda r: r["pct_change"], reverse=True)[:5]
            losers = sorted(parsed, key=lambda r: r["pct_change"])[:5]

            result = {
                "advances": advances,
                "declines": declines,
                "unchanged": unchanged,
                "gainers": gainers,
                "losers": losers,
                "source": "NSE India Public Feed (Nifty 50)",
            }
            ts_ist = terminal_cache.set(cache_key, result, ttl_seconds=ttl_seconds)
            _log_nse_status("OK", True)
            return result, False, ts_ist
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(0.8 * (attempt + 1))

    status_label = (
        "RATE LIMITED / BLOCKED"
        if any(code in last_error for code in ("401", "403", "429"))
        else "ERROR"
    )
    _log_nse_status(status_label, False, last_error)

    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None:
        return stale.data, True, stale.fetched_at_ist

    return fetch_nifty50_breadth_fallback(ttl_seconds=300)


def compute_max_pain(strikes_rows: List[Dict[str, Any]]) -> Tuple[Optional[float], List[Dict[str, float]]]:
    """Compute option Max Pain strike and strike-by-strike total payout curve."""
    if not strikes_rows:
        return None, []
    strikes = sorted({float(r["strike"]) for r in strikes_rows})
    curve: List[Dict[str, float]] = []
    for candidate in strikes:
        total_payout = 0.0
        for r in strikes_rows:
            k = float(r["strike"])
            ce_oi = float(r.get("ce_oi") or 0.0)
            pe_oi = float(r.get("pe_oi") or 0.0)
            if candidate > k:
                total_payout += (candidate - k) * ce_oi
            elif candidate < k:
                total_payout += (k - candidate) * pe_oi
        curve.append({"strike": candidate, "total_payout": total_payout})

    best = min(curve, key=lambda x: x["total_payout"])
    return best["strike"], curve


def fetch_option_chain(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    ttl_seconds: int = 120,
) -> Tuple[Dict[str, Any], bool, str]:
    """Fetch NSE option chain (index or equity) with nselib fallback, PCR, and Max Pain."""
    sym = symbol.strip().upper().replace(".NS", "").replace(".BO", "")
    is_index = sym in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}
    cache_key = f"option_chain::{sym}::{expiry or 'NEAREST'}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    url = (NSE_OPTION_INDEX_URL if is_index else NSE_OPTION_EQUITY_URL).format(symbol=sym)
    last_error = ""
    raw_records: Dict[str, Any] = {}

    try:
        payload = _nse_get_json(url, timeout=12)
        raw_records = payload.get("records", {})
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)

    # Secondary fallback via nselib if direct call blocked
    if not raw_records.get("data"):
        try:
            from nselib import derivatives

            df_oc = derivatives.nse_live_option_chain(sym, expiry_date=expiry)
            if df_oc is not None and not df_oc.empty:
                rows = []
                for _, r in df_oc.iterrows():
                    rows.append(
                        {
                            "strike": float(r.get("Strike_Price", r.get("strikePrice", 0))),
                            "expiry": str(r.get("Expiry_Date", expiry or "")),
                            "ce_oi": float(r.get("CALLS_OI", 0) or 0),
                            "ce_chg_oi": float(r.get("CALLS_Chng_in_OI", 0) or 0),
                            "ce_vol": float(r.get("CALLS_Volume", 0) or 0),
                            "ce_iv": float(r.get("CALLS_IV", 0) or 0),
                            "ce_ltp": float(r.get("CALLS_LTP", 0) or 0),
                            "pe_ltp": float(r.get("PUTS_LTP", 0) or 0),
                            "pe_iv": float(r.get("PUTS_IV", 0) or 0),
                            "pe_vol": float(r.get("PUTS_Volume", 0) or 0),
                            "pe_chg_oi": float(r.get("PUTS_Chng_in_OI", 0) or 0),
                            "pe_oi": float(r.get("PUTS_OI", 0) or 0),
                        }
                    )
                spot_val = float(df_oc["Underlying_Value"].iloc[0]) if "Underlying_Value" in df_oc.columns else None
                total_ce_oi = sum(x["ce_oi"] for x in rows)
                total_pe_oi = sum(x["pe_oi"] for x in rows)
                total_ce_vol = sum(x["ce_vol"] for x in rows)
                total_pe_vol = sum(x["pe_vol"] for x in rows)
                max_pain, mp_curve = compute_max_pain(rows)
                bundle = {
                    "symbol": sym,
                    "spot": spot_val,
                    "expiries": sorted({x["expiry"] for x in rows if x["expiry"]}),
                    "selected_expiry": expiry or (rows[0]["expiry"] if rows else ""),
                    "rows": rows,
                    "total_ce_oi": total_ce_oi,
                    "total_pe_oi": total_pe_oi,
                    "pcr_oi": round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else None,
                    "pcr_vol": round(total_pe_vol / total_ce_vol, 3) if total_ce_vol > 0 else None,
                    "max_pain": max_pain,
                    "max_pain_curve": mp_curve,
                    "source": "nselib Option Chain",
                }
                ts_ist = terminal_cache.set(cache_key, bundle, ttl_seconds=ttl_seconds)
                _log_nse_status("OK", True)
                return bundle, False, ts_ist
        except Exception as exc2:  # noqa: BLE001
            last_error = f"{last_error}; nselib: {exc2}".strip("; ")

    if raw_records.get("data"):
        expiries = list(raw_records.get("expiryDates", []))
        sel_exp = expiry if expiry in expiries else (expiries[0] if expiries else "")
        spot_val = raw_records.get("underlyingValue")

        rows: List[Dict[str, Any]] = []
        for item in raw_records.get("data", []):
            if sel_exp and item.get("expiryDate") != sel_exp:
                continue
            ce = item.get("CE") or {}
            pe = item.get("PE") or {}
            rows.append(
                {
                    "strike": float(item.get("strikePrice", 0)),
                    "expiry": str(item.get("expiryDate", sel_exp)),
                    "ce_oi": float(ce.get("openInterest", 0) or 0),
                    "ce_chg_oi": float(ce.get("changeinOpenInterest", 0) or 0),
                    "ce_vol": float(ce.get("totalTradedVolume", 0) or 0),
                    "ce_iv": float(ce.get("impliedVolatility", 0) or 0),
                    "ce_ltp": float(ce.get("lastPrice", 0) or 0),
                    "pe_ltp": float(pe.get("lastPrice", 0) or 0),
                    "pe_iv": float(pe.get("impliedVolatility", 0) or 0),
                    "pe_vol": float(pe.get("totalTradedVolume", 0) or 0),
                    "pe_chg_oi": float(pe.get("changeinOpenInterest", 0) or 0),
                    "pe_oi": float(pe.get("openInterest", 0) or 0),
                }
            )
        rows.sort(key=lambda r: r["strike"])
        total_ce_oi = sum(x["ce_oi"] for x in rows)
        total_pe_oi = sum(x["pe_oi"] for x in rows)
        total_ce_vol = sum(x["ce_vol"] for x in rows)
        total_pe_vol = sum(x["pe_vol"] for x in rows)
        max_pain, mp_curve = compute_max_pain(rows)

        bundle = {
            "symbol": sym,
            "spot": float(spot_val) if spot_val is not None else None,
            "expiries": expiries,
            "selected_expiry": sel_exp,
            "rows": rows,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "pcr_oi": round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else None,
            "pcr_vol": round(total_pe_vol / total_ce_vol, 3) if total_ce_vol > 0 else None,
            "max_pain": max_pain,
            "max_pain_curve": mp_curve,
            "source": "NSE India Option Chain API",
        }
        ts_ist = terminal_cache.set(cache_key, bundle, ttl_seconds=ttl_seconds)
        _log_nse_status("OK", True)
        return bundle, False, ts_ist

    _log_nse_status("BLOCKED / ERROR", False, last_error)
    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None:
        return stale.data, True, stale.fetched_at_ist
    return {"symbol": sym, "rows": [], "error": last_error}, False, "Unavailable"


def fetch_fii_dii_flows(ttl_seconds: int = 900) -> Tuple[List[Dict[str, Any]], bool, str]:
    """Fetch FII/DII net cash market activity from NSE or nselib."""
    cache_key = "nse_fii_dii_flows"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    last_error = ""
    rows: List[Dict[str, Any]] = []

    try:
        payload = _nse_get_json(NSE_FIIDII_URL)
        if isinstance(payload, list):
            for item in payload:
                rows.append(
                    {
                        "category": str(item.get("category", "")),
                        "date": str(item.get("date", "")),
                        "buy_value_cr": float(item.get("buyValue", 0) or 0),
                        "sell_value_cr": float(item.get("sellValue", 0) or 0),
                        "net_value_cr": float(item.get("netValue", 0) or 0),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)

    if not rows:
        try:
            from nselib import capital_market

            df = capital_market.fii_dii_trading_activity()
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    rows.append(
                        {
                            "category": str(r.get("category", r.iloc[0])),
                            "date": str(r.get("date", "")),
                            "buy_value_cr": float(str(r.get("buyValue", 0)).replace(",", "") or 0),
                            "sell_value_cr": float(str(r.get("sellValue", 0)).replace(",", "") or 0),
                            "net_value_cr": float(str(r.get("netValue", 0)).replace(",", "") or 0),
                        }
                    )
        except Exception as exc2:  # noqa: BLE001
            last_error = f"{last_error}; nselib: {exc2}".strip("; ")

    if rows:
        ts_ist = terminal_cache.set(cache_key, rows, ttl_seconds=ttl_seconds)
        _log_nse_status("OK", True)
        return rows, False, ts_ist

    _log_nse_status("BLOCKED / ERROR", False, last_error)
    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None:
        return stale.data, True, stale.fetched_at_ist
    return [], False, "Unavailable"


def fetch_corporate_actions_and_filings(
    ticker: Optional[str] = None,
    ttl_seconds: int = 1800,
) -> Tuple[Dict[str, Any], bool, str]:
    """Fetch NSE corporate actions & announcements with yfinance corporate-action fallback."""
    clean_sym = (ticker or "").strip().upper().replace(".NS", "").replace(".BO", "")
    cache_key = f"corp_actions::{clean_sym or 'MARKET'}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    actions: List[Dict[str, Any]] = []
    announcements: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        raw_actions = _nse_get_json(NSE_CORP_ACTIONS_URL)
        if isinstance(raw_actions, list):
            for it in raw_actions[:80]:
                sym = str(it.get("symbol", ""))
                if clean_sym and sym != clean_sym:
                    continue
                actions.append(
                    {
                        "symbol": sym,
                        "company": str(it.get("comp", "")),
                        "subject": str(it.get("subject", "")),
                        "ex_date": str(it.get("exDate", "")),
                        "rec_date": str(it.get("recDate", "")),
                        "series": str(it.get("series", "")),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"NSE Actions: {exc}")

    try:
        raw_ann = _nse_get_json(NSE_ANNOUNCEMENTS_URL)
        if isinstance(raw_ann, list):
            for it in raw_ann[:80]:
                sym = str(it.get("symbol", ""))
                if clean_sym and sym != clean_sym:
                    continue
                announcements.append(
                    {
                        "symbol": sym,
                        "company": str(it.get("sm_name", "")),
                        "subject": str(it.get("desc", "")),
                        "date": str(it.get("an_dt", "")),
                        "attachment": str(it.get("attchmntFile", "")),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"NSE Filings: {exc}")

    yf_dividends: List[Dict[str, Any]] = []
    yf_splits: List[Dict[str, Any]] = []
    if clean_sym:
        try:
            import yfinance as yf

            tk = yf.Ticker(f"{clean_sym}.NS")
            divs = tk.dividends
            if divs is not None and not divs.empty:
                for dt, val in divs.tail(15).items():
                    yf_dividends.append({"date": dt.strftime("%Y-%m-%d"), "dividend_inr": round(float(val), 2)})
            splits = tk.splits
            if splits is not None and not splits.empty:
                for dt, val in splits.tail(10).items():
                    yf_splits.append({"date": dt.strftime("%Y-%m-%d"), "ratio": float(val)})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"yfinance actions: {exc}")

    bundle = {
        "actions": actions,
        "announcements": announcements,
        "yf_dividends": list(reversed(yf_dividends)),
        "yf_splits": list(reversed(yf_splits)),
        "errors": errors,
    }
    if actions or announcements or yf_dividends or yf_splits:
        ts_ist = terminal_cache.set(cache_key, bundle, ttl_seconds=ttl_seconds)
        return bundle, False, ts_ist

    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None:
        return stale.data, True, stale.fetched_at_ist
    return bundle, False, "Unavailable"


def fetch_ipo_data(ttl_seconds: int = 1800) -> Tuple[Dict[str, Any], bool, str]:
    """Fetch current/upcoming Indian IPOs from NSE with Google News IPO RSS fallback."""
    cache_key = "nse_ipo_tracker"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    current_ipos: List[Dict[str, Any]] = []
    upcoming_ipos: List[Dict[str, Any]] = []
    ipo_news: List[Dict[str, str]] = []
    errors: List[str] = []

    try:
        cur = _nse_get_json(NSE_IPO_CURRENT_URL)
        if isinstance(cur, list):
            for it in cur:
                current_ipos.append(
                    {
                        "symbol": str(it.get("symbol", "")),
                        "company": str(it.get("companyName", "")),
                        "series": str(it.get("series", "")),
                        "issue_start": str(it.get("issueStartDate", "")),
                        "issue_end": str(it.get("issueEndDate", "")),
                        "price_band": str(it.get("issuePrice", "")),
                        "status": str(it.get("status", "Active")),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"NSE Current IPOs: {exc}")

    try:
        upc = _nse_get_json(NSE_IPO_UPCOMING_URL)
        if isinstance(upc, list):
            for it in upc:
                upcoming_ipos.append(
                    {
                        "symbol": str(it.get("symbol", "")),
                        "company": str(it.get("companyName", "")),
                        "series": str(it.get("series", "")),
                        "issue_start": str(it.get("issueStartDate", "")),
                        "issue_end": str(it.get("issueEndDate", "")),
                        "price_band": str(it.get("issuePrice", "")),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"NSE Upcoming IPOs: {exc}")

    try:
        rss_url = f"https://news.google.com/rss/search?q={quote_plus('India IPO NSE BSE GMP subscription listing')}&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(rss_url, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries[:15]:
            ipo_news.append(
                {
                    "title": str(entry.get("title", "")),
                    "published": str(entry.get("published", "")),
                    "link": str(entry.get("link", "")),
                }
            )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"IPO News RSS: {exc}")

    bundle = {
        "current": current_ipos,
        "upcoming": upcoming_ipos,
        "news": ipo_news,
        "errors": errors,
    }
    if current_ipos or upcoming_ipos or ipo_news:
        ts_ist = terminal_cache.set(cache_key, bundle, ttl_seconds=ttl_seconds)
        return bundle, False, ts_ist

    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None:
        return stale.data, True, stale.fetched_at_ist
    return bundle, False, "Unavailable"
