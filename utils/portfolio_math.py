"""Portfolio risk, XIRR, and Indian capital gains tax estimation utilities."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

# Statutory Indian listed equity capital gains tax rates (Finance (No. 2) Act, 2024)
INDIA_EQUITY_STCG_RATE = 0.20  # 20% u/s 111A (holding period <= 12 months)
INDIA_EQUITY_LTCG_RATE = 0.125  # 12.5% u/s 112A (holding period > 12 months)
INDIA_EQUITY_LTCG_EXEMPTION = 125_000.0  # ₹1.25 lakh annual exemption u/s 112A
INDIA_EQUITY_LTCG_DAYS = 365


def _to_date(val: Union[date, datetime, str]) -> date:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return datetime.fromisoformat(str(val).strip()[:10]).date()


def compute_xirr(cashflows: Sequence[Tuple[Union[date, datetime, str], float]]) -> Optional[float]:
    """
    Compute annualized XIRR for irregular (date, amount) cashflows.

    Negative amounts represent outflows (buys); positive amounts represent inflows
    (sells or current portfolio terminal value). Returns decimal rate (e.g., 0.14 = 14%)
    or None if cashflows lack both positive and negative entries.
    """
    if len(cashflows) < 2:
        return None

    parsed = sorted(((_to_date(d), float(amt)) for d, amt in cashflows), key=lambda x: x[0])
    amounts = [amt for _, amt in parsed]
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return None

    d0 = parsed[0][0]
    years = np.array([(d - d0).days / 365.0 for d, _ in parsed], dtype=float)
    cfs = np.array(amounts, dtype=float)

    def npv(rate: float) -> float:
        if rate <= -1.0:
            return float("inf")
        return float(np.sum(cfs / ((1.0 + rate) ** years)))

    # Bracket root via grid search over plausible annualized returns (-99% to +500%)
    grid = [-0.99, -0.9, -0.75, -0.5, -0.25, -0.1, 0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0]
    vals = [npv(r) for r in grid]
    bracket: Optional[Tuple[float, float]] = None
    for i in range(len(grid) - 1):
        v1, v2 = vals[i], vals[i + 1]
        if np.isfinite(v1) and np.isfinite(v2) and (v1 == 0 or v1 * v2 <= 0):
            bracket = (grid[i], grid[i + 1])
            break

    if bracket is None:
        return None

    low, high = bracket
    f_low = npv(low)
    for _ in range(120):
        mid = 0.5 * (low + high)
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7 or (high - low) < 1e-9:
            return round(float(mid), 6)
        if f_low * f_mid <= 0:
            high = mid
        else:
            low = mid
            f_low = f_mid
    return round(float(0.5 * (low + high)), 6)


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    """Compute maximum peak-to-trough drawdown as a negative fraction (e.g., -0.22)."""
    if equity_curve is None or equity_curve.empty:
        return 0.0
    series = equity_curve.astype(float).dropna()
    if series.empty:
        return 0.0
    running_max = series.cummax()
    drawdowns = (series / running_max) - 1.0
    return float(drawdowns.min())


def compute_portfolio_metrics(
    portfolio_returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    risk_free_rate: float = 0.065,
    trading_days: int = 252,
) -> Dict[str, Optional[float]]:
    """
    Compute annualized return, volatility, Sharpe ratio, max drawdown, and beta.

    Default risk-free rate is 6.5% p.a. (approximate Indian 91-day T-bill / repo benchmark).
    """
    rets = portfolio_returns.astype(float).dropna()
    if len(rets) < 2:
        return {
            "annualized_return": None,
            "annualized_volatility": None,
            "sharpe_ratio": None,
            "max_drawdown": None,
            "beta": None,
        }

    mean_daily = float(rets.mean())
    vol_daily = float(rets.std(ddof=1))
    ann_return = (1.0 + mean_daily) ** trading_days - 1.0
    ann_vol = vol_daily * np.sqrt(trading_days)
    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else None

    equity = (1.0 + rets).cumprod()
    max_dd = compute_max_drawdown(equity)

    beta: Optional[float] = None
    if benchmark_returns is not None and not benchmark_returns.empty:
        aligned = pd.concat([rets, benchmark_returns.astype(float)], axis=1, join="inner").dropna()
        if len(aligned) >= 5:
            p_col = aligned.iloc[:, 0]
            b_col = aligned.iloc[:, 1]
            b_var = float(b_col.var(ddof=1))
            if b_var > 0:
                beta = float(p_col.cov(b_col) / b_var)

    return {
        "annualized_return": round(float(ann_return), 6),
        "annualized_volatility": round(float(ann_vol), 6),
        "sharpe_ratio": round(float(sharpe), 4) if sharpe is not None else None,
        "max_drawdown": round(float(max_dd), 6),
        "beta": round(float(beta), 4) if beta is not None else None,
    }


def estimate_indian_capital_gains(
    lots: Sequence[Dict[str, Any]],
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Estimate Indian listed-equity unrealized STCG and LTCG tax liability.

    Rates applied (Finance (No. 2) Act, 2024):
        - STCG (holding <= 365 days): 20.0% u/s 111A
        - LTCG (holding > 365 days): 12.5% u/s 112A on gains above ₹1,25,000 exemption
    """
    ref = reference_date or date.today()
    stcg_total = 0.0
    ltcg_total = 0.0
    breakdown: List[Dict[str, Any]] = []

    for lot in lots:
        qty = float(lot.get("qty", 0.0))
        buy_price = float(lot.get("buy_price", 0.0))
        cur_price = float(lot.get("current_price", buy_price))
        buy_dt = _to_date(lot.get("buy_date", ref))
        holding_days = max(0, (ref - buy_dt).days)
        gain = (cur_price - buy_price) * qty
        bucket = "LTCG (>12M)" if holding_days > INDIA_EQUITY_LTCG_DAYS else "STCG (≤12M)"

        if holding_days > INDIA_EQUITY_LTCG_DAYS:
            ltcg_total += gain
        else:
            stcg_total += gain

        breakdown.append(
            {
                "symbol": lot.get("symbol", ""),
                "qty": qty,
                "buy_date": buy_dt.isoformat(),
                "holding_days": holding_days,
                "bucket": bucket,
                "unrealized_gain": round(gain, 2),
            }
        )

    taxable_stcg = max(0.0, stcg_total)
    stcg_tax = taxable_stcg * INDIA_EQUITY_STCG_RATE

    taxable_ltcg = max(0.0, ltcg_total - INDIA_EQUITY_LTCG_EXEMPTION)
    ltcg_tax = taxable_ltcg * INDIA_EQUITY_LTCG_RATE

    return {
        "stcg_gain": round(stcg_total, 2),
        "ltcg_gain": round(ltcg_total, 2),
        "ltcg_exemption_used": round(min(max(0.0, ltcg_total), INDIA_EQUITY_LTCG_EXEMPTION), 2),
        "taxable_stcg": round(taxable_stcg, 2),
        "taxable_ltcg": round(taxable_ltcg, 2),
        "estimated_stcg_tax": round(stcg_tax, 2),
        "estimated_ltcg_tax": round(ltcg_tax, 2),
        "total_estimated_tax": round(stcg_tax + ltcg_tax, 2),
        "stcg_rate_pct": INDIA_EQUITY_STCG_RATE * 100.0,
        "ltcg_rate_pct": INDIA_EQUITY_LTCG_RATE * 100.0,
        "ltcg_exemption_inr": INDIA_EQUITY_LTCG_EXEMPTION,
        "lots": breakdown,
    }
