"""Time helpers: everything is stored in UTC; business dates are taken in the property's time zone."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

EASTERN = "America/New_York"


def to_utc(day: date, hour: int, minute: int, tz: str = EASTERN) -> datetime:
    """A local wall-clock time on `day` in `tz`, converted to an aware UTC datetime."""
    local = datetime.combine(day, time(hour, minute), tzinfo=ZoneInfo(tz))
    return local.astimezone(UTC)


def business_date(ts: datetime, tz: str = EASTERN) -> date:
    """The local calendar date of a UTC timestamp in `tz` (the date the policy uses)."""
    return ts.astimezone(ZoneInfo(tz)).date()


def utc_date(ts: datetime) -> date:
    """The UTC calendar date (what the legacy tool wrongly uses, defect D04)."""
    return ts.astimezone(UTC).date()


def add_months(day: date, months: int) -> date:
    """Calendar month arithmetic, clamping the day (e.g. 31 Jan + 1 month = 28/29 Feb)."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    for candidate in (day.day, 30, 29, 28):
        try:
            return date(year, month, min(day.day, candidate))
        except ValueError:
            continue
    raise ValueError(f"cannot add {months} months to {day}")


def daterange(start: date, end: date) -> list[date]:
    """Inclusive list of dates."""
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def iso(ts: datetime) -> str:
    """Canonical UTC timestamp text, e.g. 2026-08-11T00:30:00Z."""
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
