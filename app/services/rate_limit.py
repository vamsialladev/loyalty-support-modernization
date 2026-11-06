"""Rate limits kept in the database, so every web process shares them and a restart doesn't reset them (SEC-07, C.8).

A fixed window: simple to reason about, and it lets a short burst through at a window's edge, which is fine for these
limits. The client address comes from the socket. Behind a proxy it must be set from a trusted header
(`docs/known-limitations.md`).
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import Table, case, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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


def _count_one(s: Session, key: str, window_start: int) -> int:
    """Add one hit in a single statement, and return the new count.

    It's the first statement of its transaction, so no request holds a read lock while it waits to write. On SQLite,
    those requests would wait on each other until the timeout. Postgres locks the row, so every hit is counted.
    """
    table = cast(Table, RateLimit.__table__)
    insert: Any = postgres_insert if s.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(table).values(key=key, window_start=window_start, hits=1)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.key],
        set_={
            "hits": case((table.c.window_start == window_start, table.c.hits + 1), else_=1),
            "window_start": window_start,
        },
    )
    return int(s.execute(statement.returning(table.c.hits)).scalar_one())


def hit(s: Session, key: str, limit: int, window_seconds: int, clock: Callable[[], float] = _now) -> None:
    """Count one request, in a transaction of its own. Raises once the limit is passed."""
    now = int(clock())
    window_start = now - now % window_seconds
    s.commit()  # ends whatever the request read first
    hits = _count_one(s, key, window_start)
    s.commit()
    if hits > limit:
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
    s.commit()  # a write first, as in `hit`
    s.execute(update(RateLimit).where(RateLimit.key == f"login-account:{username.strip().lower()[:64]}").values(hits=0))
    s.commit()
