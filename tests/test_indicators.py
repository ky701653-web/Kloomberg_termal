"""Unit tests for technical indicators in utils/indicators.py."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from utils.indicators import (
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
    compute_supertrend,
    compute_vwap,
)


class TestTechnicalIndicators(unittest.TestCase):
    def setUp(self) -> None:
        n = 60
        idx = pd.date_range("2026-01-01", periods=n, freq="B")
        closes = np.linspace(100.0, 160.0, n) + np.sin(np.arange(n) * 0.4) * 2.0
        self.df = pd.DataFrame(
            {
                "Open": closes - 0.5,
                "High": closes + 1.5,
                "Low": closes - 1.5,
                "Close": closes,
                "Volume": np.full(n, 10000.0),
            },
            index=idx,
        )

    def test_sma_and_ema(self) -> None:
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        sma3 = compute_sma(s, 3)
        self.assertTrue(pd.isna(sma3.iloc[1]))
        self.assertAlmostEqual(float(sma3.iloc[2]), 20.0)
        self.assertAlmostEqual(float(sma3.iloc[4]), 40.0)

        ema3 = compute_ema(s, 3)
        self.assertEqual(len(ema3), 5)
        self.assertGreater(float(ema3.iloc[-1]), 35.0)

    def test_rsi_bounds_and_extremes(self) -> None:
        up = pd.Series(np.arange(1.0, 40.0))
        rsi_up = compute_rsi(up, 14)
        self.assertAlmostEqual(float(rsi_up.iloc[-1]), 100.0)

        down = pd.Series(np.arange(40.0, 1.0, -1.0))
        rsi_down = compute_rsi(down, 14)
        self.assertAlmostEqual(float(rsi_down.iloc[-1]), 0.0)

        flat = pd.Series(np.full(30, 100.0))
        rsi_flat = compute_rsi(flat, 14)
        self.assertAlmostEqual(float(rsi_flat.iloc[-1]), 50.0)

    def test_macd_consistency(self) -> None:
        macd_line, sig_line, hist = compute_macd(self.df["Close"])
        diff = (macd_line - sig_line - hist).abs().max()
        self.assertAlmostEqual(float(diff), 0.0, places=9)

    def test_bollinger_bands_ordering(self) -> None:
        upper, mid, lower = compute_bollinger_bands(self.df["Close"], window=20, num_std=2.0)
        valid = upper.notna()
        self.assertTrue((upper[valid] >= mid[valid]).all())
        self.assertTrue((mid[valid] >= lower[valid]).all())
        sma20 = compute_sma(self.df["Close"], 20)
        self.assertAlmostEqual(float((mid[valid] - sma20[valid]).abs().max()), 0.0, places=9)

    def test_supertrend_output(self) -> None:
        st_line, st_dir = compute_supertrend(self.df, period=10, multiplier=3.0)
        self.assertEqual(len(st_line), len(self.df))
        self.assertTrue(st_line.iloc[20:].notna().all())
        self.assertTrue(set(st_dir.dropna().unique()).issubset({-1.0, 1.0}))

    def test_vwap_calculation(self) -> None:
        df = pd.DataFrame(
            {
                "High": [12.0, 22.0],
                "Low": [8.0, 18.0],
                "Close": [10.0, 20.0],
                "Volume": [100.0, 300.0],
            }
        )
        # Typical prices: 10.0 (vol 100) and 20.0 (vol 300) -> VWAP[1] = (1000 + 6000) / 400 = 17.5
        vwap = compute_vwap(df)
        self.assertAlmostEqual(float(vwap.iloc[0]), 10.0)
        self.assertAlmostEqual(float(vwap.iloc[1]), 17.5)


if __name__ == "__main__":
    unittest.main()
