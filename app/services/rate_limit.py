"""Rate limits kept in the database, so every web process shares them and a restart doesn't reset them (SEC-07, C.8).

A fixed window: simple to reason about, and it lets a short burst through at a window's edge, which is fine for these
limits. The client address comes from the socket. Behind a proxy it must be set from a trusted header
(`docs/known-limitations.md`).
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.persistence.models import RateLimit

LOGIN_FAILURES_PER_ACCOUNT = 5
LOGIN_FAILURES_PER_ADDRESS = 30
LOGIN_WINDOW_SECONDS = 300
REQUESTS_PER_MINUTE = 600


def _now() -> float:
    return time.time()


class RateLimited(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("too many requests")
        self.retry_after_seconds = retry_after_seconds


def _row(s: Session, key: str, window_start: int) -> RateLimit:
    query = select(RateLimit).where(RateLimit.key == key).with_for_update(key_share=True)
    row = s.scalars(query.execution_options(populate_existing=True)).first()
    if row is None:
        try:
            with s.begin_nested():
                s.add(RateLimit(key=key, window_start=window_start, hits=0))
        except IntegrityError:
            pass  # another request added it first
        row = s.scalars(query.execution_options(populate_existing=True)).one()
    return row


def _current(row: RateLimit, window_start: int) -> None:
    if row.window_start != window_start:
        row.window_start, row.hits = window_start, 0


def hit(s: Session, key: str, limit: int, window_seconds: int, clock: Callable[[], float] = _now) -> None:
    """Count one request, in a transaction of its own. Raises once the limit is passed."""
    now = int(clock())
    window_start = now - now % window_seconds
    row = _row(s, key, window_start)
    _current(row, window_start)
    row.hits += 1
    over = row.hits > limit
    s.commit()
    if over:
        raise RateLimited(window_start + window_seconds - now)


def check(s: Session, key: str, limit: int, window_seconds: int, clock: Callable[[], float] = _now) -> None:
    """Refuse if this key is already at its limit, without counting. For login: only failures count."""
    now = int(clock())
    window_start = now - now % window_seconds
    row = s.get(RateLimit, key, populate_existing=True)
    over = row is not None and row.window_start == window_start and row.hits >= limit
    s.commit()
    if over:
        raise RateLimited(window_start + window_seconds - now)


def login_keys(username: str, address: str) -> tuple[tuple[str, int], tuple[str, int]]:
    return (
        (f"login-account:{username.strip().lower()[:64]}", LOGIN_FAILURES_PER_ACCOUNT),
        (f"login-address:{address[:64]}", LOGIN_FAILURES_PER_ADDRESS),
    )


def check_login(s: Session, username: str, address: str, clock: Callable[[], float] = _now) -> None:
    for key, limit in login_keys(username, address):
        check(s, key, limit, LOGIN_WINDOW_SECONDS, clock)


def record_login_failure(s: Session, username: str, address: str, clock: Callable[[], float] = _now) -> None:
    for key, limit in login_keys(username, address):
        with contextlib.suppress(RateLimited):  # the next attempt is refused by check_login
            hit(s, key, limit, LOGIN_WINDOW_SECONDS, clock)


def clear_login_failures(s: Session, username: str) -> None:
    row = s.get(RateLimit, f"login-account:{username.strip().lower()[:64]}")
    if row is not None:
        row.hits = 0
        s.commit()
