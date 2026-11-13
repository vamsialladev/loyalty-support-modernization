"""The AG-UI endpoint inside the console: `POST /ag-ui/cases/{case_id}/runs` (spec G.5; RFC-0004).

- **Who may watch:** a signed-in console user who can read the case, in the same customer (the console's session; a
  session ID alone isn't enough, it's checked against the server's session table). Anyone else gets 401 or "not
  found", like the case page.
- **Starting:** `forwardedProps: {"start": true}` asks for an investigation, as the Investigate button does: case
  workers only, with the console's CSRF token in `X-CSRF-Token`, through the same queue (one active job per case).
  A `runId` that already asked once only watches, so resending or reconnecting can't start a second investigation.
- **Watching:** without `start`, the run only watches. AG-UI 1.0 has no stream resume, so a reconnect is a new run
  with a new `runId`, which opens with a state snapshot and replays the stored steps.
- **Inbound:** the body must be a valid `RunAgentInput` with no extra top-level fields, and its `threadId` must be
  the case's reference. Messages, tools, state and context from the client are not used: the server is the truth.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

from ag_ui.core import BaseEvent, RunAgentInput, RunErrorEvent, StateSnapshotEvent
from ag_ui.encoder import EventEncoder
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select

from app.domain.roles import NotPermitted, require_case_worker
from app.persistence.models import Case, CaseEvent
from app.services import conventional, jobs, rate_limit, sessions
from app.services.cases import CaseNotFound, WorkflowError, get_case
from app.services.instrumentation import record
from app.settings import AppSettings
from protocols.ag_ui import events

log = logging.getLogger("protocols.ag_ui")
ALLOWED_KEYS = {"threadId", "runId", "parentRunId", "state", "messages", "tools", "context", "forwardedProps", "resume"}
ALLOWED_KEYS |= {"protocolVersion"}
MAX_BODY_BYTES = 64_000
REQUESTED = "ag_ui_run_requested"


def _problem(status: int, title: str) -> JSONResponse:
    return JSONResponse({"title": title, "status": status}, status_code=status, media_type="application/problem+json")


def install_ag_ui(app: FastAPI, settings: AppSettings, poll_seconds: float = 0.5, watch_seconds: float = 120.0) -> None:
    from app.web.console import SESSION_COOKIE

    app.state.ag_ui = True  # the case page shows the live-run panel only now

    @app.post("/ag-ui/cases/{case_id}/runs", response_model=None)
    async def run(request: Request, case_id: int) -> Response:
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return _problem(413, "The request is too large.")
        try:
            body = await request.json()
        except ValueError:
            return _problem(400, "The body isn't JSON.")
        if not isinstance(body, dict) or set(body) - ALLOWED_KEYS:
            return _problem(422, "Only RunAgentInput's own fields are accepted.")
        try:
            payload = RunAgentInput.model_validate(body)
        except ValidationError:
            return _problem(422, "The body isn't a valid RunAgentInput.")
        start = isinstance(payload.forwarded_props, dict) and payload.forwarded_props.get("start") is True
        factory = request.app.state.sessions
        with factory() as s:
            active = sessions.resolve(s, request.app.state.identity, request.cookies.get(SESSION_COOKIE))
            if active is None:
                return _problem(401, "Sign in to the console first.")
            try:
                rate_limit.hit(s, f"user:{active.identity.user_id}", request.app.state.rate_limit_per_minute, 60)
                case = get_case(s, active.identity, case_id)
            except rate_limit.RateLimited:
                return _problem(429, "Too many requests.")
            except (CaseNotFound, NotPermitted):
                return _problem(404, "No such case.")
            if payload.thread_id != case.reference:
                return _problem(422, "threadId must be this case's reference.")
            before = events.current_run(s, case)
            watch_from = 0
            if start:
                if not sessions.csrf_ok(active, request.headers.get("x-csrf-token")):
                    return _problem(403, "Starting needs the console's CSRF token.")
                try:
                    require_case_worker(active.identity)
                except NotPermitted:
                    return _problem(403, "Only agents and supervisors start investigations.")
                if not _already_asked(s, case, payload.run_id):
                    try:
                        conventional.start_investigation(s, active.identity, case)
                    except WorkflowError as refused:
                        return _problem(409, str(refused))
                    record(s, case, active.identity, REQUESTED, run_id=payload.run_id[:64])
                    s.commit()
                watch_from = before.id if before is not None else 0
        encoder = EventEncoder(accept=request.headers.get("accept", "text/event-stream"))
        stream = _stream(factory, case_id, payload.run_id, watch_from, start, poll_seconds, watch_seconds)
        return StreamingResponse(
            (encoder.encode(e) for e in stream),
            media_type=encoder.get_content_type(),
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )


def _already_asked(s: Any, case: Case, run_id: str) -> bool:
    rows = s.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id, CaseEvent.action == REQUESTED))
    return any((e.detail or {}).get("run_id") == run_id[:64] for e in rows)


def _stream(
    factory: Any,
    case_id: int,
    run_id: str,
    watch_from: int,
    started: bool,
    poll_seconds: float,
    watch_seconds: float,
) -> Iterator[BaseEvent]:
    """Reads the stored run until it ends, or until the watch window closes. Each poll is a short transaction."""
    seen: set[int] = set()
    deadline = time.monotonic() + watch_seconds
    try:
        with factory() as s:
            case = s.get(Case, case_id)
            assert case is not None
            yield events.started(case, run_id)
            yield StateSnapshotEvent(snapshot=events.snapshot(s, case, events.current_run(s, case, watch_from)))
        while True:
            with factory() as s:
                case = s.get(Case, case_id)
                assert case is not None
                run = events.current_run(s, case, watch_from)
                if run is not None:
                    for step in events.new_steps(s, run, seen):
                        yield from events.step_events(step)
                working = jobs.active_case_job(s, case.id) is not None
                if (run is not None and run.status != "running" and not working) or (
                    run is None and not working and not started
                ):
                    yield from events.summary_events(s, case, run)
                    yield StateSnapshotEvent(snapshot=events.snapshot(s, case, run))
                    yield events.finished(s, case, run_id, run)
                    return
                if run is None and not working and started:
                    # Asked, but nothing queued or running any more: say what's there and stop.
                    yield StateSnapshotEvent(snapshot=events.snapshot(s, case, None))
                    yield events.finished(s, case, run_id, None)
                    return
            if time.monotonic() >= deadline:
                yield RunErrorEvent(
                    message="Still running. Start a new run (watch only) to keep following it.",
                    code="watch_window_ended",
                )
                return
            time.sleep(poll_seconds)
    except Exception:  # the frontend gets a safe message; the log gets the rest
        log.exception("ag-ui stream failed for case %s", case_id)
        yield RunErrorEvent(message="The live view stopped. The case page has the current state.", code="stream_failed")
