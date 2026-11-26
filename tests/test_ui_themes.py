"""Unit tests for Dark/Light WCAG AA palettes, CSS variables, and all 19 UI tabs."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import app
from utils.ui import THEMES, get_plotly_theme, style_change_dataframe

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def _rel_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = _rel_luminance(fg), _rel_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


class TestThemeContrastAndUI(unittest.TestCase):
    def test_dark_palette_exact_hex_and_wcag_aa(self) -> None:
        d = THEMES["dark"]
        self.assertEqual(d["bg"], "#0E1117")
        self.assertEqual(d["surface"], "#161B22")
        self.assertEqual(d["border"], "#2A313C")
        self.assertEqual(d["text"], "#E6EDF3")
        self.assertEqual(d["muted"], "#8B949E")
        self.assertEqual(d["accent"], "#F5A524")
        self.assertEqual(d["up"], "#26A69A")
        self.assertEqual(d["down"], "#EF5350")

        for mode, pal in THEMES.items():
            for surface_key in ("bg", "surface"):
                bg = pal[surface_key]
                self.assertGreaterEqual(_contrast_ratio(pal["text"], bg), 4.5, f"{mode} text vs {surface_key}")
                self.assertGreaterEqual(_contrast_ratio(pal["muted"], bg), 4.5, f"{mode} muted vs {surface_key}")
                self.assertGreaterEqual(_contrast_ratio(pal["accent"], bg), 4.5, f"{mode} accent vs {surface_key}")
                self.assertGreaterEqual(_contrast_ratio(pal["up"], bg), 4.5, f"{mode} up vs {surface_key}")
                self.assertGreaterEqual(_contrast_ratio(pal["down"], bg), 4.5, f"{mode} down vs {surface_key}")
            self.assertGreaterEqual(
                _contrast_ratio(pal["accent_contrast"], pal["accent"]), 4.5, f"{mode} button contrast"
            )

    def test_plotly_theme_and_table_styler(self) -> None:
        dark_pt = get_plotly_theme("dark")
        light_pt = get_plotly_theme("light")
        self.assertEqual(dark_pt["paper_bgcolor"], "#0E1117")
        self.assertEqual(light_pt["paper_bgcolor"], "#F6F8FA")

        df = pd.DataFrame({"Symbol": ["TCS"], "LTP (₹)": ["₹3,500.00"], "% Chg": ["+1.50%"]})
        html_out = style_change_dataframe(df, ["% Chg"]).to_html()
        self.assertIn("JetBrains Mono", html_out)
        self.assertIn("text-align: right", html_out)

    def test_all_19_tabs_render_in_dark_and_light_modes(self) -> None:
        from streamlit.testing.v1 import AppTest

        sample_quotes = [
            {"name": "Nifty 50", "symbol": "^NSEI", "price": 25884.5, "prev_close": 25820.0, "change": 64.5, "pct_change": 0.25, "high": 25950.0, "low": 25780.0, "volume": 1000000}
        ]
        sample_ohlcv = pd.DataFrame(
            {
                "Open": [100.0 + i for i in range(60)],
                "High": [102.0 + i for i in range(60)],
                "Low": [99.0 + i for i in range(60)],
                "Close": [101.0 + i for i in range(60)],
                "Volume": [50000.0] * 60,
            },
            index=pd.date_range("2026-01-01", periods=60, freq="B"),
        )
        sample_breadth = {
            "advances": 30,
            "declines": 19,
            "unchanged": 1,
            "gainers": [{"name": "TCS", "symbol": "TCS.NS", "price": 2640.0, "change": 120.0, "pct_change": 4.8, "high": 2660.0, "low": 2550.0}],
            "losers": [{"name": "ITC", "symbol": "ITC.NS", "price": 410.0, "change": -4.0, "pct_change": -0.97, "high": 415.0, "low": 408.0}],
            "source": "Mock",
        }
        sample_news = [
            {"source": "Economic Times", "title": "Nifty rises", "link": "https://economictimes.indiatimes.com", "published": "Today", "sentiment_score": 0.4, "sentiment": "Bullish"}
        ]
        sample_wl = [
            {"symbol": "RELIANCE.NS", "name": "RELIANCE", "price": 1396.2, "change": 22.2, "pct_change": 1.62, "volume": 1200000, "high_52w": 1600.0, "low_52w": 1150.0, "pos_52w_pct": 54.7, "sparkline": [1350.0, 1375.0, 1396.2]}
        ]
        sample_fund = {
            "ratios": {"symbol": "TCS.NS", "short_name": "TCS", "sector": "IT", "industry": "IT Services", "market_cap": 1e13, "pe": 25.0, "pb": 10.0, "roe_pct": 45.0, "div_yield_pct": 1.5, "current_price": 2640.0, "high_52w": 4200.0, "low_52w": 2400.0, "eps": 105.0, "debt_to_equity": 5.0, "profit_margin_pct": 19.0, "summary": "IT services."},
            "income_annual": {"columns": ["Line Item", "2025-03-31"], "rows": [{"Line Item": "Revenue", "2025-03-31": 2.4e12}]},
            "income_quarterly": {"columns": [], "rows": []},
            "balance_sheet": {"columns": [], "rows": []},
            "cashflow": {"columns": [], "rows": []},
            "peers": [],
        }
        sample_opt = {
            "symbol": "NIFTY",
            "spot": 25880.0,
            "expiries": ["28-Nov-2026"],
            "selected_expiry": "28-Nov-2026",
            "rows": [{"strike": 25900.0, "ce_oi": 1000, "ce_chg_oi": 100, "ce_iv": 12.0, "ce_ltp": 90.0, "pe_ltp": 85.0, "pe_iv": 12.5, "pe_chg_oi": 120, "pe_oi": 1200}],
            "pcr_oi": 1.2,
            "pcr_vol": 1.1,
            "max_pain": 25900.0,
            "max_pain_curve": [{"strike": 25900.0, "total_payout": 0.0}],
        }
        sample_fii = [{"category": "FII/FPI", "date": "26-Nov-2026", "buy_value_cr": 12000.0, "sell_value_cr": 11000.0, "net_value_cr": 1000.0}]
        sample_macro = {"fred_enabled": False, "fred_series": {}, "world_bank": {}, "reference": [{"Indicator": "Repo", "Value": "6.50%", "Source": "RBI", "Frequency": "Bi-monthly"}]}
        sample_mf_search = ([{"schemeCode": "120716", "schemeName": "UTI Nifty 50 Index Fund"}], "Now")
        sample_mf_nav = ({"meta": {"fund_house": "UTI"}, "latest_nav": 150.0, "latest_date": "2026-11-25", "cagr": {"1Y": 12.5}, "history": [{"date": "2026-11-25", "nav": 150.0}]}, False, "Now")
        sample_crypto = ([{"rank": 1, "name": "Bitcoin", "symbol": "BTC", "price_inr": 8000000.0, "chg_24h": 1.2, "chg_7d": 3.4, "market_cap_inr": 1e14, "volume_24h_inr": 1e12, "sparkline": [7900000.0, 8000000.0]}], False, "Now")
        sample_fx = ([{"pair": "USD / INR", "currency": "USD", "inr_per_unit": 84.4, "units_per_100_inr": 1.18, "date": "2026-11-25"}], False, "Now")

        targets = [
            ("data.market_data.fetch_yfinance_quotes", (sample_quotes, False, "Now")),
            ("modules.home.fetch_yfinance_quotes", (sample_quotes, False, "Now")),
            ("modules.heatmap.fetch_yfinance_quotes", (sample_quotes, False, "Now")),
            ("modules.options_fno.fetch_yfinance_quotes", (sample_quotes, False, "Now")),
            ("modules.macro.fetch_yfinance_quotes", (sample_quotes, False, "Now")),
            ("modules.watchlist.fetch_watchlist_quotes", (sample_wl, False, "Now")),
            ("modules.portfolio.fetch_watchlist_quotes", (sample_wl, False, "Now")),
            ("modules.charting.fetch_ohlcv", (sample_ohlcv, False, "Now")),
            ("modules.backtesting.fetch_ohlcv", (sample_ohlcv, False, "Now")),
            ("modules.charting.fetch_multi_close", (sample_ohlcv[["Close"]], False, "Now")),
            ("modules.portfolio.fetch_multi_close", (sample_ohlcv[["Close"]], False, "Now")),
            ("modules.fundamentals.fetch_fundamentals", (sample_fund, False, "Now")),
            ("modules.screener.fetch_screener_data", ([], False, "Now")),
            ("modules.heatmap.fetch_nifty50_heatmap_data", ([{"name": "TCS", "symbol": "TCS.NS", "sector": "IT", "price": 2640.0, "change": 120.0, "pct_change": 4.8, "weight_proxy": 1e9}], False, "Now")),
            ("modules.home.fetch_usd_inr_frankfurter", {"name": "USD / INR", "symbol": "USD/INR", "price": 84.4, "prev_close": 84.4, "change": 0.0, "pct_change": 0.0}),
            ("modules.home.fetch_nse_nifty50_breadth_and_movers", (sample_breadth, False, "Now")),
            ("modules.options_fno.fetch_option_chain", (sample_opt, False, "Now")),
            ("modules.fii_dii.fetch_fii_dii_flows", (sample_fii, False, "Now")),
            ("modules.corporate_actions.fetch_corporate_actions_and_filings", ({"actions": [], "announcements": [], "yf_dividends": [], "yf_splits": []}, False, "Now")),
            ("modules.ipo.fetch_ipo_data", ({"current": [], "upcoming": [], "news": []}, False, "Now")),
            ("modules.home.fetch_news_feed", (sample_news, False, "Now")),
            ("modules.news.fetch_news_feed", (sample_news, False, "Now")),
            ("modules.macro.fetch_macro_dashboard", (sample_macro, False, "Now")),
            ("modules.mutual_funds.search_mutual_funds", sample_mf_search),
            ("modules.mutual_funds.fetch_mf_nav_history", sample_mf_nav),
            ("modules.crypto_fx.fetch_crypto_inr", sample_crypto),
            ("modules.crypto_fx.fetch_fx_inr", sample_fx),
        ]

        with ExitStack() as stack:
            for target, rv in targets:
                stack.enter_context(patch(target, return_value=rv))

            for theme_mode in ("dark", "light"):
                for mod_name in app.MODULE_RENDERERS:
                    at = AppTest.from_file(APP_PATH, default_timeout=20)
                    at.session_state["theme_mode"] = theme_mode
                    at.session_state["active_module"] = mod_name
                    at.run()
                    self.assertFalse(
                        bool(at.exception),
                        msg=f"Module '{mod_name}' failed in '{theme_mode}' mode: {at.exception}",
                    )


if __name__ == "__main__":
    unittest.main()
