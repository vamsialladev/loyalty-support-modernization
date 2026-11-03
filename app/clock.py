"""Wall-clock time for audit and instrumentation, as UTC text. Business dates come from the case, never from here."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_precise() -> str:
    """With milliseconds: scripted step timings need more than whole seconds."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
