"""Traces and structured logs (OPS-02, LIVE-03, ADR-0077): the trace crosses app -> mock API -> worker, and nothing
sensitive reaches an exported span or a log line.

Planted values: an email, a phone number, a model key, a bearer token, a password in a URL and a query string. Each
test checks that the planted value itself is absent, not just that a redaction marker is present.
"""

from __future__ import annotations

import io
import json
import logging
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import correlation
from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.observability import genai, scrub, tracing
from app.observability.logs import JsonFormatter, ScrubbingFilter
from app.observability.model_calls import TracedProvider
from app.persistence.database import make_engine
from app.ports.model_provider import ModelTurn, ProviderUnavailable, Usage, UserMessage
from app.services import jobs
from app.worker import Worker
from mock_customer_api import telemetry as mock_telemetry
from tests.arm_a import SHAPE, ArmA, make_arm_a
from tests.conftest import ARM_A_TOKEN

EMAIL = "planted.person@mail.test"
PHONE = "+1 312 555 0147"
MODEL_KEY = "sk-ant-api03-plantedKEYvalue123456"
BEARER = "Bearer plantedtoken.abc.def"
DB_PASSWORD = "plantedPw99"
PLANTED = (EMAIL, "planted.person", PHONE, "555 0147", MODEL_KEY, "plantedtoken", DB_PASSWORD, "emailAddress=")


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    """Every span this process exports, through the same scrubbing exporter production uses."""
    provider = tracing.configure_process(tracing.APP)
    memory = InMemorySpanExporter()
    tracing.add_exporter(provider, memory, batch=False)
    yield memory
    memory.shutdown()  # a shut-down exporter ignores later spans; the provider keeps no other state from the test


def _everything(span: ReadableSpan) -> str:
    """All of a span as text: name, attributes, events, status."""
    parts: list[Any] = [span.name, dict(span.attributes or {}), span.status.description]
    parts += [(e.name, dict(e.attributes or {})) for e in span.events]
    return json.dumps(parts, default=str)


def _assert_clean(text: str) -> None:
    for value in PLANTED:
        assert value not in text, value


# ---------- the filter itself ----------


def test_scrub_removes_query_strings_and_redacts_secrets_and_personal_data() -> None:
    text = (
        f"GET http://mock:8020/v1/members?emailAddress={EMAIL}&familyName=Okafor failed for {PHONE}; "
        f"key {MODEL_KEY}; header {BEARER}; db postgresql+psycopg://loyalty_app:{DB_PASSWORD}@db:5432/loyalty; "
        f'"GET /v1/members?emailAddress={EMAIL} HTTP/1.1" 200'
    )
    out = scrub.scrub_text(text)
    _assert_clean(out)
    assert "Okafor" not in out  # the family name was only ever in the query string
    assert "http://mock:8020/v1/members" in out and "/v1/members?[removed]" in out


def test_url_attributes_keep_scheme_host_and_path_only() -> None:
    attrs = scrub.scrub_attributes(
        {
            "url.full": f"http://user:{DB_PASSWORD}@mock:8020/v1/members?emailAddress={EMAIL}",
            "http.target": f"/v1/members?emailAddress={EMAIL}",
            "url.query": f"emailAddress={EMAIL}",
            "http.response.status_code": 200,
        }
    )
    assert attrs == {
        "url.full": "http://mock:8020/v1/members",
        "http.target": "/v1/members",
        "url.query": "[removed]",
        "http.response.status_code": 200,
    }


def test_the_mock_api_filter_removes_the_same_planted_values_as_the_apps() -> None:
    """They're separate code on purpose (ADR-0040); this keeps them from drifting apart on what matters most."""
    line = f'"GET /v1/members?emailAddress={EMAIL}&phoneNumber=3125550147 HTTP/1.1" 200 contact {EMAIL}'
    for out in (scrub.scrub_text(line), mock_telemetry.scrub_text(line)):
        assert EMAIL not in out and "3125550147" not in out and "emailAddress=" not in out


# ---------- spans ----------


def test_an_exported_span_never_carries_planted_values_or_genai_content(spans: InMemorySpanExporter) -> None:
    with trace.get_tracer("test").start_as_current_span(f"lookup {EMAIL}") as span:
        span.set_attributes(
            {
                "url.full": f"http://mock:8020/v1/members?emailAddress={EMAIL}",
                "note": f"called with {BEARER} and {MODEL_KEY}",
                "gen_ai.input.messages": f"member {EMAIL} says points are missing",
                "gen_ai.output.messages": "the reply",
            }
        )
        span.add_event("retry", {"reason": f"timeout for {PHONE}"})
    (exported,) = spans.get_finished_spans()
    _assert_clean(_everything(exported))
    assert not genai.CONTENT_KEYS & set(exported.attributes or {})


