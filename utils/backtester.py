"""Backtesting engine for Moving-Average Crossover and RSI Mean-Reversion strategies."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from utils.indicators import compute_ema, compute_rsi, compute_sma
from utils.portfolio_math import compute_max_drawdown, compute_portfolio_metrics


def _simulate_long_only(
    df: pd.DataFrame,
    raw_signal: pd.Series,
    initial_capital: float = 100_000.0,
    fee_bps: float = 10.0,
) -> Dict[str, Any]:
    """
    Simulate long-only execution with 1-bar signal lag (no lookahead bias) and transaction costs.
    """
    closes = df["Close"].astype(float)
    asset_rets = closes.pct_change().fillna(0.0)

    # Execute today's close signal starting next trading bar
    pos = raw_signal.fillna(0).astype(float).shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(0.0)
    cost = turnover * (fee_bps / 10_000.0)
    strat_rets = (pos * asset_rets) - cost

    strat_equity = initial_capital * (1.0 + strat_rets).cumprod()
    bh_equity = initial_capital * (1.0 + asset_rets).cumprod()

    strat_dd = (strat_equity / strat_equity.cummax()) - 1.0
    bh_dd = (bh_equity / bh_equity.cummax()) - 1.0

    # Extract completed trades
    trades: List[Dict[str, Any]] = []
    in_trade = False
    entry_date = None
    entry_price = 0.0

    pos_arr = pos.to_numpy()
    idx_arr = df.index
    close_arr = closes.to_numpy()
    for i in range(1, len(df)):
        if not in_trade and pos_arr[i] == 1.0 and pos_arr[i - 1] == 0.0:
            in_trade = True
            entry_date = idx_arr[i]
            entry_price = float(close_arr[i - 1])
        elif in_trade and pos_arr[i] == 0.0 and pos_arr[i - 1] == 1.0:
            exit_price = float(close_arr[i - 1])
            ret_pct = ((exit_price / entry_price) - 1.0) * 100.0 - (2.0 * fee_bps / 100.0)
            trades.append(
                {
                    "Entry Date": str(entry_date)[:10],
                    "Exit Date": str(idx_arr[i])[:10],
                    "Entry Price": round(entry_price, 2),
                    "Exit Price": round(exit_price, 2),
                    "Return %": round(ret_pct, 2),
                }
            )
            in_trade = False

    if in_trade and entry_date is not None:
        exit_price = float(close_arr[-1])
        ret_pct = ((exit_price / entry_price) - 1.0) * 100.0 - (fee_bps / 100.0)
        trades.append(
            {
                "Entry Date": str(entry_date)[:10],
                "Exit Date": f"{str(idx_arr[-1])[:10]} (Open)",
                "Entry Price": round(entry_price, 2),
                "Exit Price": round(exit_price, 2),
                "Return %": round(ret_pct, 2),
            }
        )

    total_ret_pct = ((float(strat_equity.iloc[-1]) / initial_capital) - 1.0) * 100.0
    bh_ret_pct = ((float(bh_equity.iloc[-1]) / initial_capital) - 1.0) * 100.0
    years = max(len(df) / 252.0, 1.0 / 252.0)
    cagr_pct = ((float(strat_equity.iloc[-1]) / initial_capital) ** (1.0 / years) - 1.0) * 100.0

    perf = compute_portfolio_metrics(strat_rets, risk_free_rate=0.065)
    win_rate = (
        round(sum(1 for t in trades if t["Return %"] > 0) / len(trades) * 100.0, 1)
        if trades
        else 0.0
    )

    equity_df = pd.DataFrame(
        {
            "Strategy": strat_equity,
            "Buy_Hold": bh_equity,
            "Strategy_DD_Pct": strat_dd * 100.0,
            "Buy_Hold_DD_Pct": bh_dd * 100.0,
            "Position": pos,
        },
        index=df.index,
    )

    return {
        "equity_df": equity_df,
        "trades": trades,
        "metrics": {
            "final_capital": round(float(strat_equity.iloc[-1]), 2),
            "bh_final_capital": round(float(bh_equity.iloc[-1]), 2),
            "total_return_pct": round(total_ret_pct, 2),
            "bh_return_pct": round(bh_ret_pct, 2),
            "cagr_pct": round(float(cagr_pct), 2),
            "sharpe_ratio": perf.get("sharpe_ratio"),
            "max_drawdown_pct": round(compute_max_drawdown(strat_equity) * 100.0, 2),
            "bh_max_drawdown_pct": round(compute_max_drawdown(bh_equity) * 100.0, 2),
            "win_rate_pct": win_rate,
            "num_trades": len(trades),
        },
    }


def run_ma_crossover_backtest(
    df: pd.DataFrame,
    fast_window: int = 20,
    slow_window: int = 50,
    ma_type: str = "SMA",
    initial_capital: float = 100_000.0,
    fee_bps: float = 10.0,
) -> Dict[str, Any]:
    """Backtest long-only Fast MA > Slow MA crossover strategy."""
    if fast_window >= slow_window:
        raise ValueError("fast_window must be less than slow_window")
    closes = df["Close"].astype(float)
    fn = compute_ema if ma_type.upper() == "EMA" else compute_sma
    fast_ma = fn(closes, fast_window)
    slow_ma = fn(closes, slow_window)
    signal = (fast_ma > slow_ma).astype(int)
    return _simulate_long_only(df, signal, initial_capital=initial_capital, fee_bps=fee_bps)


def run_rsi_backtest(
    df: pd.DataFrame,
    period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
    initial_capital: float = 100_000.0,
    fee_bps: float = 10.0,
) -> Dict[str, Any]:
    """Backtest long-only RSI mean-reversion: enter when RSI <= oversold, exit when RSI >= overbought."""
    if oversold >= overbought:
        raise ValueError("oversold threshold must be less than overbought threshold")
    rsi = compute_rsi(df["Close"].astype(float), period=period)
    sig = np.zeros(len(df), dtype=int)
    holding = False
    rsi_vals = rsi.to_numpy()
    for i in range(len(df)):
        val = rsi_vals[i]
        if np.isnan(val):
            sig[i] = 0
            continue
        if not holding and val <= oversold:
            holding = True
        elif holding and val >= overbought:
            holding = False
        sig[i] = 1 if holding else 0

    signal_series = pd.Series(sig, index=df.index)
    return _simulate_long_only(df, signal_series, initial_capital=initial_capital, fee_bps=fee_bps)
