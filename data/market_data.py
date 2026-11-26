"""Resilient yfinance, Frankfurter FX, Nifty 500 universe, and fundamentals fetchers with SQLite caching."""

from __future__ import annotations

import csv
import hashlib
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf

from utils.cache import terminal_cache
from utils.indicators import compute_rsi

USER_AGENT = "IndiaTerminal/0.2 (Personal Open-Source Financial Research App)"
NIFTY500_CSV_PATH = Path(__file__).resolve().parent / "nifty500.csv"

INDIAN_INDICES: List[Tuple[str, str]] = [
    ("Nifty 50", "^NSEI"),
    ("Sensex", "^BSESN"),
    ("Bank Nifty", "^NSEBANK"),
    ("India VIX", "^INDIAVIX"),
]

SECTOR_INDICES: List[Tuple[str, str]] = [
    ("Nifty Bank", "^NSEBANK"),
    ("Nifty IT", "^CNXIT"),
    ("Nifty Auto", "^CNXAUTO"),
    ("Nifty Pharma", "^CNXPHARMA"),
    ("Nifty FMCG", "^CNXFMCG"),
    ("Nifty Metal", "^CNXMETAL"),
    ("Nifty Energy", "^CNXENERGY"),
    ("Nifty Realty", "^CNXREALTY"),
    ("Nifty PSU Bank", "^CNXPSUBANK"),
    ("Nifty Media", "^CNXMEDIA"),
    ("Nifty Infra", "^CNXINFRA"),
]

MACRO_COMMODITIES: List[Tuple[str, str, str]] = [
    ("USD / INR", "INR=X", "₹"),
    ("Gold (COMEX)", "GC=F", "$"),
    ("WTI Crude", "CL=F", "$"),
    ("Brent Crude", "BZ=F", "$"),
]

GLOBAL_INDICES: List[Tuple[str, str]] = [
    ("S&P 500", "^GSPC"),
    ("Nasdaq Composite", "^IXIC"),
    ("Dow Jones", "^DJI"),
    ("Nikkei 225", "^N225"),
    ("Hang Seng", "^HSI"),
]

DEFAULT_WATCHLIST: List[str] = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "ITC.NS",
]

NIFTY_50_SECTOR_MAP: Dict[str, str] = {
    "ADANIENT.NS": "Metals & Mining",
    "ADANIPORTS.NS": "Services",
    "APOLLOHOSP.NS": "Healthcare",
    "ASIANPAINT.NS": "Consumer Durables",
    "AXISBANK.NS": "Financial Services",
    "BAJAJ-AUTO.NS": "Automobile",
    "BAJFINANCE.NS": "Financial Services",
    "BAJAJFINSV.NS": "Financial Services",
    "BEL.NS": "Capital Goods",
    "BHARTIARTL.NS": "Telecom",
    "CIPLA.NS": "Healthcare",
    "COALINDIA.NS": "Oil, Gas & Consumable Fuels",
    "DRREDDY.NS": "Healthcare",
    "EICHERMOT.NS": "Automobile",
    "ETERNAL.NS": "Consumer Services",
    "GRASIM.NS": "Construction Materials",
    "HCLTECH.NS": "IT",
    "HDFCBANK.NS": "Financial Services",
    "HDFCLIFE.NS": "Financial Services",
    "HEROMOTOCO.NS": "Automobile",
    "HINDALCO.NS": "Metals & Mining",
    "HINDUNILVR.NS": "FMCG",
    "ICICIBANK.NS": "Financial Services",
    "INDUSINDBK.NS": "Financial Services",
    "INFY.NS": "IT",
    "ITC.NS": "FMCG",
    "JIOFIN.NS": "Financial Services",
    "JSWSTEEL.NS": "Metals & Mining",
    "KOTAKBANK.NS": "Financial Services",
    "LT.NS": "Construction",
    "M&M.NS": "Automobile",
    "MARUTI.NS": "Automobile",
    "NESTLEIND.NS": "FMCG",
    "NTPC.NS": "Power",
    "ONGC.NS": "Oil, Gas & Consumable Fuels",
    "POWERGRID.NS": "Power",
    "RELIANCE.NS": "Oil, Gas & Consumable Fuels",
    "SBILIFE.NS": "Financial Services",
    "SBIN.NS": "Financial Services",
    "SHRIRAMFIN.NS": "Financial Services",
    "SUNPHARMA.NS": "Healthcare",
    "TATACONSUM.NS": "FMCG",
    "TATASTEEL.NS": "Metals & Mining",
    "TCS.NS": "IT",
    "TECHM.NS": "IT",
    "TITAN.NS": "Consumer Durables",
    "TMPV.NS": "Automobile",
    "TRENT.NS": "Consumer Services",
    "ULTRACEMCO.NS": "Construction Materials",
    "WIPRO.NS": "IT",
}

