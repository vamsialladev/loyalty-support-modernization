"""Invalidating approvals (spec B.6, B.10; WP-06, POL-05; ADR-0059).

A changed amount, member, stay, policy or relevant evidence ends an approval. The case goes back to `Investigating`, and
the approval is never revived: a new request, a new approval and a new idempotency key follow (ADR-0055, D2). Only cases
in `Pending approval` or `Approved` qualify: anything further on has already reached the customer's system, so
reconciliation decides what happened, not this.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.case_states import CaseState
from app.domain.roles import Identity
from app.persistence.models import AdjustmentRequestRow, Case
from app.services import policies
from app.services.cases import move
from app.services.instrumentation import record

OPEN_STATUSES = ("pending", "approved")
OPEN_CASE_STATES = (CaseState.PENDING_APPROVAL.value, CaseState.APPROVED.value)


def invalidate(s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, reason: str, **detail: object) -> None:
    """Does not commit: the caller's transaction includes it. `reason` is a short code, shown to people."""
    row.status = "invalidated"
    row.invalidated_at_utc, row.invalidated_reason = utc_now(), reason
    move(case, CaseState.INVESTIGATING)
    record(s, case, who, "approval_invalidated", reason=reason, request=row.id, **detail)


def invalidate_for_policy_change(s: Session, who: Identity, customer_id: str) -> list[int]:
    """Called inside the publish transaction, so the approvals end the moment the policy applies. Only those whose
    in-force versions actually changed: a future-dated version touches none. Returns the request IDs it ended."""
    rows = s.scalars(
        select(AdjustmentRequestRow)
        .join(Case, Case.id == AdjustmentRequestRow.case_id)
        .where(
            Case.customer_id == customer_id,
            Case.status.in_(OPEN_CASE_STATES),
            AdjustmentRequestRow.status.in_(OPEN_STATUSES),
        )
        .order_by(AdjustmentRequestRow.case_id)  # one order for every locker, so two publishes can't deadlock
    ).all()
    ended = []
    for row in rows:
        case = s.get(Case, row.case_id, with_for_update={"key_share": True}, populate_existing=True)
        assert case is not None
        if case.status not in OPEN_CASE_STATES or row.status not in OPEN_STATUSES:
            continue  # it moved on while we waited for the lock
        current = policies.claim_policy_refs(s, customer_id, date.fromisoformat(row.checkout_day or "1900-01-01"))
        if current != row.policy_refs:
            invalidate(s, who, row, case, "policy_changed", bound=row.policy_refs, in_force=current)
            ended.append(row.id)
    return ended
