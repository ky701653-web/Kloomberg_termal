"""SQLite-backed caching and data-source telemetry for the terminal."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from utils.market_hours import now_ist

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "cache" / "terminal_cache.db"


@dataclass(frozen=True)
class CacheResult:
    """Wrapper returned by SQLite cache lookups."""

    data: Any
    fetched_at_ist: str
    is_stale: bool


class TerminalCache:
    """Lightweight SQLite cache with TTL, stale fallback, and source status logs."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a SQLite connection, commit/rollback its transaction, and close it."""
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fetched_epoch REAL NOT NULL,
                    fetched_at_ist TEXT NOT NULL,
                    ttl_seconds INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_status (
                    source_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_success_ist TEXT,
                    last_attempt_ist TEXT NOT NULL,
                    delay_note TEXT NOT NULL,
                    last_error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker TEXT PRIMARY KEY,
                    added_epoch REAL NOT NULL,
                    added_at_ist TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_screens (
                    name TEXT PRIMARY KEY,
                    filters_json TEXT NOT NULL,
                    created_at_ist TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    qty REAL NOT NULL,
                    buy_price REAL NOT NULL,
                    buy_date TEXT NOT NULL,
                    notes TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at_ist TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id INTEGER,
                    symbol TEXT NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at_ist TEXT NOT NULL,
                    channel TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    meta_key TEXT PRIMARY KEY,
                    meta_value TEXT NOT NULL
                )
                """
            )

    def get(self, key: str, allow_stale: bool = False) -> Optional[CacheResult]:
        """Fetch cached JSON payload by key; optionally return expired data as fallback."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT payload, fetched_epoch, fetched_at_ist, ttl_seconds
                FROM kv_cache
                WHERE cache_key = ?
                """,
                (key,),
            ).fetchone()

        if row is None:
            return None

        age = time.time() - float(row["fetched_epoch"])
        is_stale = age > int(row["ttl_seconds"])
        if is_stale and not allow_stale:
            return None

        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            return None

        return CacheResult(
            data=payload,
            fetched_at_ist=str(row["fetched_at_ist"]),
            is_stale=is_stale,
        )

    def set(self, key: str, data: Any, ttl_seconds: int = 300) -> str:
        """Persist JSON-serializable payload with a TTL in seconds."""
        ts_ist = now_ist().strftime("%d %b %Y, %I:%M:%S %p IST")
        serialized = json.dumps(data, default=str)
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO kv_cache (cache_key, payload, fetched_epoch, fetched_at_ist, ttl_seconds)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    fetched_epoch = excluded.fetched_epoch,
                    fetched_at_ist = excluded.fetched_at_ist,
                    ttl_seconds = excluded.ttl_seconds
                """,
                (key, serialized, time.time(), ts_ist, int(ttl_seconds)),
            )
        return ts_ist

    def record_source_status(
        self,
        source_name: str,
        status: str,
        delay_note: str,
        success: bool,
        error_msg: str = "",
    ) -> None:
        """Log the health, last fetch time, delay note, and error of a data source."""
        ts_ist = now_ist().strftime("%d %b %Y, %I:%M:%S %p IST")
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT last_success_ist FROM source_status WHERE source_name = ?",
                (source_name,),
            ).fetchone()
            last_success = ts_ist if success else (existing["last_success_ist"] if existing else "Never")
            conn.execute(
                """
                INSERT INTO source_status (
                    source_name, status, last_success_ist, last_attempt_ist, delay_note, last_error
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    status = excluded.status,
                    last_success_ist = excluded.last_success_ist,
                    last_attempt_ist = excluded.last_attempt_ist,
                    delay_note = excluded.delay_note,
                    last_error = excluded.last_error
                """,
                (source_name, status, last_success, ts_ist, delay_note, error_msg),
            )

    def get_all_source_statuses(self) -> List[Dict[str, str]]:
        """Return status records for all tracked data sources."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT source_name, status, last_success_ist, last_attempt_ist, delay_note, last_error
                FROM source_status
                ORDER BY source_name ASC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_kv_cache(self) -> None:
        """Delete all cached API responses while keeping schema intact."""
        with self._connection() as conn:
            conn.execute("DELETE FROM kv_cache")

    # ------------------------------------------------------------------
    # Watchlist persistence (Stage 2)
    # ------------------------------------------------------------------
    def get_watchlist(self, default_tickers: Optional[List[str]] = None) -> List[str]:
        """Return persisted watchlist tickers, seeding defaults once on first run."""
        with self._connection() as conn:
            seeded = conn.execute(
                "SELECT meta_value FROM app_meta WHERE meta_key = 'watchlist_seeded'"
            ).fetchone()
            if seeded is None and default_tickers:
                ts_ist = now_ist().strftime("%d %b %Y, %I:%M:%S %p IST")
                now_ep = time.time()
                for idx, sym in enumerate(default_tickers):
                    conn.execute(
                        "INSERT OR IGNORE INTO watchlist (ticker, added_epoch, added_at_ist) VALUES (?, ?, ?)",
                        (sym, now_ep + idx * 0.001, ts_ist),
                    )
                conn.execute(
                    "INSERT OR REPLACE INTO app_meta (meta_key, meta_value) VALUES ('watchlist_seeded', '1')"
                )
            rows = conn.execute("SELECT ticker FROM watchlist ORDER BY added_epoch ASC").fetchall()
        return [str(r["ticker"]) for r in rows]

    def add_watchlist_ticker(self, ticker: str) -> None:
        """Add a normalized ticker to the persisted watchlist."""
        ts_ist = now_ist().strftime("%d %b %Y, %I:%M:%S %p IST")
        with self._connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (ticker, added_epoch, added_at_ist) VALUES (?, ?, ?)",
                (ticker, time.time(), ts_ist),
            )
            conn.execute(
                "INSERT OR REPLACE INTO app_meta (meta_key, meta_value) VALUES ('watchlist_seeded', '1')"
            )

    def remove_watchlist_ticker(self, ticker: str) -> None:
        """Remove a ticker from the persisted watchlist."""
        with self._connection() as conn:
            conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))

    # ------------------------------------------------------------------
    # Screener saved screens persistence (Stage 4)
    # ------------------------------------------------------------------
    def save_screen(self, name: str, filters: Dict[str, Any]) -> None:
        """Save or update a named screener filter preset."""
        ts_ist = now_ist().strftime("%d %b %Y, %I:%M:%S %p IST")
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO saved_screens (name, filters_json, created_at_ist)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    filters_json = excluded.filters_json,
                    created_at_ist = excluded.created_at_ist
                """,
                (name.strip(), json.dumps(filters), ts_ist),
            )

    def get_saved_screens(self) -> Dict[str, Dict[str, Any]]:
        """Return mapping of saved screen name -> filter dict."""
        with self._connection() as conn:
            rows = conn.execute("SELECT name, filters_json FROM saved_screens ORDER BY name ASC").fetchall()
        out: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            try:
                out[str(r["name"])] = json.loads(r["filters_json"])
            except json.JSONDecodeError:
                continue
        return out

    def delete_screen(self, name: str) -> None:
        """Delete a saved screener preset."""
        with self._connection() as conn:
            conn.execute("DELETE FROM saved_screens WHERE name = ?", (name,))

    # ------------------------------------------------------------------
    # Portfolio holdings persistence (Stage 7)
    # ------------------------------------------------------------------
    def add_holding(
        self, symbol: str, qty: float, buy_price: float, buy_date: str, notes: str = ""
    ) -> int:
        """Insert a portfolio lot and return its row id."""
        with self._connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO portfolio_holdings (symbol, qty, buy_price, buy_date, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (symbol.strip().upper(), float(qty), float(buy_price), buy_date.strip(), notes.strip()),
            )
            return int(cur.lastrowid or 0)

    def get_holdings(self) -> List[Dict[str, Any]]:
        """Fetch all saved portfolio holdings ordered by buy_date ascending."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, symbol, qty, buy_price, buy_date, notes FROM portfolio_holdings ORDER BY buy_date ASC, id ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_holding(self, holding_id: int) -> None:
        """Delete a portfolio lot by id."""
        with self._connection() as conn:
            conn.execute("DELETE FROM portfolio_holdings WHERE id = ?", (int(holding_id),))

    def clear_holdings(self) -> None:
        """Remove all portfolio lots."""
        with self._connection() as conn:
            conn.execute("DELETE FROM portfolio_holdings")

    # ------------------------------------------------------------------
    # Alerts persistence (Stage 7)
    # ------------------------------------------------------------------
    def add_alert_rule(self, symbol: str, condition: str, threshold: float) -> int:
        """Create a new alert rule and return its id."""
        ts_ist = now_ist().strftime("%d %b %Y, %I:%M:%S %p IST")
        with self._connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO alert_rules (symbol, condition, threshold, enabled, created_at_ist)
                VALUES (?, ?, ?, 1, ?)
                """,
                (symbol.strip().upper(), condition, float(threshold), ts_ist),
            )
            return int(cur.lastrowid or 0)

    def get_alert_rules(self) -> List[Dict[str, Any]]:
        """Fetch all configured alert rules."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, symbol, condition, threshold, enabled, created_at_ist FROM alert_rules ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def toggle_alert_rule(self, rule_id: int, enabled: bool) -> None:
        """Enable or disable an alert rule."""
        with self._connection() as conn:
            conn.execute(
                "UPDATE alert_rules SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, int(rule_id)),
            )

    def delete_alert_rule(self, rule_id: int) -> None:
        """Delete an alert rule."""
        with self._connection() as conn:
            conn.execute("DELETE FROM alert_rules WHERE id = ?", (int(rule_id),))

    def log_alert_trigger(self, rule_id: Optional[int], symbol: str, message: str, channel: str) -> None:
        """Record a triggered alert event."""
        ts_ist = now_ist().strftime("%d %b %Y, %I:%M:%S %p IST")
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO alert_history (rule_id, symbol, message, triggered_at_ist, channel)
                VALUES (?, ?, ?, ?, ?)
                """,
                (rule_id, symbol, message, ts_ist, channel),
            )

    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent triggered alerts."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, rule_id, symbol, message, triggered_at_ist, channel FROM alert_history ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]


# Shared default cache instance
terminal_cache = TerminalCache()