@contextmanager
def _real_mock_api(arm: ArmA) -> Iterator[str]:
    """The arm's mock API on a real local socket: TestClient's transport isn't the one httpx's instrumentation
    patches, and production calls go through httpx's own transport."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(arm.mock_client.app, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_one_trace_crosses_the_app_and_the_mock_api_and_drops_the_lookup_query(
    arm: ArmA, spans: InMemorySpanExporter
) -> None:
    assert HTTPXClientInstrumentor().is_instrumented_by_opentelemetry  # configure_process did it, for every client
    raw = InMemorySpanExporter()  # unscrubbed, never exported: proves the filter is what keeps the email out
    tracing.configure_process(tracing.APP).add_span_processor(SimpleSpanProcessor(raw))
    with _real_mock_api(arm) as base, httpx.Client(base_url=base, timeout=10) as client:
        adapter = MockCustomerApiAdapter(base, ARM_A_TOKEN, SHAPE, client=client, sleep=lambda _: None)
        with trace.get_tracer("test").start_as_current_span("investigation") as root:
            adapter.find_members(email=EMAIL)
            trace_id = root.get_span_context().trace_id
    finished = [s for s in spans.get_finished_spans() if s.context.trace_id == trace_id]
    kinds = {s.kind for s in finished}
    assert {SpanKind.INTERNAL, SpanKind.CLIENT, SpanKind.SERVER} <= kinds, [(s.name, s.kind) for s in finished]
    client_span = next(s for s in finished if s.kind == SpanKind.CLIENT)
    server_span = next(s for s in finished if s.kind == SpanKind.SERVER)
    assert server_span.parent is not None and server_span.parent.span_id == client_span.context.span_id
    for span in finished:
        _assert_clean(_everything(span))
    unscrubbed = " ".join(_everything(s) for s in raw.get_finished_spans() if s.context.trace_id == trace_id)
    raw.shutdown()
    assert "emailAddress=" in unscrubbed  # the instrumentation does record the query; the exporter removes it


def test_a_job_continues_the_trace_it_was_queued_under(arm: ArmA, spans: InMemorySpanExporter) -> None:
    seen: list[str | None] = []

    def probe(_s: Any, job: jobs.ClaimedJob) -> None:
        seen.append(job.trace_parent)
        assert trace.get_current_span().get_span_context().trace_id == queued_under

    with trace.get_tracer("test").start_as_current_span("intake") as root, arm.sessions() as s:
        queued_under = root.get_span_context().trace_id
        jobs.enqueue(s, "probe", {})
        s.commit()
    assert Worker(arm.sessions, {"probe": probe}).drain() == 1
    assert seen and seen[0] is not None and format(queued_under, "032x") in seen[0]
    consumer = [s for s in spans.get_finished_spans() if s.kind == SpanKind.CONSUMER]
    assert consumer and consumer[-1].name == "job probe" and consumer[-1].context.trace_id == queued_under


def test_a_job_queued_outside_any_trace_still_runs_and_starts_its_own() -> None:
    assert tracing.current_traceparent() is None or trace.get_current_span().get_span_context().is_valid
    with tracing.continued(None, "job probe") as span:
        assert span.get_span_context().is_valid


def test_database_statements_get_spans_without_their_parameters(spans: InMemorySpanExporter) -> None:
    engine = make_engine("sqlite://")
    tracing.instrument_engine(engine)
    tracing.instrument_engine(engine)  # twice is harmless: one span per statement, not two
    with trace.get_tracer("test").start_as_current_span("request") as root, engine.connect() as conn:
        conn.execute(text("SELECT :email AS e"), {"email": EMAIL})
        with pytest.raises(OperationalError):
            conn.execute(text("SELECT * FROM no_such_table WHERE x = :p"), {"p": PHONE})
        trace_id = root.get_span_context().trace_id
    db = [s for s in spans.get_finished_spans() if s.context.trace_id == trace_id and s.kind == SpanKind.CLIENT]
    assert [s.name for s in db] == ["SELECT", "SELECT"]
    ok, failed = db
    assert dict(ok.attributes or {})["db.system.name"] == "sqlite"
    assert dict(ok.attributes or {})["db.query.text"] == "SELECT ? AS e"
    assert dict(failed.attributes or {})["error.type"] == "OperationalError"
    for span in db:
        _assert_clean(_everything(span))


def test_a_statement_outside_any_trace_gets_no_span(spans: InMemorySpanExporter) -> None:
    """The worker's once-a-second job poll would otherwise be a one-span trace each time (found on the
    observability profile, ADR-0080)."""
    engine = make_engine("sqlite://")
    tracing.instrument_engine(engine)
    before = len(spans.get_finished_spans())
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    assert len(spans.get_finished_spans()) == before


# ---------- GenAI attributes ----------


class _Model:
    name, model_id, is_mock = "mock", "mock-model-1", True

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def complete(self, *_a: Any, **_k: Any) -> ModelTurn:
        if self.fail:
            raise ProviderUnavailable(f"overloaded while reading {EMAIL}")
        return ModelTurn("end_turn", text=f"reply mentioning {EMAIL}", usage=Usage(1200, 340))

    def read_image(self, *_a: Any, **_k: Any) -> tuple[dict[str, str | None], Usage]:
        return {"field": EMAIL}, Usage(800, 20)


def test_model_calls_get_genai_attributes_and_no_content(spans: InMemorySpanExporter) -> None:
    TracedProvider(_Model(), case_id=7, cost=lambda _t: 4321).complete("system", [UserMessage(EMAIL)], [], 512, 30)
    (span,) = [s for s in spans.get_finished_spans() if s.name == "chat mock-model-1"]
    attrs = dict(span.attributes or {})
    assert span.kind == SpanKind.CLIENT
    assert attrs[genai.OPERATION_NAME] == "chat"
    assert attrs[genai.PROVIDER_NAME] == "loyalty.mock"
    assert attrs[genai.REQUEST_MODEL] == "mock-model-1"
    assert attrs[genai.INPUT_TOKENS] == 1200 and attrs[genai.OUTPUT_TOKENS] == 340
    assert tuple(attrs[genai.FINISH_REASONS]) == ("end_turn",)
    assert attrs[genai.COST_MICROUSD] == 4321 and attrs[genai.CASE_ID] == 7
    _assert_clean(_everything(span))


def test_a_failed_model_call_records_the_error_type_not_its_message(spans: InMemorySpanExporter) -> None:
    with pytest.raises(ProviderUnavailable):
        TracedProvider(_Model(fail=True)).complete("system", [], [], 512, 30)
    (span,) = [s for s in spans.get_finished_spans() if s.name == "chat mock-model-1"]
    assert dict(span.attributes or {})["error.type"] == "ProviderUnavailable"
    assert not span.events  # no exception event: its message can quote the request
    _assert_clean(_everything(span))


def test_every_genai_attribute_name_lives_in_one_module() -> None:
    """L2: the conventions are in Development, so a rename must be a one-file change."""
    root = Path(__file__).resolve().parent.parent
    offenders = [
        str(path.relative_to(root))
        for folder in ("app", "protocols")
        for path in (root / folder).rglob("*.py")
        if path.name != "genai.py" and '"gen_ai.' in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


# ---------- logs ----------


def _json_logger() -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ScrubbingFilter())
    handler.setFormatter(JsonFormatter(tracing.APP))
    logger = logging.getLogger(f"test.observability.{id(stream)}")
    logger.handlers, logger.propagate, logger.level = [handler], False, logging.INFO
    return logger, stream


def test_a_log_line_is_json_with_correlation_and_trace_ids_and_nothing_planted(spans: InMemorySpanExporter) -> None:
    logger, stream = _json_logger()
    with correlation.correlated("c0ffee"), trace.get_tracer("test").start_as_current_span("request") as span:
        logger.warning("lookup for %s with %s failed: %s", EMAIL, BEARER, f"password={DB_PASSWORD}")
        ids = (format(span.get_span_context().trace_id, "032x"), format(span.get_span_context().span_id, "016x"))
    line = json.loads(stream.getvalue())
    assert line["level"] == "WARNING" and line["service"] == "loyalty-app" and line["ts"].endswith("Z")
    assert line["correlation_id"] == "c0ffee"
    assert (line["trace_id"], line["span_id"]) == ids
    _assert_clean(stream.getvalue())


def test_an_exception_is_logged_as_a_scrubbed_traceback() -> None:
    logger, stream = _json_logger()
    try:
        raise ValueError(f"no member for {EMAIL} at postgresql://u:{DB_PASSWORD}@db/x")
    except ValueError:
        logger.exception("investigation failed")
    line = json.loads(stream.getvalue())
    assert "ValueError" in line["exception"]
    _assert_clean(stream.getvalue())


def test_the_mock_api_log_filter_scrubs_its_access_log_line() -> None:
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', None, None)
    record.args = ("127.0.0.1:5000", "GET", f"/v1/members?emailAddress={EMAIL}", "1.1", 200)
    mock_telemetry._Filter().filter(record)
    assert EMAIL not in record.getMessage() and "/v1/members?[removed]" in record.getMessage()


def test_configure_process_returns_one_provider_per_process() -> None:
    first = tracing.configure_process(tracing.APP)
    assert tracing.configure_process(tracing.WORKER) is first
    assert isinstance(trace.get_tracer_provider(), TracerProvider)
