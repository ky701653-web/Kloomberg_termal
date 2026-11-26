"""Unit tests for portfolio math, Indian capital gains, alerts, cache CRUD, and command routing."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from data.market_data import load_nifty500_universe
from data.nse_data import compute_max_pain
from modules.alerts import evaluate_rule_against_ohlcv
from modules.command_bar import parse_command
from modules.mutual_funds import compute_sip_projection
from utils.cache import TerminalCache
from utils.portfolio_math import (
    compute_max_drawdown,
    compute_portfolio_metrics,
    compute_xirr,
    estimate_indian_capital_gains,
)


class TestPortfolioMath(unittest.TestCase):
    def test_xirr_simple_annual_return(self) -> None:
        cfs = [(date(2025, 1, 1), -100000.0), (date(2026, 1, 1), 115000.0)]
        irr = compute_xirr(cfs)
        self.assertIsNotNone(irr)
        assert irr is not None
        self.assertAlmostEqual(irr, 0.15, places=3)

        # Invalid cashflows (all negative) -> None
        self.assertIsNone(compute_xirr([(date(2025, 1, 1), -1000.0), (date(2025, 6, 1), -500.0)]))

    def test_max_drawdown_and_metrics(self) -> None:
        eq = pd.Series([100.0, 120.0, 90.0, 110.0])
        self.assertAlmostEqual(compute_max_drawdown(eq), -0.25, places=6)

        rets = pd.Series([0.01, -0.005, 0.012, 0.004, -0.008, 0.009, 0.003])
        metrics = compute_portfolio_metrics(rets, benchmark_returns=rets, risk_free_rate=0.065)
        self.assertIsNotNone(metrics["sharpe_ratio"])
        self.assertAlmostEqual(float(metrics["beta"]), 1.0, places=4)

    def test_indian_capital_gains_stcg_and_ltcg(self) -> None:
        ref = date(2026, 11, 26)
        lots = [
            # STCG (< 12 months): gain = (1200 - 1000) * 100 = 20,000 -> 20% tax = 4,000
            {"symbol": "INFY.NS", "qty": 100, "buy_price": 1000.0, "current_price": 1200.0, "buy_date": "2026-06-01"},
            # LTCG (> 12 months): gain = (2500 - 1000) * 150 = 225,000 -> above 125,000 exemption = 100,000 -> 12.5% = 12,500
            {"symbol": "TCS.NS", "qty": 150, "buy_price": 1000.0, "current_price": 2500.0, "buy_date": "2024-01-10"},
        ]
        res = estimate_indian_capital_gains(lots, reference_date=ref)
        self.assertAlmostEqual(res["stcg_gain"], 20000.0)
        self.assertAlmostEqual(res["ltcg_gain"], 225000.0)
        self.assertAlmostEqual(res["estimated_stcg_tax"], 4000.0)
        self.assertAlmostEqual(res["estimated_ltcg_tax"], 12500.0)
        self.assertAlmostEqual(res["total_estimated_tax"], 16500.0)


class TestModulesAndPersistence(unittest.TestCase):
    def test_sip_projection(self) -> None:
        res = compute_sip_projection(10000.0, 10, 12.0)
        self.assertEqual(res["invested"], 1200000.0)
        self.assertGreater(res["future_value"], 2200000.0)

    def test_max_pain_calculation(self) -> None:
        rows = [
            {"strike": 24000.0, "ce_oi": 1000.0, "pe_oi": 100.0},
            {"strike": 24500.0, "ce_oi": 5000.0, "pe_oi": 5000.0},
            {"strike": 25000.0, "ce_oi": 100.0, "pe_oi": 1000.0},
        ]
        mp, curve = compute_max_pain(rows)
        self.assertEqual(mp, 24500.0)
        self.assertEqual(len(curve), 3)

    def test_alert_evaluation(self) -> None:
        df = pd.DataFrame({"Close": [100.0, 110.0]})
        msg = evaluate_rule_against_ohlcv({"symbol": "TCS.NS", "condition": "Price >=", "threshold": 105.0}, df)
        self.assertIsNotNone(msg)
        self.assertIn("TCS.NS", str(msg))
        self.assertIsNone(evaluate_rule_against_ohlcv({"symbol": "TCS.NS", "condition": "Price <=", "threshold": 95.0}, df))

    def test_sqlite_watchlist_screens_portfolio_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TerminalCache(Path(tmpdir) / "full.db")

            wl = cache.get_watchlist(default_tickers=["RELIANCE.NS", "TCS.NS"])
            self.assertEqual(wl, ["RELIANCE.NS", "TCS.NS"])
            cache.add_watchlist_ticker("INFY.NS")
            cache.remove_watchlist_ticker("TCS.NS")
            self.assertEqual(cache.get_watchlist(), ["RELIANCE.NS", "INFY.NS"])

            cache.save_screen("My Screen", {"min_roe": 15.0})
            self.assertIn("My Screen", cache.get_saved_screens())
            cache.delete_screen("My Screen")
            self.assertNotIn("My Screen", cache.get_saved_screens())

            hid = cache.add_holding("RELIANCE.NS", 10, 1250.0, "2025-01-10")
            self.assertEqual(len(cache.get_holdings()), 1)
            cache.delete_holding(hid)
            self.assertEqual(len(cache.get_holdings()), 0)

            rid = cache.add_alert_rule("INFY.NS", "Price >=", 1800.0)
            self.assertEqual(len(cache.get_alert_rules()), 1)
            cache.toggle_alert_rule(rid, False)
            self.assertEqual(cache.get_alert_rules()[0]["enabled"], 0)
            cache.log_alert_trigger(rid, "INFY.NS", "Triggered", "In-App")
            self.assertEqual(len(cache.get_alert_history()), 1)
            cache.delete_alert_rule(rid)
            self.assertEqual(len(cache.get_alert_rules()), 0)

    def test_all_stage_command_routing(self) -> None:
        cases = [
            ("WL", "Watchlist"),
            ("SCREEN", "Screener"),
            ("HEATMAP", "Sector & Nifty Heatmap"),
            ("FII", "FII/DII Flows"),
            ("MACRO", "Macro Dashboard"),
            ("RELIANCE CORP", "Corporate Actions & Filings"),
            ("IPO", "IPO Tracker"),
            ("MF", "Mutual Funds"),
            ("PORT", "Portfolio Tracker"),
            ("CRYPTO", "Crypto & FX (INR)"),
            ("ALERTS", "Alerts"),
            ("STATUS", "Data Source Status"),
        ]
        for raw, expected_mod in cases:
            parsed = parse_command(raw)
            self.assertTrue(parsed.is_valid, msg=raw)
            self.assertEqual(parsed.target_module, expected_mod, msg=raw)

    def test_nifty500_universe_loaded(self) -> None:
        uni = load_nifty500_universe()
        self.assertGreaterEqual(len(uni), 490)
        self.assertTrue(all(item["yf_ticker"].endswith(".NS") for item in uni))


if __name__ == "__main__":
    unittest.main()