NIFTY_50_TICKERS: List[str] = list(NIFTY_50_SECTOR_MAP.keys())


def _safe_float(val: Any) -> Optional[float]:
    try:
        num = float(val)
        return num if math.isfinite(num) else None
    except (TypeError, ValueError):
        return None


def _extract_quote_from_history(hist: pd.DataFrame, symbol: str, name: str) -> Optional[Dict[str, Any]]:
    """Compute last price, previous close, change, and % change from an OHLCV DataFrame."""
    if hist is None or hist.empty or "Close" not in hist.columns:
        return None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None

    last_price = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else last_price
    change = last_price - prev_close
    pct_change = (change / prev_close * 100.0) if prev_close else 0.0

    day_high = float(hist["High"].dropna().iloc[-1]) if "High" in hist.columns and not hist["High"].dropna().empty else None
    day_low = float(hist["Low"].dropna().iloc[-1]) if "Low" in hist.columns and not hist["Low"].dropna().empty else None
    volume = float(hist["Volume"].dropna().iloc[-1]) if "Volume" in hist.columns and not hist["Volume"].dropna().empty else None

    return {
        "name": name,
        "symbol": symbol,
        "price": round(last_price, 2),
        "prev_close": round(prev_close, 2),
        "change": round(change, 2),
        "pct_change": round(pct_change, 2),
        "high": round(day_high, 2) if day_high is not None else None,
        "low": round(day_low, 2) if day_low is not None else None,
        "volume": int(volume) if volume is not None else None,
    }


def fetch_yfinance_quotes(
    items: List[Tuple[str, str]],
    cache_key: str,
    ttl_seconds: int = 120,
    retries: int = 2,
) -> Tuple[List[Dict[str, Any]], bool, str]:
    """Fetch latest quotes for a list of (display_name, ticker) pairs via yfinance."""
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    symbols = [sym for _, sym in items]
    name_map = {sym: name for name, sym in items}
    last_error = ""

    for attempt in range(retries):
        try:
            df = yf.download(
                tickers=symbols,
                period="5d",
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=True,
                timeout=15,
            )
            results: List[Dict[str, Any]] = []
            if df is not None and not df.empty:
                is_multi = isinstance(df.columns, pd.MultiIndex)
                for sym in symbols:
                    if is_multi:
                        if sym not in df.columns.get_level_values(0):
                            continue
                        sub = df[sym]
                    else:
                        sub = df
                    quote = _extract_quote_from_history(sub, sym, name_map[sym])
                    if quote:
                        results.append(quote)

            if results:
                ts_ist = terminal_cache.set(cache_key, results, ttl_seconds=ttl_seconds)
                terminal_cache.record_source_status(
                    source_name="Yahoo Finance (yfinance)",
                    status="OK",
                    delay_note="~15 min delayed (NSE/BSE); EOD for some indices",
                    success=True,
                )
                return results, False, ts_ist

            last_error = "Empty response returned by yfinance."
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        if attempt < retries - 1:
            time.sleep(0.5 * (attempt + 1))

    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None:
        terminal_cache.record_source_status(
            source_name="Yahoo Finance (yfinance)",
            status="CACHED FALLBACK",
            delay_note="~15 min delayed (showing last cached snapshot)",
            success=False,
            error_msg=last_error,
        )
        return stale.data, True, stale.fetched_at_ist

    terminal_cache.record_source_status(
        source_name="Yahoo Finance (yfinance)",
        status="ERROR",
        delay_note="~15 min delayed (NSE/BSE)",
        success=False,
        error_msg=last_error,
    )
    return [], False, "Unavailable"


