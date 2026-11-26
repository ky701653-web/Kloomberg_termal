"""Macro (FRED/World Bank/RBI), RSS News + VADER, AMFI/mfapi Mutual Funds, CoinGecko & FX fetchers."""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from utils.cache import terminal_cache
from utils.secrets import get_secret

USER_AGENT = "IndiaTerminal/0.2 (Personal Open-Source Financial Research App)"
_SENTIMENT = SentimentIntensityAnalyzer()

RSS_FEEDS: List[Tuple[str, str]] = [
    ("Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Moneycontrol", "https://www.moneycontrol.com/rss/marketreports.xml"),
    ("LiveMint", "https://www.livemint.com/rss/markets"),
    ("Business Standard", "https://www.business-standard.com/rss/markets-106.rss"),
]

# Reference RBI / MOSPI macro indicators (updated with live FRED / World Bank / yfinance where available)
RBI_MOSPI_REFERENCE: List[Dict[str, str]] = [
    {
        "Indicator": "RBI Policy Repo Rate",
        "Value": "6.50% (check RBI MPC)",
        "Source": "Reserve Bank of India (RBI)",
        "Frequency": "Bi-monthly MPC",
    },
    {
        "Indicator": "India 10Y G-Sec Benchmark",
        "Value": "~6.80% - 7.05% range",
        "Source": "RBI / CCIL",
        "Frequency": "Daily",
    },
    {
        "Indicator": "MOSPI CPI / IIP Releases",
        "Value": "Monthly Official Release",
        "Source": "MOSPI (mospi.gov.in)",
        "Frequency": "Monthly",
    },
]


def _score_sentiment(text: str) -> Tuple[float, str]:
    scores = _SENTIMENT.polarity_scores(text or "")
    compound = round(float(scores.get("compound", 0.0)), 3)
    if compound >= 0.15:
        label = "Bullish"
    elif compound <= -0.15:
        label = "Bearish"
    else:
        label = "Neutral"
    return compound, label


def fetch_news_feed(
    query: Optional[str] = None,
    ttl_seconds: int = 600,
) -> Tuple[List[Dict[str, Any]], bool, str]:
    """Fetch Indian market RSS headlines + Google News query feed with VADER sentiment."""
    clean_q = (query or "").strip()
    cache_key = f"news_feed::{clean_q.upper() or 'ALL'}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    feeds = list(RSS_FEEDS)
    gnews_query = f"{clean_q} India stock market NSE" if clean_q else "Indian stock market Nifty Sensex NSE"
    feeds.append(
        (
            "Google News India",
            f"https://news.google.com/rss/search?q={quote_plus(gnews_query)}&hl=en-IN&gl=IN&ceid=IN:en",
        )
    )

    articles: List[Dict[str, Any]] = []
    errors: List[str] = []

    def _fetch_single_feed(source_name: str, url: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        local_items: List[Dict[str, Any]] = []
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=8)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:20]:
                title = str(entry.get("title", "")).strip()
                summary = str(entry.get("summary", "")).strip()
                link = str(entry.get("link", "")).strip()
                published = str(entry.get("published", "")).strip()
                if not title:
                    continue
                if clean_q and source_name != "Google News India":
                    haystack = f"{title} {summary}".lower()
                    q_base = clean_q.replace(".NS", "").replace(".BO", "").lower()
                    if q_base not in haystack:
                        continue
                compound, label = _score_sentiment(f"{title}. {summary[:200]}")
                local_items.append(
                    {
                        "source": source_name,
                        "title": title,
                        "link": link,
                        "published": published,
                        "sentiment_score": compound,
                        "sentiment": label,
                    }
                )
            return local_items, None
        except Exception as exc:  # noqa: BLE001
            return [], f"{source_name}: {exc}"

    with ThreadPoolExecutor(max_workers=len(feeds)) as pool:
        futs = [pool.submit(_fetch_single_feed, src, u) for src, u in feeds]
        for fut in as_completed(futs):
            items, err = fut.result()
            articles.extend(items)
            if err:
                errors.append(err)

    # Deduplicate by title
    seen = set()
    unique_articles = []
    for art in articles:
        key = art["title"].lower()
        if key not in seen:
            seen.add(key)
            unique_articles.append(art)

    if unique_articles:
        ts_ist = terminal_cache.set(cache_key, unique_articles, ttl_seconds=ttl_seconds)
        terminal_cache.record_source_status(
            source_name="Indian Financial RSS + VADER",
            status="OK" if not errors else "PARTIAL",
            delay_note="Live RSS aggregation with VADER sentiment",
            success=True,
            error_msg="; ".join(errors[:2]),
        )
        return unique_articles, False, ts_ist

    terminal_cache.record_source_status(
        source_name="Indian Financial RSS + VADER",
        status="ERROR",
        delay_note="Live RSS aggregation",
        success=False,
        error_msg="; ".join(errors[:2]) or "No matching articles",
    )
    stale = terminal_cache.get(cache_key, allow_stale=True)
    if stale is not None:
        return stale.data, True, stale.fetched_at_ist
    return [], False, "Unavailable"


