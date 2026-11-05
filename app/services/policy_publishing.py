"""Controlled policy publishing (spec B.6; POL-05): draft, checks, published, and the version it replaces superseded.

The checks run on the set of versions as it would be after publishing, so a version that would break an earlier date is
refused while it's still a draft. A failed check changes nothing except the audit log.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.customer_records import LedgerEntry, PendingPosting, StayRecord
from app.domain.eligibility import CustomerRules, NextAction, StayClaim, evaluate_stay
from app.domain.policy import (
    DRAFT,
    EARNING,
    MISSING_POINTS,
    PUBLISHED,
    SUPERSEDED,
    PolicyFormatError,
    PolicyVersion,
    parse_document,
)
from app.domain.roles import Identity, require_administrator
from app.persistence.models import PolicyVersionRow
from app.services import approvals, policies
from app.services.customer_config import CustomerConfig
from app.services.instrumentation import record_system

REGRESSION_DIR = Path(__file__).resolve().parents[2] / "config" / "policy-regression"
MAX_DRAFT_CHARS = 200_000


def _whole(minimum: int) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _flag(value: Any) -> bool:
    return isinstance(value, bool)


_RULE_CHECKS: dict[str, dict[str, Callable[[Any], bool]]] = {
    MISSING_POINTS: {
        "waiting_period_days": _whole(0),
        "claim_window_months": _whole(1),
        "eligible_channels": lambda v: isinstance(v, list) and all(isinstance(c, str) for c in v),
        "ota_eligible_with_member_on_booking": _flag,
        "corporate_rate_prefix": lambda v: v is None or (isinstance(v, str) and bool(v)),
        "pending_posting_blocks_adjustment": _flag,
        "supervisor_approval_required": lambda v: v is True,
        "supervisor_limit_points": _whole(1),
    },
    EARNING: {"points_per_usd_room_revenue": _whole(1)},
}


class PublishRefused(Exception):
    """The draft can't be published. `problems` says why, one line each; the form shows them."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


@dataclass(frozen=True)
class GoldenCase:
    """A dated outcome that must stay true (`config/policy-regression/<customer>.yaml`). Changing what an earlier date
    means therefore takes a reviewed change to that file, not only a publish."""

    name: str
    claim: StayClaim
    action: str
    points_owed: int | None


def load_golden_cases(customer_id: str, directory: Path = REGRESSION_DIR) -> list[GoldenCase]:
    data = yaml.safe_load((directory / f"{customer_id}.yaml").read_text(encoding="utf-8"))
    defaults = dict(data["stay_defaults"])
    posted = defaults.pop("posted_at_utc_default")
    cases = []
    for item in data["cases"]:
        record = StayRecord(**{**defaults, **item["stay"]})
        member = str(record.member_number)
        received = item["received_at_utc"]
        ledger = tuple(
            LedgerEntry(f"G-{i}", member, "posting", int(points), posted, record.stay_id)
            for i, points in enumerate(item.get("credited", []))
        )
        postings = tuple(
            PendingPosting(f"Q-{i}", member, record.stay_id, 1, posted, until, f"E-{i}")
            for i, until in enumerate(item.get("pending_until", []))
        )
        claim = StayClaim(record.stay_id, record.member_number, (record,), ledger, postings, received, received)
        cases.append(GoldenCase(item["name"], claim, item["action"], item.get("points_owed")))
    return cases


def after_publishing(existing: Sequence[PolicyVersion], candidate: PolicyVersion) -> tuple[PolicyVersion, ...]:
    """The versions as they would stand: the candidate published, the version before it closed the day before."""
    out = []
    same = [v for v in existing if v.policy_id == candidate.policy_id]
    previous = max(same, key=lambda v: v.version, default=None)
    for version in existing:
        if version is previous and previous.effective_from < candidate.effective_from:
            closes = candidate.effective_from - timedelta(days=1)
            out.append(replace(version, effective_to=closes, status=SUPERSEDED))
        else:
            out.append(version)
    return (*out, replace(candidate, status=PUBLISHED))


def _rule_problems(candidate: PolicyVersion) -> list[str]:
    checks = _RULE_CHECKS.get(candidate.policy_id)
    if checks is None:
        return [f"{candidate.policy_id} is not a known policy, so its rules can't be checked"]
    problems = []
    for name, check in checks.items():
        if name not in candidate.rules:
            problems.append(f"rule {name} is missing")
        elif not check(candidate.rules[name]):
            problems.append(f"rule {name} has an invalid value")
    return problems


