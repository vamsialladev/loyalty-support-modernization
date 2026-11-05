"""A correlation ID that follows one piece of work: web request, job, case events, upstream calls (spec B.12)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_current: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def current() -> str | None:
    return _current.get()


def new_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def correlated(correlation_id: str | None) -> Iterator[None]:
    token = _current.set(correlation_id)
    try:
        yield
    finally:
        _current.reset(token)