def fetch_watchlist_quotes(
    tickers: List[str],
    ttl_seconds: int = 60,
) -> Tuple[List[Dict[str, Any]], bool, str]:
    """Fetch price, % change, volume, 52-week range, and 30-day sparkline with 60s TTL."""
    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
    if not clean_tickers:
        return [], False, "No tickers"

    cache_key = "watchlist::" + ",".join(sorted(clean_tickers))
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    try:
        df = yf.download(
            tickers=clean_tickers,
            period="1y",
            interval="1d",
            group_by="ticker",
            progress=False,
            threads=True,
            timeout=20,
        )
        rows: List[Dict[str, Any]] = []
        if df is not None and not df.empty:
            is_multi = isinstance(df.columns, pd.MultiIndex)
            for sym in clean_tickers:
                if is_multi:
                    if sym not in df.columns.get_level_values(0):
                        continue
                    sub = df[sym]
                else:
                    sub = df
                closes = sub["Close"].dropna() if "Close" in sub.columns else pd.Series(dtype=float)
                if closes.empty:
                    continue
                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) >= 2 else price
                chg = price - prev
                pct = (chg / prev * 100.0) if prev else 0.0
                high_52w = float(sub["High"].dropna().max()) if "High" in sub.columns and not sub["High"].dropna().empty else float(closes.max())
                low_52w = float(sub["Low"].dropna().min()) if "Low" in sub.columns and not sub["Low"].dropna().empty else float(closes.min())
                vol = int(float(sub["Volume"].dropna().iloc[-1])) if "Volume" in sub.columns and not sub["Volume"].dropna().empty else 0
                spark = [round(float(x), 2) for x in closes.tail(25).tolist()]
                pos_52w = ((price - low_52w) / (high_52w - low_52w) * 100.0) if high_52w > low_52w else 50.0
                rows.append(
                    {
                        "symbol": sym,
                        "name": sym.replace(".NS", "").replace(".BO", ""),
                        "price": round(price, 2),
                        "change": round(chg, 2),
                        "pct_change": round(pct, 2),
                        "volume": vol,
                        "high_52w": round(high_52w, 2),
                        "low_52w": round(low_52w, 2),
                        "pos_52w_pct": round(pos_52w, 1),
                        "sparkline": spark,
                    }
                )
        if rows:
            ts_ist = terminal_cache.set(cache_key, rows, ttl_seconds=ttl_seconds)
            terminal_cache.record_source_status(
                source_name="Yahoo Finance (yfinance)",
                status="OK",
                delay_note="~15 min delayed (NSE/BSE); 60s watchlist cache",
                success=True,
            )
            return rows, False, ts_ist
    except Exception as exc:  # noqa: BLE001
        stale = terminal_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return stale.data, True, stale.fetched_at_ist
        terminal_cache.record_source_status(
            source_name="Yahoo Finance (yfinance)",
            status="ERROR",
            delay_note="~15 min delayed (NSE/BSE)",
            success=False,
            error_msg=str(exc),
        )
        return [], False, "Unavailable"

    return [], False, "Unavailable"


