"""Operational gauges exported over OTLP, for the dashboards and alerts (spec F.1; OPS-03, OPS-04, SEC-20; ADR-0080).

The worker exports them, because it always runs and already holds a database connection. Each collection takes one
snapshot from the stored tables (`snapshot`), so the numbers mean the same as the console's `/metrics` page:

| Gauge | Unit | What |
|---|---|---|
| `loyalty.jobs.queued` | jobs | waiting or running |
| `loyalty.jobs.oldest_age` | s | the oldest job still waiting or running |
| `loyalty.jobs.dead` | jobs | gave up; a person decides |
| `loyalty.ai.spend` | USD | provider spend, by `period` (day, month), as the caps count it |
| `loyalty.ai.cap` | USD | the configured caps, by `period`, so an alert can compare |
| `loyalty.security.refusals` | events | refusals in the last 15 minutes, by `action` |
| `loyalty.protocol.calls` | calls | MCP and A2A calls in the last 15 minutes, by `protocol` |

Counts and money only: no label holds a username, case, member or text.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.business_time import format_utc, parse_utc
from app.persistence.models import Job, SystemEvent

WINDOW_MINUTES = 15
REFUSALS = ("sign_in_failed", "authorization_denied", "rate_limited", "csrf_failed")
PROTOCOL_CALLS = {"mcp_call": "mcp", "a2a_call": "a2a"}
MICRO = 1_000_000


def snapshot(s: Session, caps_usd: Mapping[str, float] | None = None, now: datetime | None = None) -> dict[str, Any]:
    from app.ai.harness import periods, spent_microusd
    from app.services import jobs

    moment = now or datetime.now(UTC)
    waiting = list(s.scalars(select(Job.created_at_utc).where(Job.status.in_((jobs.QUEUED, jobs.RUNNING)))))
    oldest = max(0.0, (moment - parse_utc(min(waiting))).total_seconds()) if waiting else 0.0
    dead = s.scalar(select(func.count(Job.id)).where(Job.status == jobs.DEAD)) or 0
    day, month = periods(moment)
    since = format_utc(moment - timedelta(minutes=WINDOW_MINUTES))
    rows = s.execute(
        select(SystemEvent.action, func.count(SystemEvent.id))
        .where(SystemEvent.at_utc >= since, SystemEvent.action.in_((*REFUSALS, *PROTOCOL_CALLS)))
        .group_by(SystemEvent.action)
    )
    recent = {action: count for action, count in rows}
    return {
        "jobs_queued": len(waiting),
        "jobs_oldest_age": round(oldest, 1),
        "jobs_dead": int(dead),
        "ai_spend": {"day": spent_microusd(s, day) / MICRO, "month": spent_microusd(s, month) / MICRO},
        "ai_cap": dict(caps_usd or {}),
        "refusals": {action: int(recent.get(action, 0)) for action in REFUSALS},
        "protocol_calls": {name: int(recent.get(action, 0)) for action, name in PROTOCOL_CALLS.items()},
    }


class _Cached:
    """One database snapshot per collection, however many gauges read it."""

    def __init__(self, take: Callable[[], dict[str, Any]], max_age_seconds: float = 5.0) -> None:
        self.take, self.max_age = take, max_age_seconds
        self._lock = threading.Lock()
        self._value: dict[str, Any] | None = None
        self._at = 0.0

    def get(self) -> dict[str, Any]:
        with self._lock:
            if self._value is None or time.monotonic() - self._at > self.max_age:
                try:
                    self._value = self.take()
                except Exception:  # a failed read must not stop the export; the gauges just skip this round
                    return {}
                self._at = time.monotonic()
            return self._value


def register(meter: Any, take: Callable[[], dict[str, Any]]) -> None:
    from opentelemetry.metrics import CallbackOptions, Observation

    cache = _Cached(take)

    def scalar(key: str) -> Callable[[CallbackOptions], Iterable[Observation]]:
        def callback(_options: CallbackOptions) -> Iterable[Observation]:
            value = cache.get().get(key)
            return [Observation(value)] if value is not None else []

        return callback

    def labelled(key: str, label: str) -> Callable[[CallbackOptions], Iterable[Observation]]:
        def callback(_options: CallbackOptions) -> Iterable[Observation]:
            return [Observation(v, {label: k}) for k, v in (cache.get().get(key) or {}).items()]

        return callback

    meter.create_observable_gauge("loyalty.jobs.queued", [scalar("jobs_queued")], unit="{job}")
    meter.create_observable_gauge("loyalty.jobs.oldest_age", [scalar("jobs_oldest_age")], unit="s")
    meter.create_observable_gauge("loyalty.jobs.dead", [scalar("jobs_dead")], unit="{job}")
    meter.create_observable_gauge("loyalty.ai.spend", [labelled("ai_spend", "period")], unit="USD")
    meter.create_observable_gauge("loyalty.ai.cap", [labelled("ai_cap", "period")], unit="USD")
    meter.create_observable_gauge("loyalty.security.refusals", [labelled("refusals", "action")], unit="{event}")
    meter.create_observable_gauge("loyalty.protocol.calls", [labelled("protocol_calls", "protocol")], unit="{call}")


def install(
    service: str, sessions: sessionmaker[Session] | None, caps_usd: Mapping[str, float], environ: Mapping[str, str]
) -> Any:
    """A meter provider exporting over OTLP, if an endpoint is set. The worker passes `sessions` to add the gauges;
    the app passes None and gets only the HTTP server metrics its instrumentation records. Returns the provider."""
    if not (environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()):
        return None
    from opentelemetry import metrics
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    from app import __version__

    interval = int(environ.get("OTEL_METRIC_EXPORT_INTERVAL", "15000"))
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=interval)
    resource = Resource.create({"service.name": service, "service.version": __version__})
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    if sessions is not None:

        def take() -> dict[str, Any]:
            with sessions() as s:
                return snapshot(s, caps_usd)

        register(provider.get_meter("app.ops"), take)
    else:
        register_up(provider.get_meter("app.ops"))
    return provider


def register_up(meter: Any) -> None:
    """`loyalty.app.up` = 1 while the app process runs. HTTP metrics exist only after the first request, so an idle
    app looked down to the "App not reporting" rule (found in the observability check, ADR-0080)."""
    from opentelemetry.metrics import CallbackOptions, Observation

    def up(_options: CallbackOptions) -> Iterable[Observation]:
        return [Observation(1)]

    meter.create_observable_gauge("loyalty.app.up", [up], unit="{process}")  # "1" would become _ratio


def caps_from(settings: Any) -> dict[str, float]:
    return {"day": float(settings.ai_budget_daily_usd), "month": float(settings.ai_budget_total_usd)}
