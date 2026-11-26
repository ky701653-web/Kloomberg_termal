"""IST clock, NSE trading hours (9:15 AM - 3:30 PM IST), and holiday checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Dict, Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
NSE_PREOPEN_START = time(9, 0)
NSE_OPEN_TIME = time(9, 15)
NSE_CLOSE_TIME = time(15, 30)

# Major NSE equity market holidays (YYYY-MM-DD -> Holiday Name).
# Update annually from NSE's official trading holidays circular.
NSE_HOLIDAYS: Dict[str, str] = {
    # 2025
    "2025-02-26": "Mahashivratri",
    "2025-03-14": "Holi",
    "2025-03-31": "Id-Ul-Fitr (Ramzan Id)",
    "2025-04-10": "Shri Mahavir Jayanti",
    "2025-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2025-04-18": "Good Friday",
    "2025-05-01": "Maharashtra Day",
    "2025-08-15": "Independence Day",
    "2025-08-27": "Ganesh Chaturthi",
    "2025-10-02": "Mahatma Gandhi Jayanti / Dussehra",
    "2025-10-21": "Diwali Laxmi Pujan",
    "2025-10-22": "Diwali Balipratipada",
    "2025-11-05": "Prakash Gurpurb Sri Guru Nanak Dev",
    "2025-12-25": "Christmas",
    # 2026
    "2026-01-26": "Republic Day",
    "2026-03-03": "Holi",
    "2026-03-26": "Shri Ram Navami",
    "2026-03-31": "Shri Mahavir Jayanti",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-28": "Bakri Id",
    "2026-06-26": "Muharram",
    "2026-09-14": "Ganesh Chaturthi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Prakash Gurpurb Sri Guru Nanak Dev",
    "2026-12-25": "Christmas",
}


@dataclass(frozen=True)
class MarketStatus:
    """Snapshot of NSE equity market status in IST."""

    state: str  # "OPEN", "PRE-OPEN", or "CLOSED"
    reason: str
    now_ist: datetime
    next_open_ist: Optional[datetime]

    @property
    def is_open(self) -> bool:
        return self.state == "OPEN"

    @property
    def timestamp_str(self) -> str:
        return self.now_ist.strftime("%d %b %Y, %I:%M:%S %p IST")


def now_ist() -> datetime:
    """Return current timezone-aware datetime in IST."""
    return datetime.now(IST)


def is_nse_holiday(day: date) -> Optional[str]:
    """Return holiday name if `day` is a configured NSE holiday, else None."""
    return NSE_HOLIDAYS.get(day.isoformat())


def is_trading_day(day: date) -> bool:
    """Return True if `day` is Mon-Fri and not in NSE_HOLIDAYS."""
    return day.weekday() < 5 and is_nse_holiday(day) is None


def next_trading_open(reference_ist: datetime) -> datetime:
    """Compute the next NSE 9:15 AM IST market open from `reference_ist`."""
    candidate_date = reference_ist.date()
    if is_trading_day(candidate_date) and reference_ist.time() < NSE_OPEN_TIME:
        return datetime.combine(candidate_date, NSE_OPEN_TIME, tzinfo=IST)

    candidate_date += timedelta(days=1)
    while not is_trading_day(candidate_date):
        candidate_date += timedelta(days=1)
    return datetime.combine(candidate_date, NSE_OPEN_TIME, tzinfo=IST)


def get_market_status(current_dt: Optional[datetime] = None) -> MarketStatus:
    """Determine whether NSE is OPEN, PRE-OPEN, or CLOSED at `current_dt` (IST)."""
    dt = current_dt.astimezone(IST) if current_dt else now_ist()
    today = dt.date()
    holiday = is_nse_holiday(today)

    if today.weekday() >= 5:
        return MarketStatus(
            state="CLOSED",
            reason="Weekend (NSE closed Sat–Sun)",
            now_ist=dt,
            next_open_ist=next_trading_open(dt),
        )

    if holiday:
        return MarketStatus(
            state="CLOSED",
            reason=f"NSE Holiday — {holiday}",
            now_ist=dt,
            next_open_ist=next_trading_open(dt),
        )

    current_time = dt.time()
    if NSE_PREOPEN_START <= current_time < NSE_OPEN_TIME:
        return MarketStatus(
            state="PRE-OPEN",
            reason="Pre-open session (9:00–9:15 AM IST)",
            now_ist=dt,
            next_open_ist=datetime.combine(today, NSE_OPEN_TIME, tzinfo=IST),
        )

    if NSE_OPEN_TIME <= current_time <= NSE_CLOSE_TIME:
        return MarketStatus(
            state="OPEN",
            reason="Regular NSE session (9:15 AM–3:30 PM IST)",
            now_ist=dt,
            next_open_ist=None,
        )

    reason = (
        "Before market open (opens 9:15 AM IST)"
        if current_time < NSE_PREOPEN_START
        else "After market close (closed 3:30 PM IST)"
    )
    return MarketStatus(
        state="CLOSED",
        reason=reason,
        now_ist=dt,
        next_open_ist=next_trading_open(dt),
    )
