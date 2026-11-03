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

Not yet (Milestone 6): the approval-binding hash and its invalidation, row locks or versioned updates against
concurrent executes, the durable worker, the kill switch, the reconciliation job and the append-only audit role.
Until then execution runs synchronously in the request, and an approval is not bound to an evidence snapshot.

The "A as-is" benchmark variant (Milestone 10, ADR-0051) implements `WritePath` without these safeguards and is
never reachable from the console, the API or any deployment profile.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.case_states import CaseState
from app.domain.customer_records import AdjustmentRequest
from app.domain.roles import Identity, NotPermitted, approval_refusal
from app.persistence.models import AdjustmentRequestRow, Approval, Case, ExecutionAttempt
from app.ports.customer_systems import CustomerSystemError, CustomerSystems, UncertainOutcome
from app.services.cases import WorkflowError, move
from app.services.instrumentation import record

IN_FLIGHT_OR_DONE = ("executing", "executed", "execution_unknown")


@dataclass(frozen=True)
class ExecutionResult:
    status: str  # applied | unknown | not_applied | refused_duplicate | rejected_upstream
    message: str
    upstream_adjustment_id: str | None = None


class WritePath(Protocol):
    def decide(self, s: Session, who: Identity, request_id: int, *, approve: bool, reason: str) -> None: ...

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


class SharedWritePath:
    def __init__(self, customer_id: str = "hg-demo") -> None:
        self.customer_id = customer_id

    # ---------- decision ----------

    def decide(self, s: Session, who: Identity, request_id: int, *, approve: bool, reason: str) -> None:
        row, case = load_request(s, request_id)
        _permit(who, row)
        if row.status != "pending" or CaseState(case.status) is not CaseState.PENDING_APPROVAL:
            raise WorkflowError("this adjustment has already been decided")
        if not approve and not reason.strip():
            raise WorkflowError("give the reason for rejecting")
        decision = "approved" if approve else "rejected"
        s.add(
            Approval(
                adjustment_request_id=row.id,
                uid=uuid.uuid4().hex,
                decided_by=who.username,
                decision=decision,
                reason=reason.strip() or None,
                decided_at_utc=utc_now(),
            )
        )
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
