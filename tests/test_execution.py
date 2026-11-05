"""Execution through the worker, outcomes, reconciliation and the kill switch, on SQLite (spec B.10, B.12; ADR-0061).

Concurrency and real process deaths are in `tests/test_write_path_postgres.py`.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import correlation
from app.domain.case_states import CaseState
from app.domain.customer_records import AdjustmentRequest, AdjustmentResult
from app.domain.roles import Identity, NotPermitted, Role
from app.main import create_app
from app.persistence.models import AdjustmentRequestRow, Case, Job, SystemEvent, SystemSwitch, User
from app.ports.customer_systems import (
    AuthenticationFailed,
    CustomerSystemError,
    CustomerSystems,
    IdempotencyConflict,
    MalformedResponse,
    RateLimited,
    RequestRejected,
    SchemaMismatch,
    TemporarilyUnavailable,
    UncertainOutcome,
)
from app.services import cases as svc
from app.services import jobs, kill_switch
from app.services.instrumentation import events
from app.services.job_handlers import MAX_SUBMISSIONS_PER_APPROVAL, build_handlers, sweep_stranded
from app.services.write_path import EXECUTE_JOB, RECONCILE_JOB, SharedWritePath, attempts_of, load_request
from app.settings import AppSettings
from app.worker import Worker
from tests.arm_a import ArmA, Browser, field, make_arm_a

K01, MEMBER, STAY, POINTS = "DV-001", "GR-85640", "BR-6638", 14_840
ADMIN = Identity(1, "admin.ada", "Ada", Role.ADMINISTRATOR)
REASON = "Pausing while a data problem is checked."
WP = SharedWritePath(settle_seconds=0)


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def approved(arm: ArmA, s: Session, wp: SharedWritePath = WP) -> tuple[Case, AdjustmentRequestRow]:
    (case,) = arm.load(s, K01)
    who, systems = arm.who("agent.ana"), arm.systems(case.received_at_utc)
    svc.start_work(s, who, case)
    svc.attach_member(s, who, case, systems, MEMBER)
    svc.attach_stay(s, who, case, systems, MEMBER, STAY)
    svc.attach_ledger(s, who, case, systems, MEMBER, show_older=True)
    svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")
    row = svc.request_adjustment(s, who, case, arm.rules)
    assert wp.decide(s, arm.who("supervisor.sam"), row.id, systems, approve=True, reason="").status == "approved"
    return case, row


class Scripted:
    """The customer systems, with `submit_adjustment` and `find_adjustment` scripted call by call."""

    def __init__(
        self, inner: CustomerSystems, submits: list[Any] | None = None, lookups: list[Any] | None = None
    ) -> None:
        self.inner, self.submits, self.lookups = inner, list(submits or []), list(lookups or [])
        self.submit_keys: list[str] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def submit_adjustment(self, request: AdjustmentRequest, key: str) -> AdjustmentResult:
        self.submit_keys.append(key)
        step = self.submits.pop(0) if self.submits else "real"
        if step == "real":
            return self.inner.submit_adjustment(request, key)
        if step == "applied_then_lost":
            self.inner.submit_adjustment(request, key)
            raise UncertainOutcome("lost", code="timeout")
        if isinstance(step, Exception):
            raise step
        return step  # type: ignore[no-any-return]

    def find_adjustment(self, key: str) -> AdjustmentResult | None:
        step = self.lookups.pop(0) if self.lookups else "real"
        if step == "real":
            return self.inner.find_adjustment(key)
        if isinstance(step, Exception):
            raise step
        return step  # type: ignore[no-any-return]


def credits_on_ledger(arm: ArmA) -> list[Any]:
    return [e for e in arm.systems().get_ledger(MEMBER) if e.kind == "adjustment" and e.stay_id == STAY]


def worker_for(arm: ArmA, systems: Any = None, wp: SharedWritePath = WP, **kw: Any) -> Worker:
    factory = (lambda _t: systems) if systems is not None else arm.factory()
    return Worker(arm.sessions, build_handlers(wp, factory), **kw)


def retry_due_jobs(arm: ArmA) -> None:
    """Make every queued job due now, as if its wait had passed."""
    with arm.sessions() as s:
        s.execute(text("update jobs set run_after_utc = '2000-01-01T00:00:00Z' where status = 'queued'"))
        s.commit()


# ---------- through the worker ----------


def test_a_request_queues_a_job_and_the_worker_applies_it(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        queued = WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        assert queued.status == "queued" and case.status == CaseState.APPROVED
        job = s.scalars(select(Job)).one()
        assert (job.kind, job.case_id, job.payload) == (
            EXECUTE_JOB,
            case.id,
            {"request_id": row.id, "user_id": arm.who("supervisor.sam").user_id},
        )
    worker_for(arm).drain()
    with arm.sessions() as s:
        reread = s.get(Case, case.id)
        assert reread is not None and reread.status == CaseState.RESOLVED
        assert s.scalars(select(Job)).one().status == jobs.SUCCEEDED
    assert len(credits_on_ledger(arm)) == 1


def test_a_second_click_adds_no_second_job(arm: ArmA) -> None:
    with arm.sessions() as s:
        _case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        assert len(s.scalars(select(Job)).all()) == 1


@pytest.mark.parametrize("username", ["agent.ben", "agent.ana", "admin.ada", "auditor.abe"])
def test_only_a_supervisor_who_did_not_request_it_can_ask(arm: ArmA, username: str) -> None:
    with arm.sessions() as s:
        _case, row = approved(arm, s)
        with pytest.raises(NotPermitted):
            WP.request_execution(s, arm.who(username), row.id)


def test_the_requester_refused_at_run_time_stops_the_job(arm: ArmA) -> None:
    """The role is checked again when the job runs, not only when it was queued."""
    with arm.sessions() as s:
        case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        user = s.scalars(select(User).where(User.username == "supervisor.sam")).one()
        user.role = Role.AGENT.value
        s.commit()
        case_id = case.id
    worker_for(arm).drain()
    with arm.sessions() as s:
        assert s.scalars(select(Job)).one().status == jobs.DEAD
        reread = s.get(Case, case_id)
        assert reread is not None and reread.status == CaseState.APPROVED
    assert credits_on_ledger(arm) == []


def test_a_deactivated_requester_stops_the_job(arm: ArmA) -> None:
    with arm.sessions() as s:
        _case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        s.scalars(select(User).where(User.username == "supervisor.sam")).one().active = False
        s.commit()
    worker_for(arm).drain()
    with arm.sessions() as s:
        assert (s.scalars(select(Job)).one().status, s.scalars(select(Job)).one().last_error) == (
            jobs.DEAD,
            "requester_inactive",
        )
    assert credits_on_ledger(arm) == []


def test_one_correlation_id_from_the_request_to_the_events(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        with correlation.correlated("cid-from-request"):
            WP.request_execution(s, arm.who("supervisor.sam"), row.id)
    worker_for(arm).drain()
    with arm.sessions() as s:
        reread = s.get(Case, case.id)
        assert reread is not None
        marked = {e.action: e.detail.get("correlation_id") for e in events(s, reread)}
        assert marked["execution_requested"] == marked["execution_started"] == "cid-from-request"
        assert marked["adjustment_executed"] == "cid-from-request"


# ---------- outcome classes (RFC-0001) ----------


def result_for(key: str, **changes: Any) -> AdjustmentResult:
    base = AdjustmentResult("ADJ-1", key, MEMBER, STAY, POINTS, "applied", "2026-01-01T00:00:00Z", "L-ADJ-1")
    return replace(base, **changes)


@pytest.mark.parametrize(
    "error",
    [
        MalformedResponse("200 but not JSON", code="malformed"),
        SchemaMismatch("200 but a field is missing", code="schema_mismatch"),
        UncertainOutcome("timed out", code="timeout"),
    ],
)
def test_a_response_that_cannot_be_read_counts_as_may_have_applied(arm: ArmA, error: CustomerSystemError) -> None:
    """RFC-0001, fault 1: a 200 with an unreadable body used to count as "refused, safe to re-run"."""
    with arm.sessions() as s:
        case, row = approved(arm, s)
        systems = Scripted(arm.systems(case.received_at_utc), submits=[error], lookups=[None])
        result = WP.execute(s, arm.who("supervisor.sam"), row.id, systems)
        assert result.status == "unknown" and case.status == CaseState.EXECUTION_UNKNOWN
        assert row.status == "execution_unknown"


def test_the_real_mock_apis_malformed_reply_is_reconciled_to_one_credit(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        reads = arm.systems(case.received_at_utc)
        faulty = arm.systems(case.received_at_utc, fault="malformed")

        class MalformedSubmit(Scripted):
            def submit_adjustment(self, request: AdjustmentRequest, key: str) -> AdjustmentResult:
                return faulty.submit_adjustment(request, key)

        result = WP.execute(s, arm.who("supervisor.sam"), row.id, MalformedSubmit(reads))
        assert result.status == "applied" and "Reconciled" in result.message
        assert case.status == CaseState.RESOLVED
    assert len(credits_on_ledger(arm)) == 1


def test_a_key_conflict_escalates_and_keeps_the_stay_blocked(arm: ArmA) -> None:
    """RFC-0001, fault 2: a 409 used to return the case to Approved, though something was applied under that key."""
    with arm.sessions() as s:
        case, row = approved(arm, s)
        systems = Scripted(arm.systems(case.received_at_utc), submits=[IdempotencyConflict("used", code="conflict")])
        result = WP.execute(s, arm.who("supervisor.sam"), row.id, systems)
        assert result.status == "conflict" and case.status == CaseState.ESCALATED
        assert row.status == "execution_conflict" and case.resolution_code == "execution_conflict"
        assert events(s, case)[-1].action == "execution_conflict"


@pytest.mark.parametrize("field_name,value", [("points", 1), ("member_number", "GR-00000"), ("stay_id", "BR-0000")])
def test_a_different_record_from_the_submission_escalates(arm: ArmA, field_name: str, value: object) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        other = result_for("k", **{field_name: value})
        result = WP.execute(s, arm.who("supervisor.sam"), row.id, Scripted(arm.systems(case.received_at_utc), [other]))
        assert result.status == "conflict" and case.status == CaseState.ESCALATED


@pytest.mark.parametrize("field_name,value", [("points", 1), ("member_number", "GR-00000"), ("stay_id", "BR-0000")])
def test_a_different_record_found_by_reconciliation_escalates(arm: ArmA, field_name: str, value: object) -> None:
    """RFC-0001, fault 3: reconciliation used to accept any record under the key as success."""
    with arm.sessions() as s:
        case, row = approved(arm, s)
        lost = UncertainOutcome("lost", code="timeout")
        other = result_for("k", **{field_name: value})
        systems = Scripted(arm.systems(case.received_at_utc), submits=[lost], lookups=[other])
        result = WP.execute(s, arm.who("supervisor.sam"), row.id, systems)
        assert result.status == "conflict" and case.status == CaseState.ESCALATED
        assert row.status == "execution_conflict"


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationFailed("no", code="auth"),
        RequestRejected("no", code="invalid"),
    ],
)
def test_a_refusal_before_applying_returns_to_approved(arm: ArmA, error: CustomerSystemError) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        systems = Scripted(arm.systems(case.received_at_utc), submits=[error])
        assert WP.execute(s, arm.who("supervisor.sam"), row.id, systems).status == "rejected_upstream"
        assert case.status == CaseState.APPROVED and row.status == "approved"


def test_busy_retries_through_the_worker_with_the_same_key(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        received = case.received_at_utc
    systems = Scripted(arm.systems(received), submits=[TemporarilyUnavailable("busy", code="unavailable")])
    worker = worker_for(arm, systems)
    assert worker.run_once() is True
    with arm.sessions() as s:
        job = s.scalars(select(Job)).one()
        assert (job.status, job.last_error, job.attempts) == (jobs.QUEUED, "upstream_busy", 1)
    retry_due_jobs(arm)
    assert worker.run_once() is True
    assert len(set(systems.submit_keys)) == 1 and len(systems.submit_keys) == 2
    assert len(credits_on_ledger(arm)) == 1


def test_retry_after_from_the_platform_sets_the_wait(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        received = case.received_at_utc
    busy = RateLimited("slow down", retry_after_seconds=90, code="rate_limited")
    worker_for(arm, Scripted(arm.systems(received), submits=[busy])).run_once()
    with arm.sessions() as s:
        job = s.scalars(select(Job)).one()
        assert job.status == jobs.QUEUED and job.run_after_utc > job.created_at_utc


# ---------- reconciliation ----------


def test_committed_then_lost_is_resolved_with_one_credit_through_the_worker(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        received, case_id = case.received_at_utc, case.id
    systems = Scripted(arm.systems(received), submits=["applied_then_lost"])
    worker_for(arm, systems).drain()
    with arm.sessions() as s:
        reread = s.get(Case, case_id)
        assert reread is not None and reread.status == CaseState.RESOLVED
    assert len(systems.submit_keys) == 1
    assert len(credits_on_ledger(arm)) == 1


def test_one_not_found_is_not_believed(arm: ArmA) -> None:
    """RFC-0001, fault 4: a lagging platform. The first lookup misses it, the second finds it, none is resubmitted."""
    with arm.sessions() as s:
        case, row = approved(arm, s)
        systems = Scripted(arm.systems(case.received_at_utc), submits=["applied_then_lost"], lookups=[None])
        assert WP.execute(s, arm.who("supervisor.sam"), row.id, systems).status == "unknown"
        assert case.status == CaseState.EXECUTION_UNKNOWN
        assert WP.check_status(s, arm.who("supervisor.sam"), row.id, systems).status == "applied"
        assert len(systems.submit_keys) == 1 and case.status == CaseState.RESOLVED
    assert len(credits_on_ledger(arm)) == 1


def test_not_found_needs_the_settle_window_too(arm: ArmA) -> None:
    now = ["2026-11-04T12:00:00Z"]
    wp = SharedWritePath(settle_seconds=60, clock=lambda: now[0])
    with arm.sessions() as s:
        case, row = approved(arm, s, wp)
        lost = UncertainOutcome("lost", code="timeout")
        systems = Scripted(arm.systems(case.received_at_utc), submits=[lost], lookups=[None, None, None, None])
        who = arm.who("supervisor.sam")
        assert wp.execute(s, who, row.id, systems).status == "unknown"
        assert wp.check_status(s, who, row.id, systems).status == "unknown", "two lookups, but too soon"
        now[0] = "2026-11-04T12:00:59Z"
        assert wp.check_status(s, who, row.id, systems).status == "unknown"
        now[0] = "2026-11-04T12:01:00Z"
        assert wp.check_status(s, who, row.id, systems).status == "not_applied"
        assert case.status == CaseState.APPROVED


def test_a_failed_lookup_is_not_a_not_found(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        down = TemporarilyUnavailable("down", code="unavailable")
        lost = UncertainOutcome("lost", code="timeout")
        systems = Scripted(arm.systems(case.received_at_utc), submits=[lost], lookups=[down, down, down])
        who = arm.who("supervisor.sam")
        assert WP.execute(s, who, row.id, systems).status == "unknown"
        assert WP.check_status(s, who, row.id, systems).status == "unknown"
        assert WP.check_status(s, who, row.id, systems).status == "unknown"
        assert case.status == CaseState.EXECUTION_UNKNOWN
        assert [a.outcome for a in attempts_of(s, row)].count("absent") == 0


def test_confirmed_absent_resubmits_with_the_same_key_through_the_worker(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        received, case_id = case.received_at_utc, case.id
    lost = UncertainOutcome("lost", code="timeout")
    systems = Scripted(arm.systems(received), submits=[lost], lookups=[None, None])
    worker = worker_for(arm, systems)
    for _ in range(8):
        retry_due_jobs(arm)
        worker.drain()
    with arm.sessions() as s:
        reread = s.get(Case, case_id)
        assert reread is not None and reread.status == CaseState.RESOLVED
    assert len(systems.submit_keys) == 2 and len(set(systems.submit_keys)) == 1
    assert len(credits_on_ledger(arm)) == 1


def test_submissions_per_approval_are_bounded(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        received, case_id = case.received_at_utc, case.id
    lost = UncertainOutcome("lost", code="timeout")
    systems = Scripted(arm.systems(received), submits=[lost] * 10, lookups=[None] * 40)
    worker = worker_for(arm, systems)
    for _ in range(30):
        retry_due_jobs(arm)
        worker.drain()
    assert len(systems.submit_keys) == MAX_SUBMISSIONS_PER_APPROVAL
    with arm.sessions() as s:
        reread = s.get(Case, case_id)
        assert reread is not None and reread.status == CaseState.APPROVED
        assert events(s, reread)[-1].action == "execution_gave_up"
    assert credits_on_ledger(arm) == []


def test_an_unreachable_platform_leaves_the_case_visibly_unknown_when_the_job_dies(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        received, case_id = case.received_at_utc, case.id
    lost = UncertainOutcome("lost", code="timeout")
    down = TemporarilyUnavailable("down", code="unavailable")
    systems = Scripted(arm.systems(received), submits=[lost], lookups=[down] * 50)
    worker = worker_for(arm, systems)
    for _ in range(20):
        retry_due_jobs(arm)
        worker.drain()
    with arm.sessions() as s:
        reread = s.get(Case, case_id)
        assert reread is not None and reread.status == CaseState.EXECUTION_UNKNOWN, "never hidden, never assumed"
        dead = s.scalars(select(Job).where(Job.status == jobs.DEAD)).one()
        assert dead.kind == RECONCILE_JOB
        assert sweep_stranded(s) == [], "a dead job waits for a person: retries stay bounded"
        jobs.requeue_dead(s, ADMIN, dead.id)
    worker_for(arm).drain()
    with arm.sessions() as s:
        reread = s.get(Case, case_id)
        assert reread is not None and reread.status == CaseState.EXECUTION_UNKNOWN  # one real lookup isn't enough yet
        requeued = s.scalars(select(Job).where(Job.kind == RECONCILE_JOB)).one()
        assert (requeued.status, requeued.last_error) == (jobs.QUEUED, "still_unknown")


def test_a_worker_lost_mid_execution_goes_to_unknown_not_to_a_resubmit(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        job = jobs.claim(s, "dead-worker", 60)
        assert job is not None
        # What the dead worker got done: it claimed the case and submitted, and the credit landed.
        case.status, row.status = CaseState.EXECUTING.value, "executing"
        from app.persistence.models import ExecutionAttempt
        from app.services.write_path import approval_of, idempotency_key

        approval = approval_of(s, row)
        assert approval is not None
        key = idempotency_key("hg-demo", approval)
        s.add(
            ExecutionAttempt(
                adjustment_request_id=row.id,
                idempotency_key=key,
                started_by="supervisor.sam",
                started_at_utc="2026-11-04T00:00:00Z",
                outcome="submitted",
            )
        )
        s.execute(text("update jobs set lease_expires_utc = '2000-01-01T00:00:00Z'"))
        s.commit()
        received, case_id = case.received_at_utc, case.id
    arm.systems(received).submit_adjustment(AdjustmentRequest(MEMBER, STAY, POINTS, "missing_points", "agent.ana"), key)
    systems = Scripted(arm.systems(received))
    worker_for(arm, systems).drain()
    with arm.sessions() as s:
        reread = s.get(Case, case_id)
        assert reread is not None and reread.status == CaseState.RESOLVED
        actions = [e.action for e in events(s, reread)]
        assert "execution_unknown" in actions and "reconciled_applied" in actions
    assert systems.submit_keys == [], "reconciled, never resubmitted"
    assert len(credits_on_ledger(arm)) == 1


def test_the_sweep_finds_a_stranded_case_and_leaves_a_working_one(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        case.status, row.status = CaseState.EXECUTION_UNKNOWN.value, "execution_unknown"
        s.commit()
        assert sweep_stranded(s) == [row.id]
        assert sweep_stranded(s) == [], "one job is enough"
        assert s.scalars(select(Job)).one().kind == RECONCILE_JOB


# ---------- the kill switch ----------


def test_the_switch_refuses_a_request_and_holds_queued_jobs_without_using_attempts(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        who = arm.who("supervisor.sam")
        WP.request_execution(s, who, row.id)
        kill_switch.set_engaged(s, ADMIN, True, REASON)
        job_before = s.scalars(select(Job)).one()
        assert job_before.status == jobs.QUEUED
        case_id = case.id
    worker = worker_for(arm)
    assert worker.run_once() is True
    with arm.sessions() as s:
        job = s.scalars(select(Job)).one()
        assert (job.status, job.attempts, job.last_error) == (jobs.QUEUED, 0, "kill_switch")
        reread = s.get(Case, case_id)
        assert reread is not None and reread.status == CaseState.APPROVED
    assert credits_on_ledger(arm) == []
    with arm.sessions() as s:
        kill_switch.set_engaged(s, ADMIN, False, "The data problem was a false alarm.")
    retry_due_jobs(arm)
    worker.drain()
    assert len(credits_on_ledger(arm)) == 1


def test_the_switch_refuses_a_new_request(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        kill_switch.set_engaged(s, ADMIN, True, REASON)
        with pytest.raises(svc.WorkflowError, match="switched off"):
            WP.request_execution(s, arm.who("supervisor.sam"), row.id)
        assert s.scalars(select(Job)).first() is None and case.status == CaseState.APPROVED


def test_the_switch_stops_a_worker_that_passed_the_first_check(arm: ArmA) -> None:
    """Between the claim and the submission: the last look catches it, and nothing goes upstream."""
    with arm.sessions() as s:
        case, row = approved(arm, s)
        inner = arm.systems(case.received_at_utc)
        systems = Scripted(inner)
        real_is_engaged = kill_switch.is_engaged
        calls = {"n": 0}

        def second_look_sees_it(session: Session) -> bool:
            calls["n"] += 1
            return calls["n"] >= 2 or real_is_engaged(session)

        original = kill_switch.is_engaged
        kill_switch.is_engaged = second_look_sees_it  # type: ignore[assignment]
        try:
            result = WP.execute(s, arm.who("supervisor.sam"), row.id, systems)
        finally:
            kill_switch.is_engaged = original  # type: ignore[assignment]
        assert result.status == "held" and systems.submit_keys == []
        assert case.status == CaseState.APPROVED and row.status == "approved"
        assert [a.outcome for a in attempts_of(s, row)] == ["held"]
    assert credits_on_ledger(arm) == []


def test_investigation_and_reconciliation_keep_working_while_it_is_off(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        lost = UncertainOutcome("lost", code="timeout")
        systems = Scripted(arm.systems(case.received_at_utc), submits=[lost], lookups=[None])
        assert WP.execute(s, arm.who("supervisor.sam"), row.id, systems).status == "unknown"
        kill_switch.set_engaged(s, ADMIN, True, REASON)
        # Reconciliation is a read: it still runs.
        result = WP.check_status(s, arm.who("supervisor.sam"), row.id, systems)
        assert result.status == "not_applied" and case.status == CaseState.APPROVED

        (second,) = arm.load(s, "DV-012")
        who = arm.who("agent.ben")
        svc.start_work(s, who, second)
        reads = arm.systems(second.received_at_utc)
        svc.attach_member(s, who, second, reads, "GR-46204")
        svc.attach_stay(s, who, second, reads, "GR-46204", "ML-4462")
        svc.attach_ledger(s, who, second, reads, "GR-46204", show_older=True)
        svc.attach_policy(s, who, second, arm.index, "missing-points-requests#3")
        assert svc.request_adjustment(s, who, second, arm.rules).status == "pending"


def test_a_missing_switch_row_stops_adjustments(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        s.delete(s.get(SystemSwitch, kill_switch.ADJUSTMENTS))
        s.commit()
        assert kill_switch.is_engaged(s) is True
        systems = Scripted(arm.systems(case.received_at_utc))
        assert WP.execute(s, arm.who("supervisor.sam"), row.id, systems).status == "held"
        assert systems.submit_keys == []


def test_only_an_administrator_changes_the_switch_and_it_needs_a_reason(arm: ArmA) -> None:
    with arm.sessions() as s:
        with pytest.raises(NotPermitted):
            kill_switch.set_engaged(s, arm.who("supervisor.sam"), True, REASON)
        with pytest.raises(svc.WorkflowError, match="reason"):
            kill_switch.set_engaged(s, ADMIN, True, "short")
        assert kill_switch.is_engaged(s) is False
        kill_switch.set_engaged(s, ADMIN, True, REASON)
        event = s.scalars(select(SystemEvent).where(SystemEvent.action == "kill_switch_changed")).one()
        assert event.detail == {"engaged": True, "reason": REASON} and event.actor == "admin.ada"


def test_the_switch_in_the_console(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        case_id, request_id = case.id, row.id
    client = TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory()))
    admin = Browser(client)
    admin.login("admin.ada", arm.password, landing="Configuration")
    assert "Switch adjustments off" in admin.get("/admin").text
    assert admin.post("/admin/kill-switch", engage="on", reason="short").status_code == 409
    done = admin.post("/admin/kill-switch", engage="on", reason=REASON)
    assert "switched off" in field(done.text, "switch-state") or "Turn adjustments back on" in done.text

    sup = Browser(TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory())))
    sup.login("supervisor.sam", arm.password)
    page = sup.get(f"/cases/{case_id}")
    assert "switched off by an administrator" in page.text
    refused = sup.post(f"/adjustments/{request_id}/execute")
    assert refused.status_code == 409 and "switched off" in refused.text
    assert sup.post("/admin/kill-switch", engage="off", reason=REASON).status_code == 403


# ---------- the database's own guarantee ----------


def test_the_database_refuses_a_second_live_credit_for_a_stay(arm: ArmA) -> None:
    from sqlalchemy.exc import IntegrityError

    def row(case_id: int, status: str) -> AdjustmentRequestRow:
        return AdjustmentRequestRow(
            case_id=case_id,
            member_number=MEMBER,
            stay_id=STAY,
            points=1,
            reason_code="missing_points",
            checklist={},
            requested_by="agent.ana",
            requested_at_utc="2026-01-01T00:00:00Z",
            status=status,
        )

    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        s.add(row(case.id, "executed"))
        s.add(row(case.id, "rejected"))  # not live: allowed alongside
        s.commit()
        s.add(row(case.id, "executing"))
        with pytest.raises(IntegrityError):
            s.flush()


def test_load_request_refuses_an_unknown_id(arm: ArmA) -> None:
    with arm.sessions() as s, pytest.raises(svc.WorkflowError, match="no such"):
        load_request(s, 999)
