"""Scoring one case against its label: pure functions over stored records (spec E.3, F7; docs/hypotheses.md section 1).

Nothing here calls a model, the app or a database, so a corrected metric can re-score old runs at no cost.
The definitions are the pre-registered ones. If this code and `docs/hypotheses.md` disagree, this code is wrong.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

Label = Mapping[str, Any]

# The proof chain, in order (F7). The member's journey and the KPI contribution are reported per arm, not per link.
LINKS = (
    "request_understood",
    "evidence_found",
    "policy_version",
    "eligibility",
    "action_proposed",
    "approval_decision",
    "execution",
    "final_ledger",
    "case_outcome",
)
UNSTRUCTURED_DEFECTS = frozenset(f"D{n}" for n in range(16, 24))  # D16 to D23


@dataclass(frozen=True)
class CaseResult:
    """What one arm did on one case, as the runner stored it. Holds no label."""

    case_id: str
    arm: str
    run: int
    kind: str  # deterministic | mock | live: never mixed
    first_action: str
    outcome: str  # adjusted | no_adjustment | denied | escalated | unresolved
    final_points: Mapping[str, int] = field(default_factory=dict)  # per stay, at the settlement horizon
    duplicate_credits: int = 0
    unauthorized_actions: int = 0
    contacts: int = 1  # the member's first message is one contact
    identified_stays: tuple[str, ...] = ()
    evidence_seen: tuple[str, ...] = ()
    policies: Mapping[str, Sequence[str]] = field(default_factory=dict)  # stay -> "policy-id@vN", all it relied on
    eligibility: str | None = None
    approved: bool | None = None  # None: no approval was asked for
    executed: bool = False
    tool_failures: int = 0
    retries: int = 0
    latency_s: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    interrupted: bool = False
    reopened: bool = False  # the member came back (simulated)
    ai_runs: int = 0
    ai_fallbacks: int = 0  # the run ended without a valid reading, so the case kept arm B's result
    ai_stops: tuple[str, ...] = ()
    simulated_days: int = 0  # simulated, never a measurement


def expected_points(label: Label) -> dict[str, int]:
    return {stay["stay_id"]: int(stay["expected_final_points"]) for stay in label["stays"]}


def _stay_differences(result: CaseResult, label: Label) -> list[int]:
    expected = expected_points(label)
    stays = set(expected) | set(result.final_points)
    return [result.final_points.get(stay, 0) - expected.get(stay, 0) for stay in stays]


def false_approval(result: CaseResult, label: Label) -> bool:
    """More points than the label, for any reason. Checked per stay, so two errors can't cancel out."""
    return any(difference > 0 for difference in _stay_differences(result, label))


def false_denial(result: CaseResult, label: Label) -> bool:
    """The final ledger holds fewer points than the label, including a wrong wait that never resolves."""
    return any(difference < 0 for difference in _stay_differences(result, label))


def ledger_correct(result: CaseResult, label: Label) -> bool:
    return all(difference == 0 for difference in _stay_differences(result, label))


def case_success(result: CaseResult, label: Label) -> bool:
    """The primary metric: the right ledger, the right outcome, and no stay credited twice."""
    return (
        ledger_correct(result, label) and result.outcome == label["expected_outcome"] and not result.duplicate_credits
    )


def correct_action(result: CaseResult, label: Label) -> bool:
    return bool(result.first_action == label["next_action"])


def needed_clarification(label: Label) -> bool:
    return bool(label["clarification_needed"]) or label["next_action"] == "request_info"


def asked_for_information(result: CaseResult) -> bool:
    return result.first_action == "request_info"


def clarification_found(result: CaseResult, label: Label) -> bool | None:
    """Recall's numerator. None when the case doesn't need clarification, so it stays out of the denominator."""
    return asked_for_information(result) if needed_clarification(label) else None


def unnecessary_request(result: CaseResult, label: Label) -> bool:
    return asked_for_information(result) and not needed_clarification(label)


def carries_unstructured_input(label: Label) -> bool:
    return bool(UNSTRUCTURED_DEFECTS.intersection(label["scenarios"]))


NOT_RECORDED = frozenset({"other_open_case_for_same_stay"})  # no arm keeps a record of having checked this


def _not_policies(evidence: Iterable[str]) -> set[str]:
    return {name for name in evidence if not name.startswith("policy:") and name not in NOT_RECORDED}


def _right_policy_version(records: Sequence[str], wanted: str) -> bool:
    """Fails only when a record shows another version of that policy. An arm's records don't always name every policy it
    applied, and a missing record isn't evidence of a wrong one. Same rule for every arm."""
    same_policy = [record for record in records if record.split("@", 1)[0] == wanted.split("@", 1)[0]]
    return not same_policy or wanted in same_policy


def _claimed(label: Label) -> set[str]:
    return {stay["stay_id"] for stay in label["stays"] if stay.get("stay_action") != "not_claimed"}


def _link_results(result: CaseResult, label: Label) -> dict[str, bool]:
    should_adjust = label["expected_outcome"] == "adjusted"
    should_be_approved = (
        should_adjust or label["next_action"] == "adjust"
    )  # D11: approved, then stopped by the re-check
    wanted_policies = {
        stay["stay_id"]: f"{stay['policy_id']}@v{stay['policy_version']}"
        for stay in label["stays"]
        if stay["policy_id"]
    }
    return {
        "request_understood": _claimed(label) <= set(result.identified_stays),
        "evidence_found": _not_policies(label["required_evidence"]) <= _not_policies(result.evidence_seen),
        "policy_version": all(
            _right_policy_version(result.policies.get(stay, ()), w) for stay, w in wanted_policies.items()
        ),
        "eligibility": result.eligibility == label["eligibility"],
        "action_proposed": correct_action(result, label),
        "approval_decision": bool(result.approved) if should_be_approved else not result.approved,
        "execution": result.executed if should_adjust else not result.executed,
        "final_ledger": ledger_correct(result, label),
        "case_outcome": result.outcome == label["expected_outcome"] and not result.duplicate_credits,
    }


def first_failed_link(result: CaseResult, label: Label) -> str | None:
    """Where in the chain this case first went wrong (the failure funnel), or None if every link held."""
    links = _link_results(result, label)
    return next((link for link in LINKS if not links[link]), None)
