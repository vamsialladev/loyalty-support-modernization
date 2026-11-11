"""Stored rows → AG-UI 1.0 events (spec G.5). Pure functions over the database: no network, no model.

Which AG-UI events, and why only these:

- `RUN_STARTED`, `RUN_FINISHED`: `threadId` is the case reference and `runId` the client's. The result names the stop
  reason and the engine's action.
- `STATE_SNAPSHOT`: an allowlist. Case status and arm, run status and stop reason, counts, the engine's action.
- `STEP_STARTED`, `STEP_FINISHED`: model and validation steps, by name only.
- `TOOL_CALL_START`, `TOOL_CALL_END`: the tool's name; the argument hash rides in `metadata`.
- `TEXT_MESSAGE_*`: the same labelled AI summary staff already see on the case page.
- `RUN_ERROR`: a safe message, never a stack trace.

Not sent: `REASONING_*` (no chain-of-thought), `TOOL_CALL_ARGS` and `TOOL_CALL_RESULT` (no arguments or member data),
prompts, costs, secrets.
"""

from __future__ import annotations

from typing import Any

from ag_ui.core import (
    BaseEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from sqlalchemy.orm import Session

from app.ai.harness import latest_run, steps_of
from app.persistence.models import AiRun, AiStep, Case
from app.services import conventional

RUN_FIELDS = ("status", "stop_reason", "turns", "tool_calls", "is_mock")


def snapshot(s: Session, case: Case, run: AiRun | None) -> dict[str, Any]:
    """Everything the frontend may hold, and nothing else. It's for display; the server stays the source of truth."""
    rec = conventional.latest_recommendation(s, case)
    return {
        "case": {"reference": case.reference, "status": case.status, "arm": case.arm},
        "run": None if run is None else {name: getattr(run, name) for name in RUN_FIELDS},
        "engine": None if rec is None else {"action": rec.action, "detail": rec.detail},
    }


def started(case: Case, run_id: str) -> RunStartedEvent:
    return RunStartedEvent(thread_id=case.reference, run_id=run_id)


def step_events(step: AiStep) -> list[BaseEvent]:
    """One stored step becomes its start and end, so a late viewer sees completed steps whole."""
    if step.kind == "tool":
        call_id = f"step-{step.id}"
        meta = {"arguments_sha256": step.arguments_hash, "status": step.status, "elapsed_ms": step.elapsed_ms}
        return [
            ToolCallStartEvent(tool_call_id=call_id, tool_call_name=step.name, metadata=meta),
            ToolCallEndEvent(tool_call_id=call_id),
        ]
    name = f"{step.kind} {step.step}: {step.name}"[:80]
    return [StepStartedEvent(step_name=name), StepFinishedEvent(step_name=name)]


def summary_events(s: Session, case: Case, run: AiRun | None) -> list[BaseEvent]:
    """The AI summary, only when this run's text is the one on the case page."""
    rec = conventional.latest_recommendation(s, case)
    if run is None or rec is None or rec.ai_run_id != run.id or not rec.ai or not rec.ai.get("summary"):
        return []
    message_id = f"summary-{run.id}"
    return [
        TextMessageStartEvent(message_id=message_id, role="assistant"),
        TextMessageContentEvent(message_id=message_id, delta=str(rec.ai["summary"])[:2000]),
        TextMessageEndEvent(message_id=message_id),
    ]


def finished(s: Session, case: Case, run_id: str, run: AiRun | None) -> RunFinishedEvent:
    rec = conventional.latest_recommendation(s, case)
    return RunFinishedEvent(
        thread_id=case.reference,
        run_id=run_id,
        result={
            "investigation": None if run is None else run.status,
            "stop_reason": None if run is None else run.stop_reason,
            "engine_action": None if rec is None else rec.action,
            "approval": "on the case page, by a supervisor",  # never through this stream
        },
    )


def current_run(s: Session, case: Case, not_before_id: int = 0) -> AiRun | None:
    run = latest_run(s, case)
    return run if run is not None and run.id > not_before_id else None


def new_steps(s: Session, run: AiRun, seen: set[int]) -> list[AiStep]:
    """Steps not yet sent in this stream. AG-UI 1.0 defines no event IDs, so de-duplication is per stream."""
    fresh = [step for step in steps_of(s, run) if step.id not in seen]
    seen.update(step.id for step in fresh)
    return fresh
