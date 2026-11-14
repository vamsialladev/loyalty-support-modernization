"""The shared write path: decision, execution and reconciliation of a simulated adjustment (spec B.10; RFC-0001).

Every arm uses this one path, so the safeguards are identical across arms (spec B.8):

- **Separation of duties:** only a supervisor decides or executes, and never on an adjustment they requested.
- **Approval binding (ADR-0059):** an HMAC over the exact action, with an expiry. Approving and executing both re-read
  the evidence through the arm's own evaluator. Any change ends the approval.
- **One credit per stay:** a check across cases before submitting, and a partial unique index behind it. The check looks
  at adjustments only, never postings, reversals, re-posts or the queue: judging those is each arm's job, so the
  platform doesn't quietly fix arm A's pre-registered defects D06 and D07 (ADR-0044).
- **Idempotency key derived from the approval ID**, so a retry or a second click reuses the same key.
- **Uncertain outcome -> `Execution unknown` -> status lookup by key before anything else**; never a blind retry.
- **Kill switch (ADR-0061):** checked under a shared lock at the claim and again just before submitting.

Transaction boundaries in `execute` (ADR-0061). No lock is ever held across a call to a customer system:
1. Read: stored approval, duplicate check, the arm's re-check. No locks.
2. Claim: lock the case, re-check everything, record the attempt and `Executing`, commit. From here the outcome is
   treated as unknown if the process dies.
3. Last look at the switch, then submit with the key.
4. Record: lock the case, store what came back, commit.

The "A as-is" benchmark variant (Milestone 10, ADR-0051) implements `WritePath` without these safeguards and is
never reachable from the console, the API or any deployment profile.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.approval_binding import BoundAction, binding_holds, binding_mac
from app.domain.business_time import add_hours, parse_utc
from app.domain.case_states import CaseState
from app.domain.customer_records import AdjustmentRequest, AdjustmentResult
from app.domain.roles import Identity, NotPermitted, approval_refusal
from app.persistence.models import AdjustmentRequestRow, Approval, Case, ExecutionAttempt
from app.ports.customer_systems import (
    CustomerSystemError,
    CustomerSystems,
    IdempotencyConflict,
    MalformedResponse,
    RateLimited,
    SchemaMismatch,
    UncertainOutcome,
)
from app.services import approvals, jobs, kill_switch, policies, qa_sampling
from app.services.arm_review import FreshReview, review_for
from app.services.cases import WorkflowError, move
from app.services.customer_config import customer_config
from app.services.instrumentation import record

EXECUTE_JOB, RECONCILE_JOB = "execute_adjustment", "reconcile_adjustment"
IN_FLIGHT_OR_DONE = ("executing", "executed", "execution_unknown", "execution_conflict")
# A response that arrived but can't be read: the write probably applied (RFC-0001, fault 1).
MAY_HAVE_APPLIED = (UncertainOutcome, MalformedResponse, SchemaMismatch)
ABSENT_LOOKUPS_NEEDED = 2
DEFAULT_SETTLE_SECONDS = 60.0  # an assumption: how long a platform's lookup might lag a write (swap guide)
EXECUTION_OFF_MESSAGE = (
    "Adjustment execution is switched off in this deployment (FEATURE_ADJUSTMENT_EXECUTION). The approval stands; "
    "nothing was sent to the loyalty platform."
)
SUBMIT_OUTCOMES = ("submitted", "unknown", "rejected_upstream", "busy", "held", "conflict")


class RecheckFailed(WorkflowError):
    """A customer system couldn't be read for the re-check, so nothing changed. Safe to try again."""


@dataclass(frozen=True)
class ExecutionResult:
    # applied | unknown | not_applied | refused_duplicate | rejected_upstream | invalidated | conflict | held | retry
    # | in_flight | queued
    status: str
    message: str
    upstream_adjustment_id: str | None = None
    retry_after_seconds: float | None = None


@dataclass(frozen=True)
class DecisionResult:
    status: str  # approved | rejected | invalidated
    message: str


