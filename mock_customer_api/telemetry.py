"""Traces and logs for the mock customer API (OPS-02, ADR-0077).

The mock API stands for the customer's own system, so it shares no code with the app (ADR-0040). That is why this
small module repeats the app's two rules instead of importing them: **query strings never leave the process** (the
app looks members up by email and name in the query string) and **email addresses are masked**. A test runs the
same planted values through both, so they can't drift apart (`tests/test_observability.py`).

It continues the app's trace from the W3C `traceparent` header; `uvicorn --factory mock_customer_api.api:serve` turns
on JSON logs. With no `OTEL_EXPORTER_OTLP_ENDPOINT`, nothing is exported.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult

SERVICE = "mock-customer-api"
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_QUERY = re.compile(r"(?<=[\w/])\?[^\s\"'<>]*")
_URL_KEYS = frozenset({"http.url", "url.full", "http.target"})
_provider: TracerProvider | None = None


def scrub_text(text: str) -> str:
    return _EMAIL.sub("[email]", _QUERY.sub("?[removed]", text))[:2000]


def _scrub(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in (attributes or {}).items():
        if key == "url.query":
            continue
        if isinstance(value, str):
            value = value.split("?", 1)[0] if key in _URL_KEYS else scrub_text(value)
        out[key] = value
    return out


class ScrubbingExporter(SpanExporter):
    def __init__(self, inner: SpanExporter) -> None:
        self.inner = inner

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        clean = [
            ReadableSpan(
                name=scrub_text(s.name),
                context=s.context,
                parent=s.parent,
                resource=s.resource,
                attributes=_scrub(s.attributes),
                events=[Event(e.name, _scrub(e.attributes), e.timestamp) for e in s.events],
                links=s.links,
                kind=s.kind,
                status=s.status,
                start_time=s.start_time,
                end_time=s.end_time,
                instrumentation_scope=s.instrumentation_scope,
            )
            for s in spans
        ]
        return self.inner.export(clean)

    def shutdown(self) -> None:
        self.inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.inner.force_flush(timeout_millis)


def provider(environ: Mapping[str, str] | None = None) -> TracerProvider:
    """This process's provider. Uses the global one if the app's tests already set it (both run in one process)."""
    global _provider
    if _provider is None:
        environ = os.environ if environ is None else environ
        current = trace.get_tracer_provider()
        if isinstance(current, TracerProvider):
            _provider = current
        else:
            _provider = TracerProvider(resource=Resource.create({"service.name": SERVICE}))
            if environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                _provider.add_span_processor(BatchSpanProcessor(ScrubbingExporter(OTLPSpanExporter())))
            trace.set_tracer_provider(_provider)
    return _provider


def add_exporter(target: TracerProvider, exporter: SpanExporter) -> None:
    target.add_span_processor(SimpleSpanProcessor(ScrubbingExporter(exporter)))


def instrument(app: Any) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider(), excluded_urls="healthz,readyz", exclude_spans=["receive", "send"]
    )


class _Filter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg, record.args = scrub_text(record.getMessage()), None
        if record.exc_info:
            record.exc_text = scrub_text(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


class _Json(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "service": SERVICE,
            "logger": record.name,
            "message": record.getMessage(),
        }
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            line["trace_id"], line["span_id"] = format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
        if record.exc_text:
            line["exception"] = record.exc_text
        return json.dumps(line, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_Filter())
    handler.setFormatter(_Json())
    root = logging.getLogger()
    for old in list(root.handlers):
        root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO")
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
