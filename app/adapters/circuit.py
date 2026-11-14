"""A circuit breaker for calls to a dependency that is failing (spec F.1; OPS-05, ADR-0081).

Where it's justified: the customer systems and the model provider. Both already retry transient errors a bounded
number of times; when either is down, every case would still spend its retries and its timeout before giving up. The
breaker notices repeated failures and fails the next calls at once, so the queue moves to the manual fallback quickly
and the dependency isn't hammered while it recovers.

    closed ──(N failures within the window)──▶ open ──(cooldown)──▶ half-open ──(trial succeeds)──▶ closed
                                                 ▲                       │
                                                 └───(trial fails)───────┘

One breaker per dependency per process (`breaker_for`), shared by every adapter instance in that process. A breaker
never opens on a healthy answer: "not found", "conflict" and other 4xx are the dependency working.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    window_seconds: float = 30.0
    cooldown_seconds: float = 30.0
    clock: Callable[[], float] = time.monotonic
    _failures: deque[float] = field(default_factory=deque, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)
    _trial: bool = field(default=False, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def state(self) -> str:
        with self._lock:
            return self._state()

    def _state(self) -> str:
        if self._opened_at is None:
            return CLOSED
        return HALF_OPEN if self.clock() - self._opened_at >= self.cooldown_seconds else OPEN

    def allow(self) -> bool:
        """May a call go out now? In half-open, exactly one trial call goes out; the rest wait for its result."""
        with self._lock:
            state = self._state()
            if state == CLOSED:
                return True
            if state == HALF_OPEN and not self._trial:
                self._trial = True
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures.clear()
            self._opened_at, self._trial = None, False

    def record_failure(self) -> None:
        with self._lock:
            now = self.clock()
            if self._state() == HALF_OPEN:  # the trial failed: open again for another cooldown
                self._opened_at, self._trial = now, False
                return
            self._failures.append(now)
            while self._failures and now - self._failures[0] > self.window_seconds:
                self._failures.popleft()
            if len(self._failures) >= self.failure_threshold:
                self._opened_at, self._trial = now, False
                self._failures.clear()

    def retry_after_seconds(self) -> float:
        with self._lock:
            if self._opened_at is None:
                return 0.0
            return max(0.0, self.cooldown_seconds - (self.clock() - self._opened_at))


_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def breaker_for(name: str) -> CircuitBreaker:
    """The process-wide breaker for one dependency (for example `customer_api:http://mock-api:8020`)."""
    with _registry_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name)
        return _breakers[name]


class GuardedModel:
    """A model provider behind a breaker (ADR-0081). An outage (`ProviderUnavailable`) counts; a refusal of the request
    itself (`ProviderRejected`: a bad key, an unknown model) doesn't, because the provider answered. While the breaker
    is open, calls fail at once with `ProviderUnavailable`, which the loop already turns into the manual fallback."""

    def __init__(self, inner: Any, breaker: CircuitBreaker) -> None:
        self.inner, self.breaker = inner, breaker
        self.name, self.model_id, self.is_mock = inner.name, inner.model_id, inner.is_mock

    def _call(self, fn: Callable[[], Any]) -> Any:
        from app.ports.model_provider import ProviderUnavailable

        if not self.breaker.allow():
            raise ProviderUnavailable("the model provider is failing; calls are paused (circuit open)")
        try:
            result = fn()
        except ProviderUnavailable:
            self.breaker.record_failure()
            raise
        except Exception:  # the provider answered, if only to refuse: it's up (and a half-open trial must end)
            self.breaker.record_success()
            raise
        self.breaker.record_success()
        return result

    def complete(self, system: str, messages: Any, tools: Any, max_tokens: int, timeout_seconds: float) -> Any:
        return self._call(lambda: self.inner.complete(system, messages, tools, max_tokens, timeout_seconds))

    def read_image(self, media_type: str, content: bytes, timeout_seconds: float) -> Any:
        return self._call(lambda: self.inner.read_image(media_type, content, timeout_seconds))