class WritePath(Protocol):
    def decide(
        self, s: Session, who: Identity, request_id: int, systems: CustomerSystems, *, approve: bool, reason: str
    ) -> DecisionResult: ...

    def execute(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult: ...

    def check_status(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult: ...


def idempotency_key(customer_id: str, approval: Approval) -> str:
    """Deterministic from the approval (Appendix B): every execute of one approval sends the same key. Built from the
    approval's stored random ID rather than its row number, so it stays unique across database resets."""
    return f"lsm-{customer_id}-approval-{approval.uid}"


def load_request(s: Session, request_id: int) -> tuple[AdjustmentRequestRow, Case]:
    row = s.get(AdjustmentRequestRow, request_id)
    if row is None:
        raise WorkflowError("no such adjustment request")
    case = s.get(Case, row.case_id)
    assert case is not None
    return row, case


def approval_of(s: Session, row: AdjustmentRequestRow) -> Approval | None:
    return s.scalars(select(Approval).where(Approval.adjustment_request_id == row.id)).first()


def _lock(s: Session, case: Case, row: AdjustmentRequestRow) -> None:
    """Lock the case and read it and its request again. Every change to a case in flight happens under this lock."""
    s.refresh(case, with_for_update={"key_share": True})  # FOR NO KEY UPDATE: see `instrumentation.record`
    s.refresh(row)


def _permit(who: Identity, row: AdjustmentRequestRow) -> None:
    refusal = approval_refusal(who, row.requested_by)
    if refusal:
        raise NotPermitted(refusal)


def pending_approvals(s: Session, who: Identity) -> list[tuple[AdjustmentRequestRow, Case]]:
    """The supervisor's queue, for their own customer only (spec C.5). Requests the viewer made themselves are listed
    but cannot be decided by them."""
    rows = s.scalars(
        select(AdjustmentRequestRow).where(AdjustmentRequestRow.status == "pending").order_by(AdjustmentRequestRow.id)
    )
    out = []
    for row in rows:
        case = s.get(Case, row.case_id)
        assert case is not None
        if case.customer_id == who.customer_id:
            out.append((row, case))
    return out


def attempts_of(s: Session, row: AdjustmentRequestRow) -> list[ExecutionAttempt]:
    query = select(ExecutionAttempt).where(ExecutionAttempt.adjustment_request_id == row.id)
    return list(s.scalars(query.order_by(ExecutionAttempt.id)))


def _matches(found: AdjustmentResult, row: AdjustmentRequestRow) -> bool:
    return (found.member_number, found.stay_id, found.points) == (row.member_number, row.stay_id, row.points)


INVALIDATED_MESSAGE = "This approval can't stand ({reason}). The case is back under investigation."
CONFLICT_MESSAGE = "The loyalty platform holds a different record under this approval's key. The case was escalated."


class SharedWritePath:
    def __init__(
        self,
        customer_id: str = "hg-demo",
        *,
        secret_key: str | None = None,
        clock: Callable[[], str] = utc_now,
        settle_seconds: float = DEFAULT_SETTLE_SECONDS,
        execution_enabled: bool = True,
    ) -> None:
        self.customer_id = customer_id
        self._secret_key = secret_key
        self._clock = clock
        self._settle_seconds = settle_seconds
        # FEATURE_ADJUSTMENT_EXECUTION (spec F.1; OPS-05, ADR-0081). Off: nothing is sent to the loyalty platform;
        # approved requests wait, exactly as under the kill switch, and reconciliation still runs.
        self.execution_enabled = execution_enabled

    @property
    def _secret(self) -> str:
        secret = self._secret_key or os.environ.get("APP_SECRET_KEY", "")
        if not secret:
            raise WorkflowError("APP_SECRET_KEY is not set, so approvals can't be bound")
        return secret

    # ---------- the binding ----------

    def _bound_action(self, row: AdjustmentRequestRow, approval: Approval) -> BoundAction:
        return BoundAction(
            self.customer_id,
            row.id,
            approval.uid,
            row.member_number,
            row.stay_id,
            row.points,
            row.reason_code,
            tuple(row.policy_refs or ()),
            row.evidence_hash or "",
            approval.decided_by,
            approval.expires_at_utc or "",
        )

    def _fresh_review(self, s: Session, case: Case, row: AdjustmentRequestRow, systems: CustomerSystems) -> FreshReview:
        return review_for(case).review(s, case, row.stay_id, systems, case.sim_now_utc or self._clock())

    def _why_stale(self, s: Session, row: AdjustmentRequestRow, review: FreshReview) -> tuple[str, dict[str, object]]:
        """Why this request no longer matches the world, or ("", {}) if it still does."""
        if row.evidence_hash is None or row.policy_refs is None or row.checkout_day is None:
            return "not_bound", {}
        if not review.still_adjust:
            return "outcome_changed", {"outcome": review.outcome}
        if review.points != row.points:
            return "amount_changed", {"bound": row.points, "now": review.points}
        if review.evidence_hash != row.evidence_hash:
            return "evidence_changed", {}
        in_force = policies.claim_policy_refs(s, self.customer_id, date.fromisoformat(row.checkout_day))
        if in_force != row.policy_refs:
            return "policy_changed", {"bound": row.policy_refs, "in_force": in_force}
        return "", {}

    def _why_unusable(self, row: AdjustmentRequestRow, approval: Approval) -> str:
        """Checks that need no customer system: the stored approval itself."""
        if not binding_holds(self._bound_action(row, approval), self._secret, approval.binding_mac):
            return "binding_mismatch"
        if parse_utc(self._clock()) >= parse_utc(approval.expires_at_utc or self._clock()):
            return "expired"
        return ""

    # ---------- decision ----------

    def decide(
        self, s: Session, who: Identity, request_id: int, systems: CustomerSystems, *, approve: bool, reason: str
    ) -> DecisionResult:
        row, case = load_request(s, request_id)
        _permit(who, row)
        if row.status != "pending" or CaseState(case.status) is not CaseState.PENDING_APPROVAL:
            raise WorkflowError("this adjustment has already been decided")
        if not approve:
            if not reason.strip():
                raise WorkflowError("give the reason for rejecting")
            _lock(s, case, row)
            if row.status != "pending" or CaseState(case.status) is not CaseState.PENDING_APPROVAL:
                raise WorkflowError("this adjustment has already been decided or was invalidated")
            self._store_decision(s, who, row, case, "rejected", reason)
            return DecisionResult("rejected", "Adjustment rejected.")
        try:
            review = self._fresh_review(s, case, row, systems)
        except CustomerSystemError as exc:
            record(s, case, who, "system_error", operation="approval_recheck", code=exc.code or type(exc).__name__)
            s.commit()
            raise RecheckFailed("the evidence could not be read again, so nothing was approved; try again") from exc
        _lock(s, case, row)  # after the reads, so no lock is held across a call to a customer system
        if row.status != "pending" or CaseState(case.status) is not CaseState.PENDING_APPROVAL:
            raise WorkflowError("this adjustment has already been decided or was invalidated")
        stale, detail = self._why_stale(s, row, review)
        if stale:
            approvals.invalidate(s, who, row, case, stale, **detail)
            s.commit()
            return DecisionResult("invalidated", INVALIDATED_MESSAGE.format(reason=stale))
        self._store_decision(s, who, row, case, "approved", reason)
        return DecisionResult("approved", "Adjustment approved.")

    def _store_decision(
        self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, decision: str, reason: str
    ) -> None:
        approve = decision == "approved"
        now = self._clock()
        approval = Approval(
            adjustment_request_id=row.id,
            uid=uuid.uuid4().hex,
            decided_by=who.username,
            decision=decision,
            reason=reason.strip() or None,
            decided_at_utc=now,
        )
        if approve:
            approval.expires_at_utc = add_hours(now, customer_config(self.customer_id).approval_ttl_hours)
            approval.binding_mac = binding_mac(self._bound_action(row, approval), self._secret)
        s.add(approval)
        row.status = decision
        move(case, CaseState.APPROVED if approve else CaseState.REJECTED)
        if not approve:
            case.resolution_code, case.resolution_note = "rejected", reason.strip()
        record(s, case, who, f"adjustment_{decision}", points=row.points)
        s.commit()

    # ---------- asking for execution: the job commits with the request or not at all ----------

    def request_execution(self, s: Session, who: Identity, request_id: int) -> ExecutionResult:
        """What the console does. Queues the work for the worker; the case page shows how it went (ADR-0055, D1)."""
        row, case = load_request(s, request_id)
        _permit(who, row)
        _lock(s, case, row)
        state = CaseState(case.status)
        if state is CaseState.EXECUTION_UNKNOWN:
            jobs.enqueue(s, RECONCILE_JOB, {"request_id": row.id, "user_id": who.user_id}, case_id=case.id)
            s.commit()
            return ExecutionResult("queued", "Checking the loyalty platform for the earlier attempt.")
        approval = approval_of(s, row)
        if state is not CaseState.APPROVED or row.status != "approved" or approval is None:
            raise WorkflowError("only an approved adjustment can be executed")
        if not self.execution_enabled:
            s.rollback()
            raise WorkflowError(EXECUTION_OFF_MESSAGE)
        if kill_switch.is_engaged_for_claim(s):
            s.rollback()
            raise WorkflowError(kill_switch.MESSAGE)
        unusable = self._why_unusable(row, approval)
        if unusable:
            approvals.invalidate(s, who, row, case, unusable)
            s.commit()
            return ExecutionResult("invalidated", INVALIDATED_MESSAGE.format(reason=unusable))
        job = jobs.enqueue(s, EXECUTE_JOB, {"request_id": row.id, "user_id": who.user_id}, case_id=case.id)
        record(s, case, who, "execution_requested", job=job.id, points=row.points)
        s.commit()
        return ExecutionResult("queued", "Queued. The case page shows the result.")

    # ---------- execution ----------

    def _duplicate(self, s: Session, row: AdjustmentRequestRow, systems: CustomerSystems) -> str | None:
        other = s.scalars(
            select(AdjustmentRequestRow).where(
                AdjustmentRequestRow.stay_id == row.stay_id,
                AdjustmentRequestRow.id != row.id,
                AdjustmentRequestRow.status.in_(IN_FLIGHT_OR_DONE),
            )
        ).first()
        if other is not None:
            other_case = s.get(Case, other.case_id)
            ref = other_case.reference if other_case else "another case"
            return f"case {ref} has already credited, or may have credited, stay {row.stay_id}"
        for entry in systems.get_ledger(row.member_number):
            if entry.kind == "adjustment" and entry.stay_id == row.stay_id:
                return f"the ledger already shows adjustment {entry.entry_id} for stay {row.stay_id}"
        return None

    def _refuse_duplicate(
        self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, key: str, duplicate: str
    ) -> ExecutionResult:
        now = self._clock()
        s.add(
            ExecutionAttempt(
                adjustment_request_id=row.id,
                idempotency_key=key,
                started_by=who.username,
                started_at_utc=now,
                finished_at_utc=now,
                outcome="refused_duplicate",
            )
        )
        row.status = "refused_duplicate"
        move(case, CaseState.ESCALATED)
        case.resolution_code, case.resolution_note = "duplicate_prevented", duplicate
        record(s, case, who, "execution_refused_duplicate")
        s.commit()
        return ExecutionResult("refused_duplicate", f"Not executed: {duplicate}. The case was escalated.")

    def execute(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        """The work itself, safe to repeat. The worker calls this; so does the scripted agent, which has no worker."""
        row, case = load_request(s, request_id)
        s.refresh(case)
        s.refresh(row)
        _permit(who, row)
        state = CaseState(case.status)
        if state is CaseState.EXECUTION_UNKNOWN:
            return self.check_status(s, who, request_id, systems)  # reconcile first, never resubmit blindly
        if state is CaseState.EXECUTING:
            return ExecutionResult("in_flight", "Another attempt is in progress.")
        approval = approval_of(s, row)
        if state is not CaseState.APPROVED or row.status != "approved" or approval is None:
            raise WorkflowError("only an approved adjustment can be executed")
        if approval.decision != "approved":
            raise WorkflowError("only an approved adjustment can be executed")
        if not self.execution_enabled:
            return ExecutionResult("held", EXECUTION_OFF_MESSAGE)
        if kill_switch.is_engaged(s):
            return ExecutionResult("held", kill_switch.MESSAGE)
        unusable = self._why_unusable(row, approval)
        if unusable:
            _lock(s, case, row)
            if CaseState(case.status) is not CaseState.APPROVED or row.status != "approved":
                return ExecutionResult("in_flight", "Another attempt moved this case on.")
            approvals.invalidate(s, who, row, case, unusable)
            s.commit()
            return ExecutionResult("invalidated", INVALIDATED_MESSAGE.format(reason=unusable))
        key = idempotency_key(self.customer_id, approval)

        # Step 1: reads. No lock is held across these calls.
        try:
            duplicate = self._duplicate(s, row, systems)
            review = None if duplicate else self._fresh_review(s, case, row, systems)
        except CustomerSystemError as exc:
            record(s, case, who, "system_error", operation="execution_recheck", code=exc.code or type(exc).__name__)
            s.commit()
            raise RecheckFailed(
                "the ledger or evidence could not be read again, so nothing was executed; try again"
            ) from exc

        # Step 2: claim.
        _lock(s, case, row)
        if CaseState(case.status) is not CaseState.APPROVED or row.status != "approved":
            s.commit()
            return ExecutionResult("in_flight", "Another attempt moved this case on.")
        if duplicate:
            return self._refuse_duplicate(s, who, row, case, key, duplicate)
        assert review is not None
        stale, detail = self._why_stale(s, row, review)
        if stale:
            approvals.invalidate(s, who, row, case, stale, **detail)
            s.commit()
            return ExecutionResult("invalidated", INVALIDATED_MESSAGE.format(reason=stale))
        if kill_switch.is_engaged_for_claim(s):
            s.commit()
            return ExecutionResult("held", kill_switch.MESSAGE)
        attempt = ExecutionAttempt(
            adjustment_request_id=row.id,
            idempotency_key=key,
            started_by=who.username,
            started_at_utc=self._clock(),
            outcome="submitted",
        )
        try:
            s.add(attempt)
            row.status = "executing"
            move(case, CaseState.EXECUTING)
            record(s, case, who, "execution_started", points=row.points)  # flushes, so the index can refuse here too
            s.commit()  # durable before the upstream call: a crash from here on leaves a visible 'Executing' case
        except IntegrityError:  # the partial unique index: another case's credit for this stay won the race
            s.rollback()
            _lock(s, case, row)
            if CaseState(case.status) is not CaseState.APPROVED:
                return ExecutionResult("in_flight", "Another attempt moved this case on.")
            message = f"another case has already credited, or may have credited, stay {row.stay_id}"
            return self._refuse_duplicate(s, who, row, case, key, message)

        # Step 3: the last look at the switch, then submit. The read is closed first, so no transaction stays open.
        held = kill_switch.is_engaged(s)
        s.commit()
        if held:
            return self._release_held(s, who, row, case, attempt)
        request = AdjustmentRequest(
            member_number=row.member_number,
            stay_id=row.stay_id,
            points=row.points,
            reason_code=row.reason_code,
            requested_by=row.requested_by,
            note=f"case {case.reference}, approved by {approval.decided_by}",
        )
        try:
            result = systems.submit_adjustment(request, key)
        except MAY_HAVE_APPLIED as exc:
            return self._record_unknown(s, who, row, case, attempt, key, systems, exc.code)
        except IdempotencyConflict as exc:
            _lock(s, case, row)
            attempt.outcome, attempt.error_code, attempt.finished_at_utc = "conflict", exc.code, self._clock()
            return self._conflict(s, who, row, case, code=exc.code)
        except CustomerSystemError as exc:  # refused before it was applied: safe to run again later
            return self._record_refused(s, who, row, case, attempt, exc)
        # Step 4: record.
        _lock(s, case, row)
        attempt.upstream_adjustment_id, attempt.finished_at_utc = result.adjustment_id, self._clock()
        if not _matches(result, row):
            attempt.outcome = "conflict"
            return self._conflict(s, who, row, case, code="record_mismatch")
        attempt.outcome = "applied"
        self._applied(s, who, row, case, result.adjustment_id)
        return ExecutionResult("applied", f"Adjustment {result.adjustment_id} applied.", result.adjustment_id)

    def _release_held(
        self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, attempt: ExecutionAttempt
    ) -> ExecutionResult:
        _lock(s, case, row)
        attempt.outcome, attempt.finished_at_utc = "held", self._clock()
        if CaseState(case.status) is CaseState.EXECUTING:
            row.status = "approved"
            move(case, CaseState.APPROVED)
        record(s, case, who, "execution_held")
        s.commit()
        return ExecutionResult("held", kill_switch.MESSAGE)

    def _record_unknown(
        self,
        s: Session,
        who: Identity,
        row: AdjustmentRequestRow,
        case: Case,
        attempt: ExecutionAttempt,
        key: str,
        systems: CustomerSystems,
        code: str,
    ) -> ExecutionResult:
        _lock(s, case, row)
        attempt.outcome, attempt.error_code, attempt.finished_at_utc = "unknown", code, self._clock()
        if CaseState(case.status) is CaseState.EXECUTING:
            row.status = "execution_unknown"
            move(case, CaseState.EXECUTION_UNKNOWN)
            record(s, case, who, "execution_unknown", code=code)
        s.commit()
        return self._reconcile(s, who, row, case, key, systems)

    def _record_refused(
        self,
        s: Session,
        who: Identity,
        row: AdjustmentRequestRow,
        case: Case,
        attempt: ExecutionAttempt,
        exc: CustomerSystemError,
    ) -> ExecutionResult:
        _lock(s, case, row)
        busy = exc.retryable
        attempt.outcome, attempt.error_code = ("busy" if busy else "rejected_upstream"), exc.code
        attempt.finished_at_utc = self._clock()
        if CaseState(case.status) is CaseState.EXECUTING:
            row.status = "approved"
            move(case, CaseState.APPROVED)
        record(s, case, who, "system_error", operation="submit_adjustment", code=exc.code or type(exc).__name__)
        s.commit()
        if busy:
            wait = exc.retry_after_seconds if isinstance(exc, RateLimited) else None
            return ExecutionResult("retry", "The loyalty platform is busy; trying again shortly.", None, wait)
        return ExecutionResult("rejected_upstream", f"The loyalty platform refused the adjustment: {exc}")

    def _conflict(
        self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, *, code: str
    ) -> ExecutionResult:
        """Something other than what was approved sits under this key. The stay stays blocked; a person looks at it."""
        row.status = "execution_conflict"
        if CaseState(case.status) in (CaseState.EXECUTING, CaseState.EXECUTION_UNKNOWN):
            move(case, CaseState.ESCALATED)
            case.resolution_code, case.resolution_note = "execution_conflict", CONFLICT_MESSAGE
        record(s, case, who, "execution_conflict", code=code)
        s.commit()
        return ExecutionResult("conflict", CONFLICT_MESSAGE)

    def _applied(self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, adjustment_id: str) -> None:
        if CaseState(case.status) in (CaseState.EXECUTING, CaseState.EXECUTION_UNKNOWN):
            row.status = "executed"
            move(case, CaseState.RESOLVED)
            case.resolution_code, case.resolution_note = "adjusted", f"{row.points} points, adjustment {adjustment_id}"
            record(s, case, who, "adjustment_executed", points=row.points, adjustment=adjustment_id)
            qa_sampling.consider(s, case, row.requested_by)  # the requester's work is what QA reviews (ENT-18)
        s.commit()

    # ---------- recovery and reconciliation ----------

    def recover_interrupted(self, s: Session, request_id: int) -> None:
        """A worker died in `Executing`. It may have submitted, so the outcome is unknown; reconciliation decides."""
        row, case = load_request(s, request_id)
        _lock(s, case, row)
        if CaseState(case.status) is not CaseState.EXECUTING:
            s.commit()
            return
        for attempt in attempts_of(s, row):
            if attempt.outcome == "submitted":
                attempt.outcome, attempt.error_code, attempt.finished_at_utc = "unknown", "worker_lost", self._clock()
        row.status = "execution_unknown"
        move(case, CaseState.EXECUTION_UNKNOWN)
        record(s, case, jobs.SYSTEM, "execution_unknown", code="worker_lost")
        s.commit()

    def check_status(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        row, case = load_request(s, request_id)
        s.refresh(case)
        s.refresh(row)
        _permit(who, row)
        if CaseState(case.status) is not CaseState.EXECUTION_UNKNOWN:
            raise WorkflowError("there is no uncertain execution to check")
        approval = approval_of(s, row)
        assert approval is not None
        return self._reconcile(s, who, row, case, idempotency_key(self.customer_id, approval), systems)

    def reconcile_as_system(self, s: Session, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        """The same lookup, by the worker. It changes nothing a person's approval didn't already cover."""
        row, case = load_request(s, request_id)
        s.refresh(case)
        s.refresh(row)
        if CaseState(case.status) is not CaseState.EXECUTION_UNKNOWN:
            return ExecutionResult("in_flight", "Nothing uncertain to check.")
        approval = approval_of(s, row)
        assert approval is not None
        return self._reconcile(s, jobs.SYSTEM, row, case, idempotency_key(self.customer_id, approval), systems)

    def _settled(self, s: Session, row: AdjustmentRequestRow) -> bool:
        """True when "not found" can be believed: enough lookups found nothing, and enough time has passed since the
        last submission for a lagging platform to show it (RFC-0001, fault 4)."""
        attempts = attempts_of(s, row)
        last_submit = None
        absent = 0
        for attempt in reversed(attempts):
            if attempt.outcome in SUBMIT_OUTCOMES:
                last_submit = attempt
                break
            if attempt.outcome == "absent":
                absent += 1
        if last_submit is None or absent < ABSENT_LOOKUPS_NEEDED:
            return False
        submitted_at = parse_utc(last_submit.finished_at_utc or last_submit.started_at_utc)
        return parse_utc(self._clock()) >= submitted_at + timedelta(seconds=self._settle_seconds)

    def _reconcile(
        self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, key: str, systems: CustomerSystems
    ) -> ExecutionResult:
        lookup = ExecutionAttempt(
            adjustment_request_id=row.id,
            idempotency_key=key,
            started_by=who.username,
            started_at_utc=self._clock(),
            outcome="lookup",
        )
        s.add(lookup)
        s.commit()  # no transaction stays open across the call below
        try:
            found = systems.find_adjustment(key)
        except CustomerSystemError as exc:
            _lock(s, case, row)
            lookup.outcome, lookup.error_code, lookup.finished_at_utc = "lookup_failed", exc.code, self._clock()
            record(s, case, who, "reconciliation_failed", code=exc.code or type(exc).__name__)
            s.commit()
            return ExecutionResult("unknown", "The outcome is still unknown; check the status again shortly.")
        _lock(s, case, row)
        lookup.finished_at_utc = self._clock()
        if CaseState(case.status) is not CaseState.EXECUTION_UNKNOWN:
            lookup.outcome = "applied" if found else "absent"
            s.commit()
            return ExecutionResult("in_flight", "Another attempt settled this case.")
        if found is not None:
            lookup.upstream_adjustment_id = found.adjustment_id
            if not _matches(found, row):
                lookup.outcome = "conflict"
                record(s, case, who, "reconciled_conflict", adjustment=found.adjustment_id)
                return self._conflict(s, who, row, case, code="record_mismatch")
            lookup.outcome = "applied"
            record(s, case, who, "reconciled_applied", adjustment=found.adjustment_id)
            self._applied(s, who, row, case, found.adjustment_id)
            return ExecutionResult(
                "applied", f"Reconciled: adjustment {found.adjustment_id} was applied.", found.adjustment_id
            )
        lookup.outcome = "absent"
        s.flush()
        if not self._settled(s, row):
            record(s, case, who, "reconciled_not_found_yet")
            s.commit()
            return ExecutionResult("unknown", "Not found yet. It may still appear; checking again shortly.")
        lookup.outcome = "not_applied"
        row.status = "approved"
        move(case, CaseState.APPROVED)
        record(s, case, who, "reconciled_not_applied")
        s.commit()
        return ExecutionResult("not_applied", "Reconciled: nothing was applied. It can be executed again (same key).")
