"""OpenTelemetry traces for the app, the worker and the mock customer API (spec F.1; OPS-02, ADR-0077).

- One tracer provider per process, set the first time `configure_process` runs; later calls reuse it.
- FastAPI and httpx spans come from the official instrumentations, database spans from two SQLAlchemy engine
  events (`instrument_engine`); W3C trace context travels on every
  httpx call (so the mock API's spans join the app's trace) and in the job row (so the worker's spans do too).
- Spans leave the process only through `ScrubbingExporter`, which drops URL query strings and GenAI content
  attributes and redacts secrets and personal data from every string attribute and event.
- With no `OTEL_EXPORTER_OTLP_ENDPOINT`, nothing is exported: spans still exist, so log lines carry trace IDs.
  `OTEL_SDK_DISABLED=true` turns the SDK off entirely (standard OpenTelemetry setting).
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app import __version__
from app.observability.genai import CONTENT_KEYS
from app.observability.scrub import scrub_attributes, scrub_text

APP, WORKER, MOCK_API = "loyalty-app", "loyalty-worker", "mock-customer-api"
HEALTH_ROUTES = "healthz,readyz"
_PROPAGATOR = TraceContextTextMapPropagator()
_lock = threading.Lock()
_provider: TracerProvider | None = None


def scrub_span(span: ReadableSpan) -> ReadableSpan:
    """A copy of the span with nothing sensitive in it. The original is never changed."""
    attributes = {k: v for k, v in scrub_attributes(span.attributes).items() if k not in CONTENT_KEYS}
    events = [
        Event(e.name, {k: v for k, v in scrub_attributes(e.attributes).items() if k not in CONTENT_KEYS}, e.timestamp)
        for e in span.events
    ]
    status = span.status
    if status.description:
        status = Status(status.status_code, scrub_text(status.description))
    return ReadableSpan(
        name=scrub_text(span.name),
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=attributes,
        events=events,
        links=span.links,
        kind=span.kind,
        status=status,
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class ScrubbingExporter(SpanExporter):
    """Wraps the real exporter, so no code path can export an unscrubbed span."""

    def __init__(self, inner: SpanExporter) -> None:
        self.inner = inner

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self.inner.export([scrub_span(s) for s in spans])

    def shutdown(self) -> None:
        self.inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.inner.force_flush(timeout_millis)


def add_exporter(provider: TracerProvider, exporter: SpanExporter, *, batch: bool = True) -> None:
    wrapped = ScrubbingExporter(exporter)
    provider.add_span_processor(BatchSpanProcessor(wrapped) if batch else SimpleSpanProcessor(wrapped))


def _otlp_configured(environ: Mapping[str, str]) -> bool:
    return bool(
        environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        or environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    )


def configure_process(service: str, environ: Mapping[str, str] | None = None) -> TracerProvider:
    """Set up tracing for this process once: provider, OTLP export if configured, httpx client spans."""
    global _provider
    environ = os.environ if environ is None else environ
    with _lock:
        if _provider is not None:
            return _provider
        resource = Resource.create(
            {
                "service.name": service,
                "service.version": __version__,
                "deployment.environment.name": environ.get("APP_PROFILE", "portfolio"),
            }
        )
        existing = trace.get_tracer_provider()
        if isinstance(existing, TracerProvider):  # set already in this process (tests run the mock API alongside)
            provider = existing
        else:
            provider = TracerProvider(resource=resource)
            if _otlp_configured(environ):
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                add_exporter(provider, OTLPSpanExporter())
            trace.set_tracer_provider(provider)
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        _provider = provider
        return provider


# ---------- database spans ----------
# The official SQLAlchemy instrumentation (0.66b2) supports SQLAlchemy < 2.1 only and instruments nothing on this
# project's 2.1.6 (found running the tests, ADR-0077). These two engine events do the small part we need: one CLIENT
# span per statement, with the statement's text (bound parameters are never read) and the operation name.
_SPAN_KEY = "_loyalty_otel_span"
TRANSACTION_CONTROL = frozenset({"BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE"})


def _before(conn: Any, _cursor: Any, statement: str, _params: Any, context: Any, _many: bool) -> None:
    operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "QUERY"
    if operation in TRANSACTION_CONTROL:  # SQLite's explicit BEGIN (database.py) would double every trace's length
        return
    if not trace.get_current_span().get_span_context().is_valid:
        # Only inside a request, a job or a model call. The worker polls for jobs every second; on the observability
        # profile each poll became a one-span trace named SELECT and buried the real ones (ADR-0080).
        return
    span = tracer("app.db").start_span(
        operation,
        kind=SpanKind.CLIENT,
        attributes={
            "db.system.name": conn.engine.dialect.name,
            "db.operation.name": operation,
            "db.query.text": scrub_text(statement)[:1000],
        },
    )
    context._loyalty_otel_span = span


def _after(_conn: Any, _cursor: Any, _statement: str, _params: Any, context: Any, _many: bool) -> None:
    span = getattr(context, _SPAN_KEY, None)
    if span is not None:
        span.end()


def _error(exception_context: Any) -> None:
    span = getattr(exception_context.execution_context, _SPAN_KEY, None)
    if span is not None:
        span.set_attribute("error.type", type(exception_context.original_exception).__name__)
        span.set_status(Status(StatusCode.ERROR))
        span.end()


def instrument_engine(engine: Any) -> None:
    from sqlalchemy import event

    if getattr(engine, "_loyalty_traced", False):
        return
    event.listen(engine, "before_cursor_execute", _before)
    event.listen(engine, "after_cursor_execute", _after)
    event.listen(engine, "handle_error", _error)
    engine._loyalty_traced = True


def instrument_fastapi(app: Any, provider: TracerProvider) -> None:
    """Server spans for one FastAPI app. Health and readiness probes are left out: they would drown the traces."""
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls=HEALTH_ROUTES, exclude_spans=["receive", "send"]
    )


def tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name, __version__)


def current_traceparent() -> str | None:
    """The W3C `traceparent` of the current span, to store with a job; None when there's no recording trace."""
    carrier: dict[str, str] = {}
    _PROPAGATOR.inject(carrier)
    value = carrier.get("traceparent")
    return value if value and len(value) <= 55 else None


@contextmanager
def continued(traceparent: str | None, name: str, **attributes: Any) -> Iterator[trace.Span]:
    """A consumer span that continues the trace stored with a job (or starts a new one when there is none)."""
    parent = _PROPAGATOR.extract({"traceparent": traceparent}) if traceparent else otel_context.Context()
    token = otel_context.attach(parent)
    try:
        with tracer("app.worker").start_as_current_span(name, kind=SpanKind.CONSUMER, attributes=attributes) as span:
            yield span
    finally:
        otel_context.detach(token)


def ids() -> tuple[str, str] | None:
    """(trace ID, span ID) of the current span, as hex, for log lines; None outside a valid span."""
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
