"""Business dates: timestamps are stored in UTC, and rules read them as the property's local date (spec Appendix B)."""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def parse_utc(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC)


def format_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def add_hours(timestamp: str, hours: int) -> str:
    return format_utc(parse_utc(timestamp) + timedelta(hours=hours))


def business_date(timestamp: str, timezone: str) -> date:
    return parse_utc(timestamp).astimezone(ZoneInfo(timezone)).date()


def add_months(day: date, months: int) -> date:
    """The same day of a later month, or that month's last day if it is shorter."""
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def local_datetime(timestamp: str, timezone: str) -> str:
    """A UTC time as a local clock shows it, with the zone named: `2026-07-01 23:30 EDT`."""
    return parse_utc(timestamp).astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M %Z")
