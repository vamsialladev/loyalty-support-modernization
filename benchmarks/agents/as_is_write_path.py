"""The legacy write path, for the "A as-is" variant ONLY (catalog section 2b; ADR-0018; LGF-16). **Unsafe by design.**

It measures what the shared write path prevents on its own. An approval is a status flag with no binding, nothing
re-checks the ledger before an adjustment, there's no cross-case duplicate check, and each attempt gets a fresh
idempotency key, so a retry after a timeout is a new request.

It runs only inside the benchmark runner, against a disposable database, and refuses anything else. The app can't import
it (`tests/test_generator.py`), and it's excluded from H1 to H6.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.case_states import CaseState
from app.domain.customer_records import AdjustmentRequest
from app.domain.roles import Identity
from app.persistence.models import AdjustmentRequestRow, Approval, Case, ExecutionAttempt
from app.ports.customer_systems import CustomerSystems, UncertainOutcome
from app.services.cases import move
from app.services.instrumentation import record
from app.services.write_path import DecisionResult, ExecutionResult, load_request


class NotDisposable(Exception):
    pass


def refuse_unless_disposable(database_path: Path) -> None:
    """A temp-folder SQLite file, or nothing."""
    root = Path(tempfile.gettempdir()).resolve()
    if root not in database_path.resolve().parents:
        raise NotDisposable(f"A as-is only runs on a disposable database under {root}")


class AsIsWritePath:
    def __init__(self, database_path: Path) -> None:
        refuse_unless_disposable(database_path)

    def decide(
        self, s: Session, who: Identity, request_id: int, systems: CustomerSystems, *, approve: bool, reason: str
    ) -> DecisionResult:
        row, case = load_request(s, request_id)
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
        return DecisionResult(decision, "Decision stored as a status flag (legacy path).")

    def execute(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        row, case = load_request(s, request_id)
        request = AdjustmentRequest(
            member_number=row.member_number,
            stay_id=row.stay_id,
            points=row.points,
            reason_code=row.reason_code,
            requested_by=row.requested_by,
            note=f"case {case.reference}",
        )
        move(case, CaseState.EXECUTING)
        record(s, case, who, "execution_started", points=row.points)
        s.commit()
        for attempts_left in (1, 0):
            key = f"as-is-{uuid.uuid4().hex}"  # fresh on every attempt: the defect this variant measures
            s.add(
                ExecutionAttempt(
                    adjustment_request_id=row.id,
                    idempotency_key=key,
                    started_by=who.username,
                    started_at_utc=utc_now(),
                    outcome="submitted",
                )
            )
            s.commit()
            try:
                result = systems.submit_adjustment(request, key)
            except UncertainOutcome:
                if attempts_left:
                    continue  # no lookup first: a retry is a new request
                raise
            return self._applied(s, who, row, case, result.adjustment_id)
        raise AssertionError("the loop returns or raises")

    def _applied(
        self, s: Session, who: Identity, row: AdjustmentRequestRow, case: Case, adjustment_id: str
    ) -> ExecutionResult:
        row.status = "executed"
        move(case, CaseState.RESOLVED)
        case.resolution_code, case.resolution_note = "adjusted", f"{row.points} points, adjustment {adjustment_id}"
        record(s, case, who, "adjustment_executed", points=row.points, adjustment=adjustment_id)
        s.commit()
        return ExecutionResult("applied", f"Adjustment {adjustment_id} applied (legacy path).", adjustment_id)

    def check_status(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        return ExecutionResult("applied", "The legacy path has no status check.")
