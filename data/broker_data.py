"""Real-time Indian Broker API connectors (Zerodha Kite Connect, Upstox v2, Angel One SmartAPI)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import requests

from utils.cache import terminal_cache
from utils.secrets import get_secret


def to_kite_instrument(symbol: str) -> str:
    """Convert RELIANCE.NS / TCS.BO / RELIANCE into Kite format (NSE:RELIANCE / BSE:TCS)."""
    s = symbol.strip().upper()
    if ":" in s:
        return s
    if s.endswith(".BO"):
        return f"BSE:{s[:-3]}"
    if s.endswith(".NS"):
        return f"NSE:{s[:-3]}"
    return f"NSE:{s}"


def parse_kite_quote_response(payload: Dict[str, Any], instrument: str) -> Optional[Dict[str, Any]]:
    """Normalize Zerodha Kite Connect /quote response payload."""
    data = (payload or {}).get("data") or {}
    q = data.get(instrument) or next(iter(data.values()), None)
    if not isinstance(q, dict):
        return None
    ohlc = q.get("ohlc") or {}
    ltp = float(q.get("last_price") or 0.0)
    prev_close = float(ohlc.get("close") or ltp)
    chg = ltp - prev_close
    pct = (chg / prev_close * 100.0) if prev_close else 0.0
    return {
        "broker": "Zerodha Kite Connect",
        "symbol": instrument,
        "ltp": round(ltp, 2),
        "change": round(chg, 2),
        "pct_change": round(pct, 2),
        "open": ohlc.get("open"),
        "high": ohlc.get("high"),
        "low": ohlc.get("low"),
        "prev_close": prev_close,
        "volume": q.get("volume"),
        "timestamp": str(q.get("timestamp") or q.get("last_trade_time") or ""),
    }


def parse_upstox_quote_response(payload: Dict[str, Any], instrument_key: str) -> Optional[Dict[str, Any]]:
    """Normalize Upstox v2 /market-quote/quotes response payload."""
    data = (payload or {}).get("data") or {}
    q = data.get(instrument_key) or next(iter(data.values()), None)
    if not isinstance(q, dict):
        return None
    ohlc = q.get("ohlc") or {}
    ltp = float(q.get("last_price") or 0.0)
    prev_close = float(ohlc.get("close") or ltp)
    chg = float(q.get("net_change") if q.get("net_change") is not None else (ltp - prev_close))
    pct = (chg / prev_close * 100.0) if prev_close else 0.0
    return {
        "broker": "Upstox v2",
        "symbol": str(q.get("symbol") or instrument_key),
        "ltp": round(ltp, 2),
        "change": round(chg, 2),
        "pct_change": round(pct, 2),
        "open": ohlc.get("open"),
        "high": ohlc.get("high"),
        "low": ohlc.get("low"),
        "prev_close": prev_close,
        "volume": q.get("volume"),
        "timestamp": str(q.get("last_trade_time") or ""),
    }


def parse_angel_quote_response(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize Angel One SmartAPI /market/v1/quote response payload."""
    fetched: List[Dict[str, Any]] = ((payload or {}).get("data") or {}).get("fetched") or []
    if not fetched:
        return None
    q = fetched[0]
    ltp = float(q.get("ltp") or 0.0)
    prev_close = float(q.get("close") or ltp)
    chg = float(q.get("netChange") if q.get("netChange") is not None else (ltp - prev_close))
    pct = float(q.get("percentChange") if q.get("percentChange") is not None else ((chg / prev_close * 100.0) if prev_close else 0.0))
    return {
        "broker": "Angel One SmartAPI",
        "symbol": str(q.get("tradingSymbol") or q.get("symbolToken") or ""),
        "ltp": round(ltp, 2),
        "change": round(chg, 2),
        "pct_change": round(pct, 2),
        "open": q.get("open"),
        "high": q.get("high"),
        "low": q.get("low"),
        "prev_close": prev_close,
        "volume": q.get("tradeVolume"),
        "timestamp": str(q.get("exchFeedTime") or ""),
    }


def fetch_zerodha_quote(symbol: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Fetch real-time quote from Zerodha Kite Connect REST API."""
    api_key = get_secret("ZERODHA_API_KEY")
    access_token = get_secret("ZERODHA_ACCESS_TOKEN")
    if not api_key or not access_token:
        return None, "Missing ZERODHA_API_KEY or ZERODHA_ACCESS_TOKEN in .env / Secrets."

    instrument = to_kite_instrument(symbol)
    try:
        resp = requests.get(
            "https://api.kite.trade/quote",
            params={"i": instrument},
            headers={
                "X-Kite-Version": "3",
                "Authorization": f"token {api_key}:{access_token}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        parsed = parse_kite_quote_response(resp.json(), instrument)
        if not parsed:
            return None, f"No quote returned for {instrument}."
        terminal_cache.record_source_status("Zerodha Kite Connect", "OK", "Real-time broker quote", True)
        return parsed, ""
    except Exception as exc:  # noqa: BLE001
        terminal_cache.record_source_status("Zerodha Kite Connect", "ERROR", "Real-time broker quote", False, str(exc))
        return None, str(exc)


def fetch_upstox_quote(instrument_key: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Fetch real-time quote from Upstox v2 REST API (e.g., NSE_EQ|INE002A01018)."""
    token = get_secret("UPSTOX_ACCESS_TOKEN")
    if not token:
        return None, "Missing UPSTOX_ACCESS_TOKEN in .env / Secrets."

    key = instrument_key.strip()
    try:
        resp = requests.get(
            "https://api.upstox.com/v2/market-quote/quotes",
            params={"instrument_key": key},
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        parsed = parse_upstox_quote_response(resp.json(), key)
        if not parsed:
            return None, f"No quote returned for {key}."
        terminal_cache.record_source_status("Upstox v2 API", "OK", "Real-time broker quote", True)
        return parsed, ""
    except Exception as exc:  # noqa: BLE001
        terminal_cache.record_source_status("Upstox v2 API", "ERROR", "Real-time broker quote", False, str(exc))
        return None, str(exc)


def fetch_angel_quote(symbol_token: str, exchange: str = "NSE") -> Tuple[Optional[Dict[str, Any]], str]:
    """Fetch real-time quote from Angel One SmartAPI REST endpoint."""
    api_key = get_secret("ANGEL_API_KEY")
    access_token = get_secret("ANGEL_ACCESS_TOKEN")
    if not api_key or not access_token:
        return None, "Missing ANGEL_API_KEY or ANGEL_ACCESS_TOKEN in .env / Secrets."

    local_ip = get_secret("ANGEL_CLIENT_LOCAL_IP", "127.0.0.1")
    public_ip = get_secret("ANGEL_CLIENT_PUBLIC_IP", "127.0.0.1")
    mac_addr = get_secret("ANGEL_MAC_ADDRESS", "00:00:00:00:00:00")

    try:
        resp = requests.post(
            "https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote",
            json={"mode": "FULL", "exchangeTokens": {exchange.upper(): [symbol_token.strip()]}},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": local_ip,
                "X-ClientPublicIP": public_ip,
                "X-MACAddress": mac_addr,
                "X-PrivateKey": api_key,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        parsed = parse_angel_quote_response(resp.json())
        if not parsed:
            return None, f"No quote returned for token {symbol_token}."
        terminal_cache.record_source_status("Angel One SmartAPI", "OK", "Real-time broker quote", True)
        return parsed, ""
    except Exception as exc:  # noqa: BLE001
        terminal_cache.record_source_status("Angel One SmartAPI", "ERROR", "Real-time broker quote", False, str(exc))
        return None, str(exc)
