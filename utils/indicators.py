"""Pure pandas/numpy technical indicators for Charting, Screener, and Alerts."""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average over `window` periods."""
    if window <= 0:
        raise ValueError("window must be positive")
    return series.astype(float).rolling(window=window, min_periods=window).mean()


def compute_ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential Moving Average over `window` periods."""
    if window <= 0:
        raise ValueError("window must be positive")
    return series.astype(float).ewm(span=window, adjust=False, min_periods=window).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index (0-100)."""
    if period <= 0:
        raise ValueError("period must be positive")
    close = series.astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # When avg_loss == 0 and avg_gain > 0 -> RSI = 100; when both == 0 -> RSI = 50
    both_zero = (avg_gain == 0.0) & (avg_loss == 0.0)
    only_loss_zero = (avg_loss == 0.0) & (avg_gain > 0.0)
    rsi = rsi.where(~only_loss_zero, 100.0)
    rsi = rsi.where(~both_zero, 50.0)
    return rsi


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, Signal line, and Histogram."""
    close = series.astype(float)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(
    series: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Upper, Middle (SMA), and Lower Bollinger Bands."""
    close = series.astype(float)
    middle = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std(ddof=0)
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def compute_supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
) -> Tuple[pd.Series, pd.Series]:
    """
    Compute Supertrend indicator and trend direction (+1 bullish, -1 bearish).

    Expects columns: High, Low, Close.
    """
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    n = len(df)
    final_upper = basic_upper.to_numpy(copy=True)
    final_lower = basic_lower.to_numpy(copy=True)
    close_arr = close.to_numpy()
    supertrend = np.full(n, np.nan, dtype=float)
    direction = np.ones(n, dtype=float)

    first_valid = int(np.argmax(~np.isnan(atr.to_numpy()))) if (~np.isnan(atr.to_numpy())).any() else n
    if first_valid < n:
        supertrend[first_valid] = final_upper[first_valid]
        direction[first_valid] = -1.0 if close_arr[first_valid] < supertrend[first_valid] else 1.0

    for i in range(first_valid + 1, n):
        if np.isnan(final_upper[i]) or np.isnan(final_lower[i]):
            continue

        if final_upper[i] < final_upper[i - 1] or close_arr[i - 1] > final_upper[i - 1]:
            final_upper[i] = final_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        if final_lower[i] > final_lower[i - 1] or close_arr[i - 1] < final_lower[i - 1]:
            final_lower[i] = final_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        prev_st = supertrend[i - 1]
        if prev_st == final_upper[i - 1]:
            if close_arr[i] <= final_upper[i]:
                supertrend[i] = final_upper[i]
                direction[i] = -1.0
            else:
                supertrend[i] = final_lower[i]
                direction[i] = 1.0
        else:
            if close_arr[i] >= final_lower[i]:
                supertrend[i] = final_lower[i]
                direction[i] = 1.0
            else:
                supertrend[i] = final_upper[i]
                direction[i] = -1.0

    return (
        pd.Series(supertrend, index=df.index, name="Supertrend"),
        pd.Series(direction, index=df.index, name="Supertrend_Dir"),
    )


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Volume-Weighted Average Price over the loaded price series."""
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float).fillna(0.0).clip(lower=0.0)

    typical_price = (high + low + close) / 3.0
    cum_vol = volume.cumsum().replace(0.0, np.nan)
    return (typical_price * volume).cumsum() / cum_vol
