"""Online quality sampling for human QA (spec E5; ENT-18).

A configurable share of closed cases is queued for a person to review against the QA rubric (`docs/qa-rubric.md`,
proposed until it's calibrated in user acceptance testing, Milestone 18). Results live in their own table and are
**never** mixed with the offline evaluation: the benchmark runner doesn't read them, and they don't become labels
without the label-review step (ENT-21).

Which cases: those in the configured arms (default: C, the AI-assisted arm), chosen by a keyed hash of the case
reference, so the choice is repeatable, can't be steered by whoever closes the case, and needs no scheduler. Scripted
benchmark cases are never sampled. The reviewer can't be the person who closed the case.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.roles import Identity, NotPermitted, Role
from app.persistence.models import Case, QaSample
from app.services.customer_config import customer_config
from app.services.instrumentation import SCRIPTED_PREFIX, record

PENDING, REVIEWED = "pending", "reviewed"
REVIEWERS = (Role.SUPERVISOR, Role.AUDITOR)
# The rubric's items and their allowed answers (docs/qa-rubric.md). Codes only: no free text, so a review holds no
# personal data.
RUBRIC: dict[str, tuple[str, ...]] = {
    "outcome": ("right", "wrong", "unsure"),
    "evidence": ("complete", "missing", "wrong"),
    "policy_cited": ("right", "wrong", "none_needed"),
    "explanation": ("clear", "unclear", "misleading"),
    "member_message": ("ready", "needs_edit", "wrong"),
}


@dataclass(frozen=True)
class SamplingConfig:
    rate_percent: float = 10.0
    arms: tuple[str, ...] = ("C",)
    key: bytes = b"qa-sampling"  # set from APP_SECRET_KEY, so nobody can predict which cases are picked


def config_for(customer_id: str) -> SamplingConfig:
    """From the customer's `monitoring` section (ADR-0078). No section means a rate of 0: nothing is sampled."""
    config = customer_config(customer_id)
    key = os.environ.get("APP_SECRET_KEY", "").encode() or f"qa-sampling:{customer_id}".encode()
    return SamplingConfig(config.qa_sample_percent, config.qa_sample_arms, key)


def chosen(reference: str, config: SamplingConfig) -> bool:
    """A keyed hash of the reference, as a number from 0 to 9999, below the rate. 10% picks about 1 case in 10."""
    digest = hmac.new(config.key, reference.encode(), hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big") % 10_000 < round(config.rate_percent * 100)


def consider(s: Session, case: Case, closed_by: str, config: SamplingConfig | None = None) -> QaSample | None:
    """Called in the same transaction that resolves a case, on all three paths: arm A's close, arm B and C's close,
    and an executed adjustment. `closed_by` is the person whose work it was (for an execution: who requested it).
    Adds a pending sample if this case is chosen."""
    config = config or config_for(case.customer_id)
    if case.arm not in config.arms or closed_by.startswith(SCRIPTED_PREFIX):
        return None
    if not chosen(case.reference, config):
        return None
    sample = QaSample(
        case_id=case.id,
        arm=case.arm,
        rate_percent=config.rate_percent,
        status=PENDING,
        closed_by=closed_by,
        sampled_at_utc=utc_now(),
    )
    try:
        with s.begin_nested():
            s.add(sample)
            s.flush()
    except IntegrityError:  # already sampled: a reopened case closing again keeps its first sample
        return None
    return sample


def require_reviewer(who: Identity) -> None:
    if who.role not in REVIEWERS:
        raise NotPermitted("only supervisors and auditors review QA samples")


def pending(s: Session, who: Identity, limit: int = 50) -> list[QaSample]:
    require_reviewer(who)
    query = (
        select(QaSample)
        .join(Case, Case.id == QaSample.case_id)
        .where(QaSample.status == PENDING, Case.customer_id == who.customer_id)
        .order_by(QaSample.id)
        .limit(limit)
    )
    return list(s.scalars(query))


class InvalidReview(ValueError):
    pass


def review(s: Session, who: Identity, sample_id: int, answers: dict[str, str]) -> QaSample:
    require_reviewer(who)
    sample = s.get(QaSample, sample_id)
    case = s.get(Case, sample.case_id) if sample else None
    if sample is None or case is None or case.customer_id != who.customer_id:
        raise NotPermitted("no such QA sample")
    if sample.status != PENDING:
        raise InvalidReview("already reviewed")
    if who.username == sample.closed_by:
        raise NotPermitted("the person who closed the case can't review it")
    if set(answers) != set(RUBRIC):
        raise InvalidReview("answer every rubric item, and nothing else: " + ", ".join(RUBRIC))
    wrong = sorted(k for k, v in answers.items() if v not in RUBRIC[k])
    if wrong:
        raise InvalidReview("not an allowed answer for: " + ", ".join(wrong))
    sample.status, sample.answers = REVIEWED, dict(answers)
    sample.reviewer, sample.reviewed_at_utc = who.username, utc_now()
    record(s, case, who, "qa_reviewed", sample=sample.id, outcome=answers["outcome"])
    s.commit()
    return sample


def summary(s: Session, who: Identity) -> dict[str, object]:
    """Counts per rubric answer. Online results only, labelled as such; never merged with benchmark reports."""
    require_reviewer(who)
    rows = s.scalars(
        select(QaSample).join(Case, Case.id == QaSample.case_id).where(Case.customer_id == who.customer_id)
    ).all()
    reviewed = [r for r in rows if r.status == REVIEWED]
    counts = {item: {answer: 0 for answer in answers} for item, answers in RUBRIC.items()}
    for r in reviewed:
        for item, answer in (r.answers or {}).items():
            counts[item][answer] += 1
    return {
        "source": "online QA sampling (synthetic cases), not the offline benchmark",
        "sampled": len(rows),
        "reviewed": len(reviewed),
        "answers": counts,
    }
