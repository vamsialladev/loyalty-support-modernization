"""The shared write path: supervisor decision, execution and reconciliation of a simulated adjustment (spec B.10).

Every arm uses this one path, so the safeguards are identical across arms (spec B.8). Milestone 5 builds it thin,
behind the `WritePath` interface Milestone 6 completes (ADR-0044):

- **Separation of duties:** only a supervisor decides or executes, and never on an adjustment they requested.
- **Idempotency key derived from the approval ID**, so a retry or a second click reuses the same key.
- **Cross-case duplicate check** before submitting: refuse if this app already credited (or may have credited) the
  stay from any case, or the ledger already shows an adjustment for it. It looks at adjustments only, never at
  postings, reversals, re-posts or the posting queue: judging those is each arm's job, so the platform does not
  quietly fix arm A's pre-registered defects D06 and D07.
- **Uncertain outcome -> `Execution unknown` -> status lookup by key before anything else**; never a blind retry.

- **Approval binding (ADR-0059):** an approval is an HMAC over the exact action, with an expiry. Approving re-reads the
  evidence first; executing recomputes the binding and re-reads again. Any change ends the approval.

Not yet (later steps of Milestone 6): row locks against concurrent executes, the durable worker, the kill switch and the
reconciliation job. Until then execution runs synchronously in the request.

The "A as-is" benchmark variant (Milestone 10, ADR-0051) implements `WritePath` without these safeguards and is
never reachable from the console, the API or any deployment profile.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.approval_binding import BoundAction, binding_holds, binding_mac
from app.domain.business_time import add_hours, parse_utc
from app.domain.case_states import CaseState
from app.domain.customer_records import AdjustmentRequest
from app.domain.roles import Identity, NotPermitted, approval_refusal
from app.persistence.models import AdjustmentRequestRow, Approval, Case, ExecutionAttempt
from app.ports.customer_systems import CustomerSystemError, CustomerSystems, UncertainOutcome
from app.services import approvals, policies
from app.services.arm_review import FreshReview, review_for
from app.services.cases import WorkflowError, move
from app.services.customer_config import customer_config
from app.services.instrumentation import record

IN_FLIGHT_OR_DONE = ("executing", "executed", "execution_unknown")


@dataclass(frozen=True)
class ExecutionResult:
    status: str  # applied | unknown | not_applied | refused_duplicate | rejected_upstream | invalidated
    message: str
    upstream_adjustment_id: str | None = None


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
    s.refresh(case, with_for_update=True)
    s.refresh(row)


def _permit(who: Identity, row: AdjustmentRequestRow) -> None:
    refusal = approval_refusal(who, row.requested_by)
    if refusal:
        raise NotPermitted(refusal)


def pending_approvals(s: Session, who: Identity) -> list[tuple[AdjustmentRequestRow, Case]]:
    """The supervisor's queue. Requests the viewer made themselves are listed but cannot be decided by them."""
    rows = s.scalars(
        select(AdjustmentRequestRow).where(AdjustmentRequestRow.status == "pending").order_by(AdjustmentRequestRow.id)
    )
    out = []
    for row in rows:
        case = s.get(Case, row.case_id)
        assert case is not None
        out.append((row, case))
    return out


def attempts_of(s: Session, row: AdjustmentRequestRow) -> list[ExecutionAttempt]:
    query = select(ExecutionAttempt).where(ExecutionAttempt.adjustment_request_id == row.id)
    return list(s.scalars(query.order_by(ExecutionAttempt.id)))


INVALIDATED_MESSAGE = "This approval can't stand ({reason}). The case is back under investigation."


