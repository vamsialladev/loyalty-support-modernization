"""The case event log: audit trail and E.2 instrumentation in one table (`case_events`; requirement LEG-02).

Every action an agent or supervisor takes is one numbered step with who, when (wall clock, milliseconds), the
simulated business time, and what happened: searches and their result counts, evidence attached, checklist outcome,
decisions with points, information requests, escalations, overrides, approvals, executions, system errors.

These are raw software facts. Correctness (right outcome, false approval, false denial) is scored only by the
Milestone 10 benchmark runner, outside the app, against labels the app never sees. Step counts and timings from the
scripted agent are labelled "scripted, not human timing" and are never presented as employee handling time (E.7).
Search inputs are recorded by kind ("member number", "name + email"), not by value, to keep personal data out.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import correlation
from app.clock import utc_now_precise
from app.domain.roles import Identity
from app.persistence.models import Case, CaseEvent, SystemEvent

SCRIPTED_PREFIX = "scripted-"
SYSTEM_PREFIX = "system-"


def actor_kind(who: Identity) -> str:
    """Scripted benchmark actors are ordinary accounts with the same roles; their usernames mark them (ADR-0048)."""
    if who.username.startswith(SYSTEM_PREFIX):
        return "system"
    return "scripted" if who.username.startswith(SCRIPTED_PREFIX) else "human"


def record(s: Session, case: Case, who: Identity, action: str, **detail: Any) -> CaseEvent:
    if correlation_id := correlation.current():
        detail["correlation_id"] = correlation_id
    step = (s.scalar(select(func.max(CaseEvent.step)).where(CaseEvent.case_id == case.id)) or 0) + 1
    event = CaseEvent(
        case_id=case.id,
        step=step,
        actor=who.username,
        actor_kind=actor_kind(who),
        action=action,
        detail=detail,
        at_utc=utc_now_precise(),
        sim_time_utc=case.received_at_utc,
    )
    s.add(event)
    s.flush()
    return event


def record_system(s: Session, who: Identity, action: str, **detail: Any) -> SystemEvent:
    """An audit event with no case: policy publishing, the kill switch, dead jobs."""
    event = SystemEvent(
        actor=who.username, actor_kind=actor_kind(who), action=action, detail=detail, at_utc=utc_now_precise()
    )
    s.add(event)
    s.flush()
    return event


def system_events(s: Session, limit: int = 50) -> list[SystemEvent]:
    return list(s.scalars(select(SystemEvent).order_by(SystemEvent.id.desc()).limit(limit)))


def events(s: Session, case: Case) -> list[CaseEvent]:
    return list(s.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.step)))