def _fetch_world_bank_series(indicator: str, label: str) -> Optional[Dict[str, Any]]:
    url = f"https://api.worldbank.org/v2/country/IND/indicator/{indicator}"
    resp = requests.get(url, params={"format": "json", "per_page": 10}, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return None
    points = [
        {"date": str(row["date"]), "value": float(row["value"])}
        for row in payload[1]
        if row.get("value") is not None
    ]
    if not points:
        return None
    points.sort(key=lambda p: p["date"])
    return {"label": label, "latest": points[-1], "history": points}


def fetch_macro_dashboard(ttl_seconds: int = 3600) -> Tuple[Dict[str, Any], bool, str]:
    """Fetch India & Global macro series from FRED (if key set), World Bank, and Yahoo Finance."""
    cache_key = "macro_dashboard_bundle"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    fred_key = get_secret("FRED_API_KEY")
    fred_series: Dict[str, Any] = {}
    fred_error = ""

    if fred_key:
        try:
            from fredapi import Fred

            fred = Fred(api_key=fred_key)
            series_map = {
                "FEDFUNDS": "US Fed Funds Rate (%)",
                "DGS10": "US 10Y Treasury Yield (%)",
                "INDIRLTLT01STM": "India 10Y Long-Term Rate (%)",
                "INDCPIALLMINMEI": "India CPI Index (2015=100)",
                "DEXINUS": "USD / INR (FRED)",
            }
            for sid, label in series_map.items():
                try:
                    s = fred.get_series(sid).dropna().tail(36)
                    if not s.empty:
                        pts = [{"date": idx.strftime("%Y-%m-%d"), "value": round(float(v), 3)} for idx, v in s.items()]
                        fred_series[sid] = {"label": label, "latest": pts[-1], "history": pts}
                except Exception:
                    continue
            terminal_cache.record_source_status(
                source_name="FRED Macro API",
                status="OK" if fred_series else "ERROR",
                delay_note="Official St. Louis Fed macro series",
                success=bool(fred_series),
            )
        except Exception as exc:  # noqa: BLE001
            fred_error = str(exc)
            terminal_cache.record_source_status(
                source_name="FRED Macro API",
                status="ERROR",
                delay_note="Official St. Louis Fed macro series",
                success=False,
                error_msg=fred_error,
            )
    else:
        terminal_cache.record_source_status(
            source_name="FRED Macro API",
            status="KEY NOT SET",
            delay_note="Optional free FRED_API_KEY enables live US/India FRED series",
            success=False,
            error_msg="Add FRED_API_KEY in .env or Streamlit secrets",
        )

    wb_series: Dict[str, Any] = {}
    wb_specs = {
        "NY.GDP.MKTP.KD.ZG": "India GDP Growth (Annual %)",
        "FP.CPI.TOTL.ZG": "India CPI Inflation (Annual %)",
        "FI.RES.TOTL.CD": "India Total Forex Reserves (USD)",
    }
    for code, label in wb_specs.items():
        try:
            res = _fetch_world_bank_series(code, label)
            if res:
                wb_series[code] = res
        except Exception:
            continue

    if wb_series:
        terminal_cache.record_source_status(
            source_name="World Bank Macro API",
            status="OK",
            delay_note="Annual India macro indicators (free, no key)",
            success=True,
        )

    bundle = {
        "fred_enabled": bool(fred_key),
        "fred_series": fred_series,
        "fred_error": fred_error,
        "world_bank": wb_series,
        "reference": RBI_MOSPI_REFERENCE,
    }
    ts_ist = terminal_cache.set(cache_key, bundle, ttl_seconds=ttl_seconds)
    return bundle, False, ts_ist


def search_mutual_funds(query: str = "Nifty 50", ttl_seconds: int = 3600) -> Tuple[List[Dict[str, str]], str]:
    """Search Indian mutual fund schemes via mfapi.in (backed by AMFI scheme codes)."""
    clean_q = query.strip() or "Nifty 50"
    cache_key = f"mf_search::{clean_q.lower()}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, cached.fetched_at_ist

    try:
        resp = requests.get(
            "https://api.mfapi.in/mf/search",
            params={"q": clean_q},
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        )
        resp.raise_for_status()
        items = resp.json()
        results = [
            {"schemeCode": str(it["schemeCode"]), "schemeName": str(it["schemeName"])}
            for it in (items or [])[:60]
            if it.get("schemeCode") and it.get("schemeName")
        ]
        ts_ist = terminal_cache.set(cache_key, results, ttl_seconds=ttl_seconds)
        terminal_cache.record_source_status(
            source_name="AMFI / mfapi.in Mutual Funds",
            status="OK",
            delay_note="Daily end-of-day AMFI NAVs",
            success=True,
        )
        return results, ts_ist
    except Exception as exc:  # noqa: BLE001
        terminal_cache.record_source_status(
            source_name="AMFI / mfapi.in Mutual Funds",
            status="ERROR",
            delay_note="Daily end-of-day AMFI NAVs",
            success=False,
            error_msg=str(exc),
        )
        stale = terminal_cache.get(cache_key, allow_stale=True)
        return (stale.data, stale.fetched_at_ist) if stale else ([], "Unavailable")


def fetch_mf_nav_history(scheme_code: str, ttl_seconds: int = 3600) -> Tuple[Dict[str, Any], bool, str]:
    """Fetch scheme metadata, historical NAV curve, and trailing CAGR from mfapi.in."""
    code = str(scheme_code).strip()
    cache_key = f"mf_nav::{code}"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    try:
        resp = requests.get(
            f"https://api.mfapi.in/mf/{code}",
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        meta = payload.get("meta", {})
        raw_data = payload.get("data", [])

        rows = []
        for entry in raw_data:
            try:
                dt = datetime.strptime(entry["date"], "%d-%m-%Y").date()
                nav = float(entry["nav"])
                if math.isfinite(nav) and nav > 0:
                    rows.append({"date": dt.isoformat(), "nav": nav})
            except Exception:
                continue

        rows.sort(key=lambda r: r["date"])
        cagr = {}
        if rows:
            df = pd.DataFrame(rows)
            df["dt"] = pd.to_datetime(df["date"])
            latest_dt = df["dt"].iloc[-1]
            latest_nav = float(df["nav"].iloc[-1])
            for label, years in [("1Y", 1), ("3Y", 3), ("5Y", 5)]:
                target_dt = latest_dt - pd.DateOffset(years=years)
                sub = df[df["dt"] <= target_dt]
                if not sub.empty:
                    past_nav = float(sub["nav"].iloc[-1])
                    if past_nav > 0:
                        cagr[label] = round(((latest_nav / past_nav) ** (1.0 / years) - 1.0) * 100.0, 2)

        bundle = {
            "meta": meta,
            "latest_nav": rows[-1]["nav"] if rows else None,
            "latest_date": rows[-1]["date"] if rows else "N/A",
            "cagr": cagr,
            "history": rows[-1800:],  # Keep up to ~7 years of daily NAVs in cache
        }
        ts_ist = terminal_cache.set(cache_key, bundle, ttl_seconds=ttl_seconds)
        return bundle, False, ts_ist
    except Exception as exc:  # noqa: BLE001
        stale = terminal_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return stale.data, True, stale.fetched_at_ist
        return {"meta": {}, "error": str(exc), "history": [], "cagr": {}}, False, "Unavailable"


def fetch_crypto_inr(ttl_seconds: int = 180) -> Tuple[List[Dict[str, Any]], bool, str]:
    """Fetch top cryptocurrencies quoted in INR from CoinGecko free API."""
    cache_key = "coingecko_top_inr"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "inr",
                "order": "market_cap_desc",
                "per_page": 20,
                "page": 1,
                "sparkline": "true",
                "price_change_percentage": "24h,7d",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        )
        resp.raise_for_status()
        raw = resp.json()
        rows = [
            {
                "rank": item.get("market_cap_rank"),
                "name": item.get("name"),
                "symbol": str(item.get("symbol", "")).upper(),
                "price_inr": item.get("current_price"),
                "chg_24h": item.get("price_change_percentage_24h"),
                "chg_7d": item.get("price_change_percentage_7d_in_currency"),
                "market_cap_inr": item.get("market_cap"),
                "volume_24h_inr": item.get("total_volume"),
                "sparkline": (item.get("sparkline_in_7d") or {}).get("price", [])[-48:],
            }
            for item in (raw or [])
        ]
        ts_ist = terminal_cache.set(cache_key, rows, ttl_seconds=ttl_seconds)
        terminal_cache.record_source_status(
            source_name="CoinGecko Crypto API",
            status="OK",
            delay_note="Near real-time INR crypto prices (free, rate-limited)",
            success=True,
        )
        return rows, False, ts_ist
    except Exception as exc:  # noqa: BLE001
        terminal_cache.record_source_status(
            source_name="CoinGecko Crypto API",
            status="ERROR",
            delay_note="Near real-time INR crypto prices",
            success=False,
            error_msg=str(exc),
        )
        stale = terminal_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return stale.data, True, stale.fetched_at_ist
        return [], False, "Unavailable"


def fetch_fx_inr(ttl_seconds: int = 1800) -> Tuple[List[Dict[str, Any]], bool, str]:
    """Fetch major global currency rates expressed in INR via Frankfurter ECB API."""
    cache_key = "frankfurter_fx_inr_cross"
    cached = terminal_cache.get(cache_key, allow_stale=False)
    if cached is not None:
        return cached.data, False, cached.fetched_at_ist

    currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "SGD", "CHF", "CAD"]
    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "INR", "to": ",".join(currencies)},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        rates = payload.get("rates", {})
        date_str = str(payload.get("date", ""))
        rows = []
        for cur in currencies:
            r = rates.get(cur)
            if r and float(r) > 0:
                inr_per_unit = 1.0 / float(r)
                rows.append(
                    {
                        "pair": f"{cur} / INR",
                        "currency": cur,
                        "inr_per_unit": round(inr_per_unit, 4),
                        "units_per_100_inr": round(float(r) * 100.0, 4),
                        "date": date_str,
                    }
                )
        ts_ist = terminal_cache.set(cache_key, rows, ttl_seconds=ttl_seconds)
        terminal_cache.record_source_status(
            source_name="Frankfurter FX API",
            status="OK",
            delay_note="Daily ECB reference rate (free, no key)",
            success=True,
        )
        return rows, False, ts_ist
    except Exception as exc:  # noqa: BLE001
        terminal_cache.record_source_status(
            source_name="Frankfurter FX API",
            status="ERROR",
            delay_note="Daily ECB reference rate",
            success=False,
            error_msg=str(exc),
        )
        stale = terminal_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return stale.data, True, stale.fetched_at_ist
        return [], False, "Unavailable"
