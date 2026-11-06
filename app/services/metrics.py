"""Operational metrics, read from the event log and the case tables (spec B.11, B.13, E.2; UI-01, API-01).

Observed counts only, and never a score: nothing here knows what the right answer was. Scripted benchmark actors are
kept apart from people, because a scripted run's steps and times measure software, not an employee (spec E.7).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.business_time import parse_utc
from app.domain.case_states import CaseState
from app.domain.roles import Identity, NotPermitted, Role
from app.persistence.models import AdjustmentRequestRow, Case, CaseEvent, Feedback, Job, Recommendation
from app.services import jobs

HUMAN, SCRIPTED = "human", "scripted"
WITHOUT_A_LABEL_NOTE = "Observed counts. They say what happened, not whether it was right."


@dataclass
class ArmMetrics:
    arm: str
    kind: str  # who worked the cases: human | scripted
    cases: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    median_steps: float | None = None
    median_minutes_to_close: float | None = None
    adjustments_requested: int = 0
    adjustments_executed: int = 0
    points_executed: int = 0
    approvals_invalidated: int = 0
    overrides: int = 0
    information_requests: int = 0
    escalated: int = 0
    investigations: int = 0
    feedback_helpful: int = 0
    feedback_not_helpful: int = 0
    engine_results: dict[str, int] = field(default_factory=dict)


@dataclass
class Metrics:
    rows: list[ArmMetrics]
    jobs_queued: int
    jobs_dead: int
    note: str = WITHOUT_A_LABEL_NOTE


def require_metrics_reader(who: Identity) -> None:
    if who.role not in (Role.SUPERVISOR, Role.ADMINISTRATOR, Role.AUDITOR):
        raise NotPermitted("only supervisors, administrators and auditors read the metrics")


def _worked_by(events: list[CaseEvent]) -> str:
    """A case any scripted actor touched is a scripted case, so its numbers never mix with people's."""
    return SCRIPTED if any(e.actor_kind == SCRIPTED for e in events) else HUMAN


def _minutes(first: str, last: str) -> float:
    return round((parse_utc(last[:19] + "Z") - parse_utc(first[:19] + "Z")).total_seconds() / 60, 1)


def collect(s: Session, who: Identity) -> Metrics:
    require_metrics_reader(who)
    events_by_case: dict[int, list[CaseEvent]] = {}
    for event in s.scalars(select(CaseEvent).order_by(CaseEvent.case_id, CaseEvent.step)):
        events_by_case.setdefault(event.case_id, []).append(event)
    requests_by_case: dict[int, list[AdjustmentRequestRow]] = {}
    for adjustment in s.scalars(select(AdjustmentRequestRow)):
        requests_by_case.setdefault(adjustment.case_id, []).append(adjustment)
    feedback_by_case: dict[int, list[Feedback]] = {}
    for item in s.scalars(select(Feedback)):
        feedback_by_case.setdefault(item.case_id, []).append(item)
    latest: dict[int, Recommendation] = {}
    for rec in s.scalars(select(Recommendation).order_by(Recommendation.id)):
        latest[rec.case_id] = rec

    table: dict[tuple[str, str], ArmMetrics] = {}
    steps: dict[tuple[str, str], list[int]] = {}
    closes: dict[tuple[str, str], list[float]] = {}
    statuses: dict[tuple[str, str], Counter[str]] = {}
    results: dict[tuple[str, str], Counter[str]] = {}
    for case in s.scalars(select(Case)):
        events = events_by_case.get(case.id, [])
        key = (case.arm, _worked_by(events))
        stats = table.setdefault(key, ArmMetrics(*key))
        stats.cases += 1
        statuses.setdefault(key, Counter())[case.status] += 1
        results.setdefault(key, Counter())
        steps.setdefault(key, []).append(len(events))
        if case.status == CaseState.RESOLVED.value and events:
            closes.setdefault(key, []).append(_minutes(events[0].at_utc, events[-1].at_utc))
        for event in events:
            if event.action == "information_requested":
                stats.information_requests += 1
            elif event.action == "case_escalated":
                stats.escalated += 1
            elif event.action == "investigation_completed":
                stats.investigations += 1
            elif event.action == "case_closed" and event.detail.get("override"):
                stats.overrides += 1
        for request in requests_by_case.get(case.id, []):
            stats.adjustments_requested += 1
            if request.status == "executed":
                stats.adjustments_executed += 1
                stats.points_executed += request.points
            if request.status == "invalidated":
                stats.approvals_invalidated += 1
        for item in feedback_by_case.get(case.id, []):
            stats.feedback_helpful += item.rating == "helpful"
            stats.feedback_not_helpful += item.rating == "not_helpful"
        if case.id in latest:
            results[key][latest[case.id].action] += 1

    for key, stats in table.items():
        stats.by_status = dict(sorted(statuses[key].items()))
        stats.engine_results = dict(sorted(results[key].items()))
        stats.median_steps = median(steps[key]) if steps[key] else None
        stats.median_minutes_to_close = median(closes[key]) if closes.get(key) else None
    queued = s.scalars(select(Job.id).where(Job.status.in_((jobs.QUEUED, jobs.RUNNING)))).all()
    dead = s.scalars(select(Job.id).where(Job.status == jobs.DEAD)).all()
    return Metrics(sorted(table.values(), key=lambda r: (r.arm, r.kind)), len(queued), len(dead))
