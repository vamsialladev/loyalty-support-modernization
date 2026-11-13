"""AG-UI 1.0 inside the console (spec G.5, G.13; PROTO-05; threat T25).

The endpoint is driven over HTTP as a signed-in console user, and the SSE body is parsed as a frontend would. Every
event must be a standard AG-UI 1.0 type; nothing private may appear; reconnects and resends must not start a second
investigation. The independent client (`@ag-ui/client`) is in `docs/protocol-test-results.md`.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from ag_ui.core import EventType
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import create_app
from app.persistence.models import AiRun, Case, CaseEvent, Job
from app.services import assisted, conventional
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath
from app.settings import AppSettings
from app.worker import Worker
from benchmarks.intake import load_case, read_split
from protocols.ag_ui.routes import install_ag_ui
from tests.arm_a import ArmA, Browser, make_arm_a

PRIVATE = ("REASONING", "THINKING", "TOOL_CALL_ARGS", "TOOL_CALL_RESULT")


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def load_c(arm: ArmA) -> int:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == arm.scenario("K01"))
    with arm.sessions() as s:
        return load_case(s, item, arm="C")[0].id


def work(arm: ArmA) -> None:
    Worker(arm.sessions, build_handlers(SharedWritePath("hg-demo"), arm.factory(), assisted.mock_runtime())).drain()


def investigated(arm: ArmA) -> int:
    cid = load_c(arm)
    with arm.sessions() as s:
        conventional.start_investigation(s, arm.who("agent.ana"), s.get(Case, cid))  # type: ignore[arg-type]
    work(arm)
    return cid


def browser(arm: ArmA, user: str = "agent.ana", watch_seconds: float = 2.0) -> Browser:
    app = create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory())
    install_ag_ui(app, AppSettings(database_url=arm.app_url), poll_seconds=0.05, watch_seconds=watch_seconds)
    b = Browser(TestClient(app))
    b.login(user, arm.password, landing="" if user != "agent.ana" else "Points queue")
    return b


def reference(arm: ArmA, case_id: int) -> str:
    with arm.sessions() as s:
        return s.get(Case, case_id).reference  # type: ignore[union-attr]


def run_input(thread: str, run_id: str | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "threadId": thread,
        "runId": run_id or uuid.uuid4().hex,
        "messages": [],
        "tools": [],
        "context": [],
        **extra,
    }


def stream(b: Browser, case_id: int, body: dict[str, Any], csrf: bool = False) -> tuple[int, list[dict[str, Any]]]:
    headers = {"Accept": "text/event-stream"}
    if csrf:
        headers["X-CSRF-Token"] = b.csrf
    resp = b.client.post(f"/ag-ui/cases/{case_id}/runs", json=body, headers=headers)
    if resp.status_code != 200:
        return resp.status_code, []
    assert resp.headers["content-type"].startswith("text/event-stream")
    data = [line[len("data: ") :] for line in resp.text.splitlines() if line.startswith("data: ")]
    return 200, [json.loads(d) for d in data]


def jobs_for(arm: ArmA, case_id: int) -> int:
    with arm.sessions() as s:
        return int(s.scalar(select(func.count()).select_from(Job).where(Job.case_id == case_id)) or 0)


# ---------- what the stream shows ----------


def test_watching_a_finished_run_replays_it_in_standard_events(arm: ArmA) -> None:
    cid = investigated(arm)
    thread = reference(arm, cid)
    status, evs = stream(browser(arm), cid, run_input(thread, "run-1"))
    types = [e["type"] for e in evs]
    assert status == 200
    assert types[0] == "RUN_STARTED" and evs[0]["threadId"] == thread and evs[0]["runId"] == "run-1"
    assert types[1] == "STATE_SNAPSHOT" and types[-1] == "RUN_FINISHED"
    assert all(EventType(t) for t in types)  # every one is an AG-UI 1.0 event type: nothing invented
    with arm.sessions() as s:
        run = s.scalars(select(AiRun).where(AiRun.case_id == cid)).one()
        tool_steps = run.tool_calls
    starts = [e for e in evs if e["type"] == "TOOL_CALL_START"]
    assert tool_steps >= 1  # the mock run on K01 calls tools, so this can't pass on an empty stream
    assert len(starts) == tool_steps and len(starts) == types.count("TOOL_CALL_END")
    assert all(len(e["metadata"]["arguments_sha256"]) == 64 for e in starts)
    assert evs[-1]["result"]["approval"] == "on the case page, by a supervisor"


def test_nothing_private_is_streamed(arm: ArmA) -> None:
    cid = investigated(arm)
    _, evs = stream(browser(arm), cid, run_input(reference(arm, cid)))
    assert not [e for e in evs if e["type"].startswith(PRIVATE)]
    text = json.dumps(evs)
    with arm.sessions() as s:
        rec = conventional.latest_recommendation(s, s.get(Case, cid))  # type: ignore[arg-type]
        assert rec is not None and rec.member_number
        member = arm.systems().get_member(rec.member_number)
    for private in (member.last_name, member.email or "@@", rec.member_number, "prompt", "cost_microusd", "token"):
        assert private not in text, private
    snapshot = next(e for e in evs if e["type"] == "STATE_SNAPSHOT")["snapshot"]
    assert set(snapshot) == {"case", "run", "engine"} and set(snapshot["case"]) == {"reference", "status", "arm"}


def test_the_summary_is_the_text_staff_already_see(arm: ArmA) -> None:
    cid = investigated(arm)
    _, evs = stream(browser(arm), cid, run_input(reference(arm, cid)))
    with arm.sessions() as s:
        rec = conventional.latest_recommendation(s, s.get(Case, cid))  # type: ignore[arg-type]
    content = [e["delta"] for e in evs if e["type"] == "TEXT_MESSAGE_CONTENT"]
    assert rec is not None and rec.ai and rec.ai["summary"]  # the K01 mock run is accepted and has a summary
    assert content == [rec.ai["summary"]]


# ---------- who may watch or start ----------


def test_watching_needs_a_console_session(arm: ArmA) -> None:
    cid = investigated(arm)
    b = browser(arm)
    b.client.cookies.clear()
    assert stream(b, cid, run_input(reference(arm, cid)))[0] == 401


def test_another_customers_case_is_not_found(arm: ArmA) -> None:
    cid = investigated(arm)
    thread = reference(arm, cid)
    with arm.sessions() as s:
        s.get(Case, cid).customer_id = "cedarpoint"  # type: ignore[union-attr]
        s.commit()
    assert stream(browser(arm), cid, run_input(thread))[0] == 404


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"threadId": "WRONG", "runId": "r", "messages": [], "tools": [], "context": []}, 422),
        ({"runId": "r"}, 422),
        ({"threadId": "{ref}", "runId": "r", "messages": [], "tools": [], "context": [], "approve": True}, 422),
        ("not an object", 422),
    ],
)
def test_inbound_input_is_validated(arm: ArmA, body: Any, status: int) -> None:
    cid = investigated(arm)
    if isinstance(body, dict) and body.get("threadId") == "{ref}":
        body["threadId"] = reference(arm, cid)
    assert stream(browser(arm), cid, body)[0] == status


def test_starting_needs_the_csrf_token_and_a_case_worker(arm: ArmA) -> None:
    cid = load_c(arm)
    thread = reference(arm, cid)
    start = run_input(thread, forwardedProps={"start": True})
    assert stream(browser(arm), cid, start, csrf=False)[0] == 403
    assert stream(browser(arm, "auditor.abe"), cid, start, csrf=True)[0] == 403
    assert jobs_for(arm, cid) == 0


def test_resending_or_reconnecting_never_starts_a_second_investigation(arm: ArmA) -> None:
    cid = load_c(arm)
    thread = reference(arm, cid)
    b = browser(arm, watch_seconds=0.3)
    first = run_input(thread, "run-a", forwardedProps={"start": True})
    status, evs = stream(b, cid, first, csrf=True)
    assert status == 200 and jobs_for(arm, cid) == 1
    # No worker ran, so the window closes with RUN_ERROR, and no RUN_FINISHED is made up for an unfinished run.
    assert evs[-1]["type"] == "RUN_ERROR" and evs[-1]["code"] == "watch_window_ended"
    assert stream(b, cid, first, csrf=True)[0] == 200  # the same runId again: watches only
    assert stream(b, cid, run_input(thread, "run-b"), csrf=True)[0] == 200  # a reconnect: a new run, watch only
    assert jobs_for(arm, cid) == 1
    with arm.sessions() as s:
        asked = s.scalar(
            select(func.count())
            .select_from(CaseEvent)
            .where(CaseEvent.case_id == cid, CaseEvent.action == "ag_ui_run_requested")
        )
    assert asked == 1
    work(arm)  # the worker runs the one investigation
    _, after = stream(b, cid, run_input(thread, "run-c"))
    assert after[-1]["type"] == "RUN_FINISHED" and after[-1]["result"]["investigation"] in ("finished", "stopped")
    with arm.sessions() as s:
        assert s.scalar(select(func.count()).select_from(AiRun).where(AiRun.case_id == cid)) == 1


def test_a_stream_never_sends_the_same_step_twice(arm: ArmA) -> None:
    cid = investigated(arm)
    _, evs = stream(browser(arm), cid, run_input(reference(arm, cid)))
    ids = [e["toolCallId"] for e in evs if e["type"] == "TOOL_CALL_START"]
    assert len(ids) == len(set(ids))


def test_the_endpoint_exists_only_with_the_flag_on(arm: ArmA) -> None:
    off = TestClient(create_app(AppSettings(database_url=arm.app_url), arm.factory()))
    assert off.post("/ag-ui/cases/1/runs", json={}).status_code in (404, 405)
    on = TestClient(create_app(AppSettings(database_url=arm.app_url, feature_ag_ui=True), arm.factory()))
    assert on.post("/ag-ui/cases/1/runs", json={}).status_code == 422


def test_the_panel_appears_only_with_the_endpoint_and_renders_text_only(arm: ArmA) -> None:
    cid = investigated(arm)
    on = browser(arm).get(f"/cases/{cid}")
    assert 'data-testid="live-run"' in on.text and "/static/ag-ui-panel.js" in on.text
    off = Browser(TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory())))
    off.login("agent.ana", arm.password)
    assert 'data-testid="live-run"' not in off.get(f"/cases/{cid}").text
    script = (Path(__file__).resolve().parent.parent / "app/web/static/ag-ui-panel.js").read_text(encoding="utf-8")
    assert "textContent" in script and "innerHTML" not in script and "eval(" not in script
    assert '"start"' not in script  # watch only: the panel never starts an investigation


def test_the_protocol_lab_page_is_for_administrators_and_only_with_a_protocol_on(arm: ArmA) -> None:
    on = Browser(TestClient(create_app(AppSettings(database_url=arm.app_url, feature_mcp=True), arm.factory())))
    on.login("admin.ada", arm.password, landing="")
    page = on.get("/admin/protocols")
    assert page.status_code == 200 and page.text.count('data-testid="protocol"') == 3
    assert "FEATURE_MCP: on" in page.text and "FEATURE_A2A: off" in page.text
    # Each independent run is shown with its evidence file, and nothing is claimed without one.
    assert page.text.count("security/evidence/") == 3 and "NOT RUN" not in page.text
    # PROTO-04's limits travel with its status (ADR-0072).
    for limit in ("Verified with limitations", "45 of the 47 required", "rejects by design", "test authentication"):
        assert limit in page.text
    for evidence in ("mcp-inspector-run.txt", "a2a-tck-run.txt", "ag-ui-client-run.txt"):
        assert (Path(__file__).resolve().parent.parent / "security" / "evidence" / evidence).is_file()
    on.login("agent.ana", arm.password)
    assert on.get("/admin/protocols").status_code == 403
    off = Browser(TestClient(create_app(AppSettings(database_url=arm.app_url), arm.factory())))
    off.login("admin.ada", arm.password, landing="")
    assert off.get("/admin/protocols").status_code == 404
