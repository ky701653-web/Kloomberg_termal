"""Unit tests for Stage 1: formatting, IST market hours, SQLite cache, and command bar."""

from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from modules.command_bar import normalize_indian_ticker, parse_command
from utils.cache import TerminalCache
from utils.formatting import format_indian_commas, format_inr, format_pct
from utils.market_hours import IST, get_market_status


class TestFormatting(unittest.TestCase):
    def test_indian_commas(self) -> None:
        self.assertEqual(format_indian_commas(1234567.89), "12,34,567.89")
        self.assertEqual(format_indian_commas(950.5), "950.50")
        self.assertEqual(format_indian_commas(-100000), "-1,00,000.00")

    def test_format_inr_compact_lakh_crore(self) -> None:
        self.assertEqual(format_inr(12.4e12, compact=True), "₹12.40 lakh crore")
        self.assertEqual(format_inr(450e7, compact=True), "₹450.00 Cr")
        self.assertEqual(format_inr(2.5e5, compact=True), "₹2.50 L")
        self.assertEqual(format_inr(1542.5, compact=False), "₹1,542.50")
        self.assertEqual(format_inr(None), "N/A")

    def test_format_pct(self) -> None:
        self.assertEqual(format_pct(1.234), "+1.23%")
        self.assertEqual(format_pct(-0.5), "-0.50%")
        self.assertEqual(format_pct(0.0), "0.00%")


class TestMarketHours(unittest.TestCase):
    def test_open_during_nse_hours(self) -> None:
        # Thursday 11:00 AM IST (non-holiday)
        dt = datetime(2026, 11, 26, 11, 0, tzinfo=IST)
        status = get_market_status(dt)
        self.assertEqual(status.state, "OPEN")
        self.assertTrue(status.is_open)

    def test_preopen_session(self) -> None:
        dt = datetime(2026, 11, 26, 9, 5, tzinfo=IST)
        status = get_market_status(dt)
        self.assertEqual(status.state, "PRE-OPEN")

    def test_closed_after_hours(self) -> None:
        dt = datetime(2026, 11, 26, 16, 0, tzinfo=IST)
        status = get_market_status(dt)
        self.assertEqual(status.state, "CLOSED")
        self.assertIsNotNone(status.next_open_ist)

    def test_closed_on_nse_holiday(self) -> None:
        # Republic Day 2026 (Monday)
        dt = datetime(2026, 1, 26, 11, 0, tzinfo=IST)
        status = get_market_status(dt)
        self.assertEqual(status.state, "CLOSED")
        self.assertIn("Republic Day", status.reason)

    def test_closed_on_weekend(self) -> None:
        # Saturday
        dt = datetime(2026, 11, 28, 11, 0, tzinfo=IST)
        status = get_market_status(dt)
        self.assertEqual(status.state, "CLOSED")
        self.assertIn("Weekend", status.reason)


class TestSQLiteCache(unittest.TestCase):
    def test_set_get_and_stale_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TerminalCache(Path(tmpdir) / "test.db")
            cache.set("nifty", {"price": 24500.0}, ttl_seconds=1)
            fresh = cache.get("nifty", allow_stale=False)
            self.assertIsNotNone(fresh)
            assert fresh is not None
            self.assertFalse(fresh.is_stale)
            self.assertEqual(fresh.data["price"], 24500.0)

            time.sleep(1.1)
            self.assertIsNone(cache.get("nifty", allow_stale=False))
            stale = cache.get("nifty", allow_stale=True)
            self.assertIsNotNone(stale)
            assert stale is not None
            self.assertTrue(stale.is_stale)

    def test_source_status_logging(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TerminalCache(Path(tmpdir) / "status.db")
            cache.record_source_status("Yahoo Finance", "OK", "~15m delayed", success=True)
            statuses = cache.get_all_source_statuses()
            self.assertEqual(len(statuses), 1)
            self.assertEqual(statuses[0]["status"], "OK")


class TestCommandBar(unittest.TestCase):
    def test_normalize_ticker(self) -> None:
        self.assertEqual(normalize_indian_ticker("reliance"), "RELIANCE.NS")
        self.assertEqual(normalize_indian_ticker("TCS.BO"), "TCS.BO")
        self.assertEqual(normalize_indian_ticker("NIFTY"), "^NSEI")

    def test_command_routing(self) -> None:
        cmd1 = parse_command("RELIANCE GO")
        self.assertEqual(cmd1.target_module, "Home / Market Overview")
        self.assertEqual(cmd1.ticker, "RELIANCE.NS")

        cmd2 = parse_command("TCS FA")
        self.assertEqual(cmd2.target_module, "Fundamentals")
        self.assertEqual(cmd2.ticker, "TCS.NS")

        cmd3 = parse_command("INFY GP")
        self.assertEqual(cmd3.target_module, "Charting")
        self.assertEqual(cmd3.ticker, "INFY.NS")

        cmd4 = parse_command("NIFTY OPT")
        self.assertEqual(cmd4.target_module, "F&O / Options")
        self.assertEqual(cmd4.ticker, "^NSEI")

        cmd5 = parse_command("NEWS HDFCBANK")
        self.assertEqual(cmd5.target_module, "News Feed")
        self.assertEqual(cmd5.ticker, "HDFCBANK.NS")

        cmd_help = parse_command("HELP")
        self.assertTrue(cmd_help.show_help)


if __name__ == "__main__":
    unittest.main()
