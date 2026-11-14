"""Structured JSON logs with correlation and trace IDs, scrubbed before they're written (spec F.1; OPS-02).

`configure_logging` is called only by the process entry points (`app.main:serve`, the worker, the mock API's
`serve`), never by `create_app`, so tests keep pytest's own log capture. Every record passes `ScrubbingFilter` first:
the message is formatted, scrubbed (`app.observability.scrub`) and frozen, so arguments can't bring a secret back.
Exceptions are logged as their type and a scrubbed traceback.

    LOG_FORMAT=json (default) | text        LOG_LEVEL=INFO (default)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app import correlation
from app.observability import tracing
from app.observability.scrub import scrub_text

# Loggers whose own handlers would bypass the filter; they're pointed at the root handler instead.
SERVER_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def utc_timestamp(record: logging.LogRecord) -> str:
    return datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ScrubbingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "_scrubbed", False):
            record.msg = scrub_text(record.getMessage())
            record.args = None
            if record.exc_info:
                record.exc_text = scrub_text(logging.Formatter().formatException(record.exc_info))
                record.exc_info = None
            record._scrubbed = True
        return True


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": utc_timestamp(record),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": scrub_text(record.getMessage()),
        }
        if correlation_id := correlation.current():
            line["correlation_id"] = correlation_id
        if trace_ids := tracing.ids():
            line["trace_id"], line["span_id"] = trace_ids
        if record.exc_text:
            line["exception"] = scrub_text(record.exc_text)
        return json.dumps(line, ensure_ascii=False)


def configure_logging(service: str, environ: Mapping[str, str] | None = None) -> logging.Handler:
    environ = os.environ if environ is None else environ
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ScrubbingFilter())
    if environ.get("LOG_FORMAT", "json").strip().lower() == "text":
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    for old in list(root.handlers):
        root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO")
    for name in SERVER_LOGGERS:
        server = logging.getLogger(name)
        server.handlers.clear()
        server.propagate = True
    return handler
