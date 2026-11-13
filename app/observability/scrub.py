"""One filter for secrets and personal data, used by both logs and traces (OPS-02, SEC-05).

Reuses the two existing filters, so there is one definition of "sensitive": `app.ai.redaction.redact` (emails, cards,
phones, model keys, bearer tokens) and the readiness check's `mask_secrets` shape (passwords in URLs, `token=...`).
Query strings are dropped from URLs entirely, because the customer-API adapter looks members up by email and name in
the query string (found while adding HTTP client spans, ADR-0077).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.ai.redaction import redact

_URL_PASSWORD = re.compile(r"(://[^:/\s]+:)[^@\s]+@")
_NAMED_SECRET = re.compile(r"(?i)((?:password|passwd|token|secret|api[_-]?key)[\"']?\s*[=:]\s*[\"']?)[^\s\"',&]+")
_URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>]+")
# A query string on a bare path, as in an access-log line: `"GET /v1/members?email=... HTTP/1.1"`.
_PATH_QUERY = re.compile(r"(?<=[\w/])\?[^\s\"'<>]+")
# Span attributes that carry a URL or a query; the query is removed, not redacted.
URL_KEYS = frozenset({"http.url", "url.full", "http.target", "url.query", "http.request.url"})
MAX_TEXT = 2000


def strip_query(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[url]"
    if not parts.scheme and not parts.netloc:  # a target like "/v1/members?email=..."
        return url.split("?", 1)[0]
    return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))


def scrub_text(text: str) -> str:
    text = _URL_IN_TEXT.sub(lambda m: strip_query(m.group(0)), text)
    text = _PATH_QUERY.sub("?[removed]", text)
    text = _NAMED_SECRET.sub(r"\1***", _URL_PASSWORD.sub(r"\1***@", text))
    return redact(text)[:MAX_TEXT]


def scrub_value(key: str, value: Any) -> Any:
    if key == "url.query":
        return "[removed]"
    if isinstance(value, str):
        return strip_query(value) if key in URL_KEYS else scrub_text(value)
    if isinstance(value, tuple | list):
        return tuple(scrub_value(key, v) for v in value)
    return value


def scrub_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    return {k: scrub_value(k, v) for k, v in (attributes or {}).items()}
