"""The engine against the independent reference labeler, on the DEV split only (spec E.1, ELIG-01).

Two separately written implementations of the same written policy. A disagreement means one of them is wrong; it is read
against the policy text, never settled by copying the other. The validation, held-out and stress splits are not opened
here: tuning the engine on them would spoil the benchmark (spec E.1).

Test code may read labels (it is the evaluator); the app never does.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pytest

from app.domain.customer_records import LedgerEntry, PendingPosting, StayRecord
from app.domain.eligibility import NextAction, StayClaim, combine, evaluate_stay
from app.domain.policy import PolicyVersion, parse_document
from app.services.customer_config import CustomerConfig
from tests.conftest import ROOT, read_jsonl

POLICIES = tuple(
    parse_document(p.read_text(encoding="utf-8")).version for p in (ROOT / "policies/hg-demo").glob("*.md")
)
CUSTOMER = CustomerConfig.load("hg-demo").rules


def build(record_type: type, row: dict[str, Any]) -> Any:
    names = {f.name for f in fields(record_type)}
    return record_type(**{k: v for k, v in row.items() if k in names})


def stay_claim(facts: dict[str, Any], stay_id: str, *, as_of: str | None = None, with_reply: bool = True) -> StayClaim:
    received = facts["received_at_utc"]
    return StayClaim(
        stay_id=stay_id,
        claimant=facts["claimant"],
        records=tuple(build(StayRecord, r) for r in facts["records"] if r["stay_id"] == stay_id),
        ledger=tuple(build(LedgerEntry, e) for e in facts["ledger"] if e["stay_id"] == stay_id),
        postings=tuple(build(PendingPosting, q) for q in facts["queue"] if q["stay_id"] == stay_id),
        received_at_utc=received,
        as_of_utc=as_of or received,
        duplicate_profiles=tuple(facts["duplicate_profiles"]),
        merged_profiles=tuple(facts["merged_profiles"]),
        member_stated_channel=facts["reply_channel"] if with_reply else None,
    )


@pytest.fixture(scope="module")
def dev_labels(generated: Path) -> list[dict[str, Any]]:
    return read_jsonl(generated / "benchmarks/datasets/v1/labels/dev.jsonl")


def stay_disagreements(
    labels: list[dict[str, Any]], policies: tuple[PolicyVersion, ...]
) -> tuple[Counter[str], list[tuple[Any, ...]]]:
    """How many claimed stays were compared per expected action, and where the two implementations differ."""
    compared: Counter[str] = Counter()
    disagreements: list[tuple[Any, ...]] = []
    for label in labels:
        facts = label["facts"]
        late = bool(facts["harness_late_postings"])
        for expected in label["stays"]:
            if expected["stay_action"] == "not_claimed":
                continue
            compared[expected["stay_action"]] += 1
            got = evaluate_stay(stay_claim(facts, expected["stay_id"]), policies, CUSTOMER)
            ref = got.policy_refs[0] if got.policy_refs else None
            mine = {
                "eligibility": got.status.value,
                "action": got.action.value,
                "existing_credit": got.existing_credit.value,
                "policy": (ref.policy_id, ref.version) if ref else (None, None),
            }
            theirs = {
                "eligibility": expected["eligibility"],
                "action": expected["stay_action"],
                "existing_credit": expected["existing_credit"],
                "policy": (expected["policy_id"], expected["policy_version"]),
            }
            # The label's `earned` is 0 for ineligible stays, and its `owed` is a final-ledger figure for wait_until
            # and late postings, so those two are compared only where they mean the same thing.
            if expected["eligibility"] not in ("ineligible", "needs_escalation"):
                mine["earned"], theirs["earned"] = got.earned_points, expected["earned_points"]
            if expected["stay_action"] == "adjust" and not late:
                mine["owed"], theirs["owed"] = got.points_owed, expected["owed_by_adjustment"]
            if mine != theirs:
                disagreements.append((label["case_id"], label["scenarios"], expected["stay_id"], mine, theirs))
    return compared, disagreements


def test_engine_and_labeler_agree_on_every_claimed_stay_in_the_dev_split(dev_labels: list[dict[str, Any]]) -> None:
    compared, disagreements = stay_disagreements(dev_labels, POLICIES)
    assert disagreements == []
    assert sum(compared.values()) >= 100
    # A comparison that never reached a rule would agree for the wrong reason.
    assert {
        "adjust",
        "no_adjustment_credited",
        "no_adjustment_pending",
        "wait_until",
        "not_checked_out",
        "deny",
        "escalate",
    } <= set(compared)


@pytest.mark.parametrize(
    ("policy_id", "version", "rule", "wrong"),
    [
        ("missing-points-requests", 2, "waiting_period_days", 30),
        ("missing-points-requests", 2, "ota_eligible_with_member_on_booking", False),
        ("missing-points-requests", 2, "corporate_rate_prefix", None),
        ("missing-points-requests", 2, "pending_posting_blocks_adjustment", False),
        ("guest-rewards-earning", 2, "points_per_usd_room_revenue", 11),
    ],
)
def test_the_comparison_catches_a_wrong_rule(
    dev_labels: list[dict[str, Any]], policy_id: str, version: int, rule: str, wrong: object
) -> None:
    """Change one rule and the two must disagree, or the agreement above would prove nothing."""
    changed = tuple(
        replace(p, rules={**p.rules, rule: wrong}) if (p.policy_id, p.version) == (policy_id, version) else p
        for p in POLICIES
    )
    assert stay_disagreements(dev_labels, changed)[1]


def test_engine_and_labeler_agree_on_every_case_verdict_in_the_dev_split(dev_labels: list[dict[str, Any]]) -> None:
    disagreements = []
    compared = 0
    for label in dev_labels:
        facts = label["facts"]
        if len(facts["candidate_stays"]) > 1:
            continue  # "which stay did you mean?" is the arm's question, asked before eligibility runs
        results = [
            evaluate_stay(stay_claim(facts, stay_id, with_reply=False), POLICIES, CUSTOMER)
            for stay_id in facts["claimed_stay_ids"]
        ]
        verdict = combine(results)
        compared += 1
        mine = (verdict.status.value, verdict.action.value, verdict.detail)
        theirs = (label["eligibility"], label["next_action"], label["next_action_detail"])
        if mine != theirs:
            disagreements.append((label["case_id"], label["scenarios"], mine, theirs))
    assert compared >= 90
    assert disagreements == []


def test_a_recheck_after_a_late_posting_stops_the_adjustment(dev_labels: list[dict[str, Any]]) -> None:
    """The harness event the labeler plants: investigation says adjust, the posting lands after approval, and the
    re-check before execution must stop it (spec B.10)."""
    cases = [lab for lab in dev_labels if lab["facts"]["harness_late_postings"]]
    assert cases
    for label in cases:
        facts = label["facts"]
        stay_id = facts["claimed_stay_ids"][0]
        at_claim = evaluate_stay(stay_claim(facts, stay_id), POLICIES, CUSTOMER)
        assert at_claim.action is NextAction.ADJUST and at_claim.points_owed > 0, label["case_id"]
        last = max(e["posted_at_utc"] for e in facts["ledger"] if e["stay_id"] == stay_id)
        later = evaluate_stay(stay_claim(facts, stay_id, as_of=last), POLICIES, CUSTOMER)
        assert later.action is NextAction.NO_ADJUSTMENT_CREDITED, label["case_id"]
