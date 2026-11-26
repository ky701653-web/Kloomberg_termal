"""Indian currency, lakh/crore, and percentage formatting utilities."""

from __future__ import annotations

import math
from typing import Optional

INR_SYMBOL = "₹"
COLOR_UP = "#26A69A"
COLOR_DOWN = "#EF5350"
COLOR_FLAT = "#8B949E"


def is_valid_number(value: object) -> bool:
    """Return True if value can be converted to a finite float."""
    if value is None:
        return False
    try:
        num = float(value)
        return math.isfinite(num)
    except (TypeError, ValueError):
        return False


def format_indian_commas(value: float, decimals: int = 2) -> str:
    """Format a number using Indian digit grouping (e.g., 12,34,567.89)."""
    if not is_valid_number(value):
        return "N/A"
    sign = "-" if value < 0 else ""
    abs_val = abs(float(value))
    formatted = f"{abs_val:.{decimals}f}"
    if "." in formatted:
        int_part, dec_part = formatted.split(".")
        dec_suffix = f".{dec_part}"
    else:
        int_part, dec_suffix = formatted, ""

    if len(int_part) <= 3:
        grouped = int_part
    else:
        last_three = int_part[-3:]
        rest = int_part[:-3]
        chunks = []
        while len(rest) > 2:
            chunks.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            chunks.append(rest)
        chunks.reverse()
        grouped = ",".join(chunks) + "," + last_three

    return f"{sign}{grouped}{dec_suffix}"


def format_inr(value: Optional[float], decimals: int = 2, compact: bool = False) -> str:
    """Format an INR value using Indian notation (lakh / crore / lakh crore)."""
    if not is_valid_number(value):
        return "N/A"
    num = float(value)  # type: ignore[arg-type]
    if not compact:
        sign = "-" if num < 0 else ""
        return f"{sign}{INR_SYMBOL}{format_indian_commas(abs(num), decimals=decimals)}"

    sign = "-" if num < 0 else ""
    abs_val = abs(num)
    if abs_val >= 1e12:
        return f"{sign}{INR_SYMBOL}{abs_val / 1e12:.{decimals}f} lakh crore"
    if abs_val >= 1e7:
        return f"{sign}{INR_SYMBOL}{abs_val / 1e7:.{decimals}f} Cr"
    if abs_val >= 1e5:
        return f"{sign}{INR_SYMBOL}{abs_val / 1e5:.{decimals}f} L"
    return f"{sign}{INR_SYMBOL}{format_indian_commas(abs_val, decimals=decimals)}"


def format_number(value: Optional[float], decimals: int = 2, prefix: str = "") -> str:
    """Format a generic market price or index level with standard commas."""
    if not is_valid_number(value):
        return "N/A"
    num = float(value)  # type: ignore[arg-type]
    sign = "-" if num < 0 else ""
    return f"{sign}{prefix}{abs(num):,.{decimals}f}"


def format_pct(value: Optional[float], decimals: int = 2, show_sign: bool = True) -> str:
    """Format a percentage change with optional leading +/- sign."""
    if not is_valid_number(value):
        return "N/A"
    num = float(value)  # type: ignore[arg-type]
    if show_sign and num > 0:
        return f"+{num:.{decimals}f}%"
    return f"{num:.{decimals}f}%"


def delta_color(value: Optional[float]) -> str:
    """Return Bloomberg-style hex color for positive, negative, or flat moves."""
    if not is_valid_number(value):
        return COLOR_FLAT
    num = float(value)  # type: ignore[arg-type]
    if num > 0:
        return COLOR_UP
    if num < 0:
        return COLOR_DOWN
    return COLOR_FLAT