def fetch_ohlcv(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    ttl_seconds: int = 120,
) -> Tuple[pd.DataFrame, bool, str]:
    """Fetch OHLCV DataFrame for charting and technical analysis, cached in SQLite."""
    sym = ticker.strip().upper()
    cache_key = f"ohlcv::{sym}::{period}::{interval}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None and cached.data:
        df = pd.DataFrame(cached.data)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        return df, False, cached.fetched_at_ist

    try:
        df = yf.download(
            tickers=sym,
            period=period,
            interval=interval,
            progress=False,
            threads=False,
            timeout=15,
        )
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).copy()
            records = []
            for idx, row in df.iterrows():
                records.append(
                    {
                        "Date": idx.isoformat(),
                        "Open": float(row["Open"]),
                        "High": float(row["High"]),
                        "Low": float(row["Low"]),
                        "Close": float(row["Close"]),
                        "Volume": float(row["Volume"]) if pd.notna(row["Volume"]) else 0.0,
                    }
                )
            ts_ist = terminal_cache.set(cache_key, records, ttl_seconds=ttl_seconds)
            return df, False, ts_ist
    except Exception:
        pass

    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None and stale.data:
        df = pd.DataFrame(stale.data)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        return df, True, stale.fetched_at_ist
    return pd.DataFrame(), False, "Unavailable"


def fetch_multi_close(
    tickers: List[str],
    period: str = "1y",
    ttl_seconds: int = 180,
) -> Tuple[pd.DataFrame, bool, str]:
    """Fetch aligned Close prices for multiple tickers (for rebased comparison)."""
    clean = [t.strip().upper() for t in tickers if t.strip()]
    if not clean:
        return pd.DataFrame(), False, "No tickers"

    cache_key = f"multiclose::{period}::" + ",".join(sorted(clean))
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None and cached.data:
        df = pd.DataFrame(cached.data)
        df["Date"] = pd.to_datetime(df["Date"])
        return df.set_index("Date"), False, cached.fetched_at_ist

    try:
        raw = yf.download(tickers=clean, period=period, interval="1d", progress=False, threads=True, timeout=20)
        if raw is not None and not raw.empty:
            if isinstance(raw.columns, pd.MultiIndex):
                closes = raw["Close"].copy()
            else:
                closes = raw[["Close"]].copy()
                closes.columns = clean[:1]
            closes = closes.dropna(how="all")
            if not closes.empty:
                out = closes.reset_index()
                date_col = out.columns[0]
                out = out.rename(columns={date_col: "Date"})
                out["Date"] = out["Date"].astype(str)
                ts_ist = terminal_cache.set(cache_key, out.to_dict(orient="records"), ttl_seconds=ttl_seconds)
                return closes, False, ts_ist
    except Exception:
        pass

    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None and stale.data:
        df = pd.DataFrame(stale.data)
        df["Date"] = pd.to_datetime(df["Date"])
        return df.set_index("Date"), True, stale.fetched_at_ist
    return pd.DataFrame(), False, "Unavailable"