def _date_problems(candidate: PolicyVersion, stands: Sequence[PolicyVersion]) -> list[str]:
    problems = []
    if candidate.effective_to is not None and candidate.effective_to < candidate.effective_from:
        problems.append("effective_to is before effective_from")
    chain = sorted((v for v in stands if v.policy_id == candidate.policy_id), key=lambda v: v.version)
    for earlier, later in pairwise(chain):
        if later.effective_from <= earlier.effective_from:
            problems.append(f"v{later.version} starts on or before v{earlier.version}")
        elif earlier.effective_to is None or earlier.effective_to + timedelta(days=1) != later.effective_from:
            problems.append(f"v{earlier.version} and v{later.version} leave a gap or overlap in their dates")
    return problems


def publish_problems(
    candidate: PolicyVersion,
    existing: Sequence[PolicyVersion],
    golden: Sequence[GoldenCase],
    customer: CustomerRules,
) -> list[str]:
    """Everything wrong with publishing `candidate`. Pure, so each check is tested without a database."""
    problems = _rule_problems(candidate)
    latest = max((v.version for v in existing if v.policy_id == candidate.policy_id), default=0)
    if candidate.version != latest + 1:
        problems.append(f"the next version of {candidate.policy_id} is {latest + 1}, not {candidate.version}")
    stands = after_publishing(existing, candidate)
    problems += _date_problems(candidate, stands)
    if problems:
        return problems  # the rules aren't readable, so the golden cases can't run
    for case in golden:
        got = evaluate_stay(case.claim, stands, customer)
        if got.action != NextAction(case.action):
            problems.append(f"golden case '{case.name}': expected {case.action}, got {got.action.value}")
        elif case.points_owed is not None and got.points_owed != case.points_owed:
            problems.append(f"golden case '{case.name}': expected {case.points_owed} points, got {got.points_owed}")
    return problems


def create_draft(s: Session, who: Identity, text: str, customer_id: str) -> PolicyVersionRow:
    """Store a new draft from a policy document's text. It can't apply to any stay until it is published."""
    require_administrator(who)
    if len(text) > MAX_DRAFT_CHARS:
        raise PublishRefused([f"the document is longer than {MAX_DRAFT_CHARS} characters"])
    normal = text.replace("\r\n", "\n")
    try:
        doc = parse_document(normal)
    except (PolicyFormatError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise PublishRefused([f"the document can't be read: {exc}"]) from exc
    if doc.version.customer != customer_id:
        raise PublishRefused([f"the document is for {doc.version.customer}, not {customer_id}"])
    found = s.scalars(
        select(PolicyVersionRow).where(
            PolicyVersionRow.customer_id == customer_id,
            PolicyVersionRow.policy_id == doc.version.policy_id,
            PolicyVersionRow.version == doc.version.version,
        )
    ).first()
    if found is not None:
        raise PublishRefused([f"{found.policy_id} v{found.version} already exists: a stored version never changes"])
    row = policies.store_document(s, customer_id, doc, normal, status=DRAFT, created_by=who.username)
    record_system(s, who, "policy_draft_created", policy=row.policy_id, version=row.version, checksum=row.checksum)
    s.commit()
    return row


def publish(s: Session, who: Identity, row_id: int, config: CustomerConfig) -> PolicyVersionRow:
    """Run the checks and publish in one transaction. A refusal is logged and raises `PublishRefused`."""
    require_administrator(who)
    row = s.get(PolicyVersionRow, row_id, with_for_update=True)
    if row is None or row.customer_id != config.customer_id:
        raise PublishRefused(["there is no such policy version"])
    if row.status != DRAFT:
        raise PublishRefused([f"{row.policy_id} v{row.version} is already {row.status}"])
    candidate = policies.to_domain(row)
    existing = policies.published_versions(s, config.customer_id)
    golden = load_golden_cases(config.customer_id)
    problems = publish_problems(candidate, existing, golden, config.rules)
    if problems:
        record_system(s, who, "policy_publish_refused", policy=row.policy_id, version=row.version, problems=problems)
        s.commit()
        raise PublishRefused(problems)
    now = utc_now()
    same = [r for r in policies.version_rows(s, config.customer_id) if r.policy_id == row.policy_id and r.id != row.id]
    previous = max((r for r in same if r.status != DRAFT), key=lambda r: r.version, default=None)
    closed = None
    if previous is not None:
        closes = candidate.effective_from - timedelta(days=1)
        previous.effective_to, previous.status = closes.isoformat(), SUPERSEDED
        closed = previous.version
    row.status, row.published_by, row.published_at_utc = PUBLISHED, who.username, now
    row.regression = {"golden_cases": len(golden), "problems": [], "checked_at_utc": now}
    s.flush()
    ended = approvals.invalidate_for_policy_change(s, who, config.customer_id)
    record_system(
        s,
        who,
        "policy_published",
        policy=row.policy_id,
        version=row.version,
        checksum=row.checksum,
        effective_from=row.effective_from,
        supersedes=closed,
        golden_cases=len(golden),
        invalidated_requests=ended,
    )
    s.commit()
    return row
