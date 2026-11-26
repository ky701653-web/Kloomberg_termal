"""Unit tests for backtesting, broker parsers, AI market summary, security helpers, and new routes."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from data.broker_data import (
    parse_angel_quote_response,
    parse_kite_quote_response,
    parse_upstox_quote_response,
    to_kite_instrument,
)
from modules.command_bar import parse_command
from utils.backtester import run_ma_crossover_backtest, run_rsi_backtest
from utils.market_summary import build_deterministic_market_summary
from utils.ui import sanitize_http_url


class TestBacktestingAndEnhancements(unittest.TestCase):
    def setUp(self) -> None:
        n = 120
        idx = pd.date_range("2025-01-01", periods=n, freq="B")
        wave = 100.0 + np.cumsum(np.sin(np.arange(n) * 0.25) * 1.8 + 0.25)
        self.df = pd.DataFrame(
            {
                "Open": wave - 0.5,
                "High": wave + 1.2,
                "Low": wave - 1.2,
                "Close": wave,
                "Volume": np.full(n, 50000.0),
            },
            index=idx,
        )

    def test_ma_crossover_backtest(self) -> None:
        res = run_ma_crossover_backtest(self.df, fast_window=10, slow_window=30, ma_type="SMA", initial_capital=100000.0)
        self.assertEqual(len(res["equity_df"]), len(self.df))
        self.assertGreater(res["metrics"]["final_capital"], 0.0)
        self.assertLessEqual(res["metrics"]["max_drawdown_pct"], 0.0)
        with self.assertRaises(ValueError):
            run_ma_crossover_backtest(self.df, fast_window=30, slow_window=10)

    def test_rsi_backtest(self) -> None:
        res = run_rsi_backtest(self.df, period=14, oversold=35.0, overbought=65.0, initial_capital=100000.0)
        self.assertEqual(len(res["equity_df"]), len(self.df))
        self.assertGreater(res["metrics"]["final_capital"], 0.0)
        with self.assertRaises(ValueError):
            run_rsi_backtest(self.df, oversold=70.0, overbought=30.0)

    def test_broker_parsers(self) -> None:
        self.assertEqual(to_kite_instrument("RELIANCE.NS"), "NSE:RELIANCE")
        self.assertEqual(to_kite_instrument("TCS.BO"), "BSE:TCS")

        kite_payload = {
            "data": {
                "NSE:RELIANCE": {
                    "last_price": 1400.0,
                    "ohlc": {"open": 1380.0, "high": 1405.0, "low": 1375.0, "close": 1385.0},
                    "volume": 123456,
                }
            }
        }
        k_q = parse_kite_quote_response(kite_payload, "NSE:RELIANCE")
        self.assertIsNotNone(k_q)
        assert k_q is not None
        self.assertEqual(k_q["ltp"], 1400.0)
        self.assertEqual(k_q["change"], 15.0)

        up_payload = {
            "data": {
                "NSE_EQ|INE002A01018": {
                    "symbol": "RELIANCE",
                    "last_price": 1402.0,
                    "ohlc": {"open": 1380.0, "high": 1405.0, "low": 1375.0, "close": 1390.0},
                    "volume": 200000,
                }
            }
        }
        u_q = parse_upstox_quote_response(up_payload, "NSE_EQ|INE002A01018")
        self.assertIsNotNone(u_q)
        assert u_q is not None
        self.assertEqual(u_q["ltp"], 1402.0)

        ang_payload = {
            "data": {
                "fetched": [
                    {"tradingSymbol": "RELIANCE-EQ", "ltp": 1405.0, "close": 1395.0, "open": 1390.0, "high": 1410.0, "low": 1385.0, "tradeVolume": 300000}
                ]
            }
        }
        a_q = parse_angel_quote_response(ang_payload)
        self.assertIsNotNone(a_q)
        assert a_q is not None
        self.assertEqual(a_q["ltp"], 1405.0)

    def test_ai_market_summary_and_sanitization(self) -> None:
        summary = build_deterministic_market_summary(
            indices=[{"name": "Nifty 50", "price": 25884.5, "pct_change": 0.45}],
            macro=[{"name": "USD / INR", "price": 84.4, "pct_change": 0.05}],
            breadth={"advances": 32, "declines": 18, "unchanged": 0, "gainers": [{"name": "TCS", "pct_change": 4.8}], "losers": [{"name": "ITC", "pct_change": -1.1}]},
            headlines=[{"title": "Nifty rallies on IT buying", "sentiment": "Bullish", "sentiment_score": 0.4}],
        )
        self.assertIn("Nifty 50", summary)
        self.assertIn("Risk-On", summary)

        self.assertEqual(sanitize_http_url("https://economictimes.indiatimes.com/a"), "https://economictimes.indiatimes.com/a")
        self.assertEqual(sanitize_http_url("javascript:alert(1)"), "#")

    def test_backtest_command_routing(self) -> None:
        c1 = parse_command("RELIANCE BT")
        self.assertEqual(c1.target_module, "Backtesting")
        self.assertEqual(c1.ticker, "RELIANCE.NS")
        c2 = parse_command("BT")
        self.assertEqual(c2.target_module, "Backtesting")


if __name__ == "__main__":
    unittest.main()