def _df_to_table_dict(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Convert a yfinance financial statement DataFrame into JSON-safe dict."""
    if df is None or df.empty:
        return {"columns": [], "rows": []}
    cols = [str(c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else c) for c in df.columns]
    rows = []
    for idx, r in df.iterrows():
        item: Dict[str, Any] = {"Line Item": str(idx)}
        for col_name, val in zip(cols, r.tolist()):
            item[col_name] = _safe_float(val)
        rows.append(item)
    return {"columns": ["Line Item"] + cols, "rows": rows}


def load_nifty500_universe() -> List[Dict[str, str]]:
    """Load local Nifty 500 ticker universe from data/nifty500.csv (falls back to Nifty 50)."""
    if NIFTY500_CSV_PATH.exists():
        items: List[Dict[str, str]] = []
        with NIFTY500_CSV_PATH.open("r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = (row.get("Symbol") or "").strip().upper()
                if not sym:
                    continue
                items.append(
                    {
                        "symbol": sym,
                        "yf_ticker": f"{sym}.NS",
                        "name": (row.get("Company Name") or sym).strip(),
                        "sector": (row.get("Industry") or "Other").strip(),
                    }
                )
        if items:
            return items

    return [
        {
            "symbol": t.replace(".NS", ""),
            "yf_ticker": t,
            "name": t.replace(".NS", ""),
            "sector": sec,
        }
        for t, sec in NIFTY_50_SECTOR_MAP.items()
    ]


def fetch_stock_ratios(ticker: str, ttl_seconds: int = 3600) -> Dict[str, Any]:
    """Fetch cached valuation & profitability ratios for a single ticker via yfinance."""
    sym = ticker.strip().upper()
    cache_key = f"ratios::{sym}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data

    try:
        info = yf.Ticker(sym).info or {}
        div_raw = _safe_float(info.get("dividendYield"))
        # yfinance returns dividendYield either as percentage (e.g., 1.45) or fraction (0.0145)
        div_pct = None
        if div_raw is not None:
            div_pct = round(div_raw if div_raw > 0.25 else div_raw * 100.0, 2)

        roe_raw = _safe_float(info.get("returnOnEquity"))
        roe_pct = round(roe_raw * 100.0, 2) if roe_raw is not None else None

        data = {
            "symbol": sym,
            "short_name": info.get("shortName") or sym.replace(".NS", ""),
            "sector": info.get("sector") or "Unknown",
            "industry": info.get("industry") or "Unknown",
            "market_cap": _safe_float(info.get("marketCap")),
            "pe": _safe_float(info.get("trailingPE")),
            "forward_pe": _safe_float(info.get("forwardPE")),
            "pb": _safe_float(info.get("priceToBook")),
            "roe_pct": roe_pct,
            "roa_pct": round(_safe_float(info.get("returnOnAssets")) * 100.0, 2) if _safe_float(info.get("returnOnAssets")) is not None else None,
            "debt_to_equity": _safe_float(info.get("debtToEquity")),
            "div_yield_pct": div_pct,
            "current_price": _safe_float(info.get("currentPrice") or info.get("regularMarketPrice")),
            "high_52w": _safe_float(info.get("fiftyTwoWeekHigh")),
            "low_52w": _safe_float(info.get("fiftyTwoWeekLow")),
            "eps": _safe_float(info.get("trailingEps")),
            "profit_margin_pct": round(_safe_float(info.get("profitMargins")) * 100.0, 2) if _safe_float(info.get("profitMargins")) is not None else None,
            "summary": info.get("longBusinessSummary") or "",
        }
        terminal_cache.set(cache_key, data, ttl_seconds=ttl_seconds)
        return data
    except Exception:
        stale = terminal_cache.get(cache_key, allow_stale=True)
        return stale.data if stale else {"symbol": sym}


def fetch_fundamentals(ticker: str, ttl_seconds: int = 1800) -> Tuple[Dict[str, Any], bool, str]:
    """Fetch financial statements, quarterly results, key ratios, and sector peers."""
    sym = ticker.strip().upper()
    cache_key = f"fundamentals::{sym}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    try:
        tk = yf.Ticker(sym)
        ratios = fetch_stock_ratios(sym, ttl_seconds=ttl_seconds)

        # Find sector peers from local Nifty 500 list
        universe = load_nifty500_universe()
        base_sym = sym.replace(".NS", "").replace(".BO", "")
        my_entry = next((u for u in universe if u["symbol"] == base_sym), None)
        peer_candidates: List[str] = []
        if my_entry:
            peer_candidates = [
                u["yf_ticker"]
                for u in universe
                if u["sector"] == my_entry["sector"] and u["symbol"] != base_sym
            ][:5]
        if not peer_candidates:
            peer_candidates = [t for t in DEFAULT_WATCHLIST if t != sym][:4]

        peers: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = {pool.submit(fetch_stock_ratios, p, ttl_seconds): p for p in [sym] + peer_candidates}
            for fut in as_completed(futs):
                try:
                    peers.append(fut.result())
                except Exception:
                    continue

        bundle = {
            "ratios": ratios,
            "income_annual": _df_to_table_dict(tk.financials),
            "income_quarterly": _df_to_table_dict(tk.quarterly_financials),
            "balance_sheet": _df_to_table_dict(tk.balance_sheet),
            "cashflow": _df_to_table_dict(tk.cashflow),
            "peers": peers,
        }
        ts_ist = terminal_cache.set(cache_key, bundle, ttl_seconds=ttl_seconds)
        return bundle, False, ts_ist
    except Exception as exc:  # noqa: BLE001
        stale = terminal_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return stale.data, True, stale.fetched_at_ist
        return {"ratios": {"symbol": sym}, "error": str(exc)}, False, "Unavailable"


def fetch_screener_data(
    universe_items: List[Dict[str, str]],
    include_fundamentals: bool = True,
    ttl_seconds: int = 900,
) -> Tuple[List[Dict[str, Any]], bool, str]:
    """
    Fetch batched technical + optional fundamental metrics for Nifty 500 screener.

    Downloads 1y daily bars in chunks of 50 to avoid yfinance rate limits, then
    optionally enriches valuation/profitability ratios from cached Ticker.info.
    """
    tickers = [u["yf_ticker"] for u in universe_items]
    if not tickers:
        return [], False, "No tickers"

    meta_map = {u["yf_ticker"]: u for u in universe_items}
    sig = hashlib.sha256(",".join(sorted(tickers)).encode("utf-8")).hexdigest()[:16]
    cache_key = f"screener::{len(tickers)}::{sig}::{int(include_fundamentals)}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    rows: List[Dict[str, Any]] = []
    chunk_size = 50
    chunks = [tickers[i : i + chunk_size] for i in range(0, len(tickers), chunk_size)]

    def _download_chunk(chunk: List[str]) -> List[Dict[str, Any]]:
        chunk_rows: List[Dict[str, Any]] = []
        try:
            df = yf.download(
                tickers=chunk,
                period="1y",
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=True,
                timeout=25,
            )
            if df is None or df.empty:
                return chunk_rows
            is_multi = isinstance(df.columns, pd.MultiIndex)
            for sym in chunk:
                sub = df[sym] if (is_multi and sym in df.columns.get_level_values(0)) else (df if not is_multi else None)
                if sub is None or sub.empty or "Close" not in sub.columns:
                    continue
                closes = sub["Close"].dropna()
                if len(closes) < 5:
                    continue
                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                pct_chg = (price - prev) / prev * 100.0 if prev else 0.0
                high_52w = float(sub["High"].dropna().max()) if "High" in sub.columns and not sub["High"].dropna().empty else float(closes.max())
                pct_from_high = ((price - high_52w) / high_52w * 100.0) if high_52w else 0.0

                vols = sub["Volume"].dropna() if "Volume" in sub.columns else pd.Series(dtype=float)
                cur_vol = float(vols.iloc[-1]) if not vols.empty else 0.0
                avg_vol_20 = float(vols.tail(20).mean()) if len(vols) >= 5 else cur_vol
                vol_spike = (cur_vol / avg_vol_20) if avg_vol_20 > 0 else 1.0

                rsi_series = compute_rsi(closes, 14).dropna()
                rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

                u = meta_map[sym]
                chunk_rows.append(
                    {
                        "symbol": u["symbol"],
                        "yf_ticker": sym,
                        "name": u["name"],
                        "sector": u["sector"],
                        "price": round(price, 2),
                        "pct_change": round(pct_chg, 2),
                        "high_52w": round(high_52w, 2),
                        "pct_from_52w_high": round(pct_from_high, 2),
                        "volume": int(cur_vol),
                        "vol_spike_x": round(vol_spike, 2),
                        "rsi_14": round(rsi_val, 1) if rsi_val is not None else None,
                        "market_cap_cr": None,
                        "pe": None,
                        "pb": None,
                        "roe_pct": None,
                        "div_yield_pct": None,
                    }
                )
        except Exception:
            pass
        return chunk_rows

    with ThreadPoolExecutor(max_workers=min(3, len(chunks))) as pool:
        futs = [pool.submit(_download_chunk, c) for c in chunks]
        for fut in as_completed(futs):
            rows.extend(fut.result())

    if include_fundamentals and rows:
        def _enrich(row: Dict[str, Any]) -> None:
            r = fetch_stock_ratios(row["yf_ticker"], ttl_seconds=3600)
            mcap = r.get("market_cap")
            row["market_cap_cr"] = round(mcap / 1e7, 1) if mcap else None
            row["pe"] = round(r["pe"], 2) if r.get("pe") is not None else None
            row["pb"] = round(r["pb"], 2) if r.get("pb") is not None else None
            row["roe_pct"] = r.get("roe_pct")
            row["div_yield_pct"] = r.get("div_yield_pct")

        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = [pool.submit(_enrich, r) for r in rows]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception:
                    continue

    if rows:
        ts_ist = terminal_cache.set(cache_key, rows, ttl_seconds=ttl_seconds)
        return rows, False, ts_ist

    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None:
        return stale.data, True, stale.fetched_at_ist
    return [], False, "Unavailable"


def fetch_nifty50_heatmap_data(ttl_seconds: int = 180) -> Tuple[List[Dict[str, Any]], bool, str]:
    """Fetch Nifty 50 quotes annotated with sector for treemap heatmap."""
    items = [(t.replace(".NS", ""), t) for t in NIFTY_50_TICKERS]
    rows, is_stale, ts_ist = fetch_yfinance_quotes(
        items=items,
        cache_key="nifty50_heatmap_quotes",
        ttl_seconds=ttl_seconds,
    )
    for row in rows:
        row["sector"] = NIFTY_50_SECTOR_MAP.get(row["symbol"], "Other")
        # Use traded turnover proxy (price * volume) for visual tile sizing when market cap isn't fetched
        vol = float(row.get("volume") or 100_000)
        row["weight_proxy"] = max(1.0, float(row.get("price") or 1.0) * vol)
    return rows, is_stale, ts_ist


def fetch_usd_inr_frankfurter(ttl_seconds: int = 1800) -> Optional[Dict[str, Any]]:
    """Fallback USD/INR reference rate from the free Frankfurter API (ECB daily rate)."""
    cache_key = "frankfurter_usd_inr"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data

    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "USD", "to": "INR"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        rate = float(payload["rates"]["INR"])
        result = {
            "name": "USD / INR (ECB Ref)",
            "symbol": "USD/INR",
            "price": round(rate, 4),
            "prev_close": round(rate, 4),
            "change": 0.0,
            "pct_change": 0.0,
            "date": payload.get("date", ""),
        }
        terminal_cache.set(cache_key, result, ttl_seconds=ttl_seconds)
        terminal_cache.record_source_status(
            source_name="Frankfurter FX API",
            status="OK",
            delay_note="Daily ECB reference rate (free, no key)",
            success=True,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        terminal_cache.record_source_status(
            source_name="Frankfurter FX API",
            status="ERROR",
            delay_note="Daily ECB reference rate (free, no key)",
            success=False,
            error_msg=str(exc),
        )
        stale = terminal_cache.get(cache_key, allow_stale=True)
        return stale.data if stale else None


def fetch_nifty50_breadth_fallback(ttl_seconds: int = 300) -> Tuple[Dict[str, Any], bool, str]:
    """Compute Nifty 50 advance/decline breadth and top 5 gainers/losers via yfinance."""
    items = [(t.replace(".NS", ""), t) for t in NIFTY_50_TICKERS]
    rows, is_stale, ts_ist = fetch_yfinance_quotes(
        items=items,
        cache_key="nifty50_yfinance_breadth",
        ttl_seconds=ttl_seconds,
    )
    if not rows:
        return {"advances": 0, "declines": 0, "unchanged": 0, "gainers": [], "losers": [], "source": "Unavailable"}, is_stale, ts_ist

    advances = sum(1 for r in rows if r["pct_change"] > 0)
    declines = sum(1 for r in rows if r["pct_change"] < 0)
    unchanged = sum(1 for r in rows if r["pct_change"] == 0)

    sorted_rows = sorted(rows, key=lambda r: r["pct_change"], reverse=True)
    gainers = sorted_rows[:5]
    losers = sorted(rows, key=lambda r: r["pct_change"])[:5]

    return (
        {
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "gainers": gainers,
            "losers": losers,
            "source": "Yahoo Finance fallback (~15 min delayed, Nifty 50)",
        },
        is_stale,
        ts_ist,
    )
