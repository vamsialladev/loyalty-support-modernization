"""The re-check before approval and before execution: each arm re-runs its evaluator on fresh reads (ADR-0044, WP-07).

Milestones 7 and 8 add arms B and C here, using the eligibility engine and their own view of the evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from sqlalchemy.orm import Session

from app.arms.legacy.checklist import Outcome, evaluate
from app.arms.legacy.revalidation import evidence_facts, fresh_evidence
from app.arms.legacy.rules import LegacyRules
from app.domain.approval_binding import evidence_hash
from app.persistence.models import Case
from app.ports.customer_systems import CustomerSystems
from app.services.cases import ARM_A, WorkflowError, current_evidence


@dataclass(frozen=True)
class FreshReview:
    still_adjust: bool
    points: int | None
    outcome: str
    evidence_hash: str


class ArmReview(Protocol):
    def review(self, s: Session, case: Case, stay_id: str, systems: CustomerSystems, as_of_utc: str) -> FreshReview: ...


class LegacyReview:
    def __init__(self, rules: LegacyRules) -> None:
        self.rules = rules

    def review(self, s: Session, case: Case, stay_id: str, systems: CustomerSystems, as_of_utc: str) -> FreshReview:
        fresh = fresh_evidence(systems, current_evidence(s, case), as_of_utc)
        checklist = evaluate(fresh, case.received_at_utc, self.rules)
        return FreshReview(
            checklist.outcome is Outcome.ADJUST,
            checklist.points_owed,
            checklist.outcome.value,
            evidence_hash(evidence_facts(fresh, stay_id)),
        )


@lru_cache(maxsize=8)
def _legacy_review(customer_id: str) -> LegacyReview:
    return LegacyReview(LegacyRules.load(customer_id))


def review_for(case: Case) -> ArmReview:
    if case.arm == ARM_A:
        return _legacy_review(case.customer_id)
    raise WorkflowError(f"no re-check is defined for arm {case.arm}")