class SharedWritePath:
    def __init__(
        self,
        customer_id: str = "hg-demo",
        *,
        secret_key: str | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.customer_id = customer_id
        self._secret_key = secret_key
        self._clock = clock

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
            self._store_decision(s, who, row, case, "rejected", reason)
            return DecisionResult("rejected", "Adjustment rejected.")
        try:
            review = self._fresh_review(s, case, row, systems)
        except CustomerSystemError as exc:
            record(s, case, who, "system_error", operation="approval_recheck", code=exc.code or type(exc).__name__)
            s.commit()
            raise WorkflowError("the evidence could not be read again, so nothing was approved; try again") from exc
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

    def execute(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        row, case = load_request(s, request_id)
        _permit(who, row)
        if CaseState(case.status) is CaseState.EXECUTION_UNKNOWN:
            return self.check_status(s, who, request_id, systems)  # reconcile first, never resubmit blindly
        approval = approval_of(s, row)
        if (
            CaseState(case.status) is not CaseState.APPROVED
            or row.status != "approved"
            or approval is None
            or approval.decision != "approved"
        ):
            raise WorkflowError("only an approved adjustment can be executed")
        unusable = self._why_unusable(row, approval)
        if unusable:
            approvals.invalidate(s, who, row, case, unusable)
            s.commit()
            return ExecutionResult("invalidated", INVALIDATED_MESSAGE.format(reason=unusable))
        key = idempotency_key(self.customer_id, approval)
        attempt = ExecutionAttempt(
            adjustment_request_id=row.id, idempotency_key=key, started_by=who.username, started_at_utc=utc_now()
        )
        try:
            duplicate = self._duplicate(s, row, systems)
        except CustomerSystemError as exc:
            record(s, case, who, "system_error", operation="duplicate_check", code=exc.code or type(exc).__name__)
            s.commit()
            raise WorkflowError("the ledger could not be checked for an earlier credit; try again") from exc
        if duplicate:
            attempt.outcome, attempt.finished_at_utc = "refused_duplicate", utc_now()
            s.add(attempt)
            row.status = "refused_duplicate"
            move(case, CaseState.ESCALATED)
            case.resolution_code, case.resolution_note = "duplicate_prevented", duplicate
            record(s, case, who, "execution_refused_duplicate")
            s.commit()
            return ExecutionResult("refused_duplicate", f"Not executed: {duplicate}. The case was escalated.")

        try:
            review = self._fresh_review(s, case, row, systems)
        except CustomerSystemError as exc:
            record(s, case, who, "system_error", operation="execution_recheck", code=exc.code or type(exc).__name__)
            s.commit()
            raise WorkflowError("the evidence could not be read again, so nothing was executed; try again") from exc
        stale, detail = self._why_stale(s, row, review)
        if stale:
            approvals.invalidate(s, who, row, case, stale, **detail)
            s.commit()
            return ExecutionResult("invalidated", INVALIDATED_MESSAGE.format(reason=stale))

        attempt.outcome = "submitted"
        s.add(attempt)
        row.status = "executing"
        move(case, CaseState.EXECUTING)
        record(s, case, who, "execution_started", points=row.points)
        s.commit()  # durable before the upstream call: a crash here leaves a visible 'Executing' case

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
        except UncertainOutcome as exc:
            attempt.outcome, attempt.error_code, attempt.finished_at_utc = "unknown", exc.code, utc_now()
            row.status = "execution_unknown"
            move(case, CaseState.EXECUTION_UNKNOWN)
            record(s, case, who, "execution_unknown", code=exc.code)
            s.commit()
            return self._reconcile(s, who, row, case, key, systems)
        except CustomerSystemError as exc:  # refused before it was applied: safe to run again later
            attempt.outcome, attempt.error_code, attempt.finished_at_utc = "rejected_upstream", exc.code, utc_now()
            row.status = "approved"
            move(case, CaseState.APPROVED)
            record(s, case, who, "system_error", operation="submit_adjustment", code=exc.code or type(exc).__name__)
            s.commit()
            return ExecutionResult("rejected_upstream", f"The loyalty platform refused the adjustment: {exc}")
        attempt.outcome, attempt.finished_at_utc = "applied", utc_now()
        attempt.upstream_adjustment_id = result.adjustment_id
        self._applied(s, who, row, case, result.adjustment_id)
        return ExecutionResult("applied", f"Adjustment {result.adjustment_id} applied.", result.adjustment_id)

    def _applied(self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, adjustment_id: str) -> None:
        row.status = "executed"
        move(case, CaseState.RESOLVED)
        case.resolution_code, case.resolution_note = "adjusted", f"{row.points} points, adjustment {adjustment_id}"
        record(s, case, who, "adjustment_executed", points=row.points, adjustment=adjustment_id)
        s.commit()

    # ---------- reconciliation ----------

    def check_status(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        row, case = load_request(s, request_id)
        _permit(who, row)
        if CaseState(case.status) is not CaseState.EXECUTION_UNKNOWN:
            raise WorkflowError("there is no uncertain execution to check")
        approval = approval_of(s, row)
        assert approval is not None
        return self._reconcile(s, who, row, case, idempotency_key(self.customer_id, approval), systems)

    def _reconcile(
        self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, key: str, systems: CustomerSystems
    ) -> ExecutionResult:
        lookup = ExecutionAttempt(
            adjustment_request_id=row.id,
            idempotency_key=key,
            started_by=who.username,
            started_at_utc=utc_now(),
            outcome="lookup",
        )
        s.add(lookup)
        try:
            found = systems.find_adjustment(key)
        except CustomerSystemError as exc:
            lookup.outcome, lookup.error_code, lookup.finished_at_utc = "unknown", exc.code, utc_now()
            record(s, case, who, "reconciliation_failed", code=exc.code or type(exc).__name__)
            s.commit()
            return ExecutionResult("unknown", "The outcome is still unknown; check the status again shortly.")
        lookup.finished_at_utc = utc_now()
        if found is not None:
            lookup.outcome, lookup.upstream_adjustment_id = "applied", found.adjustment_id
            record(s, case, who, "reconciled_applied", adjustment=found.adjustment_id)
            self._applied(s, who, row, case, found.adjustment_id)
            return ExecutionResult(
                "applied", f"Reconciled: adjustment {found.adjustment_id} was applied.", found.adjustment_id
            )
        lookup.outcome = "not_applied"
        row.status = "approved"
        move(case, CaseState.APPROVED)
        record(s, case, who, "reconciled_not_applied")
        s.commit()
        return ExecutionResult("not_applied", "Reconciled: nothing was applied. It can be executed again (same key).")
