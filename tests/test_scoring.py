"""Scoring and verdicts on hand-built cases, not on any run (BENCH-05, BENCH-07, BENCH-10; docs/hypotheses.md)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from evaluations import decide
from evaluations.decide import Difference, Runs, Verdict, h1, h2, h3, h4, h5, h6, h7, section_two_rule
from evaluations.scoring import (
    CaseResult,
    case_success,
    clarification_found,
    correct_action,
    false_approval,
    false_denial,
    first_failed_link,
    unnecessary_request,
)


def label(case_id: str = "X-1", **over: Any) -> dict[str, Any]:
    base = {
        "case_id": case_id,
        "clarification_needed": False,
        "eligibility": "eligible",
        "expected_outcome": "adjusted",
        "next_action": "adjust",
        "required_evidence": ["ledger", "stay_record"],
        "scenarios": ["K01"],
        "stays": [
            {"stay_id": "S1", "expected_final_points": 100, "policy_id": "p", "policy_version": 2},
        ],
    }
    return base | over


def good(case_id: str = "X-1", **over: Any) -> CaseResult:
    base: dict[str, Any] = {
        "case_id": case_id,
        "arm": "B",
        "run": 1,
        "kind": "deterministic",
        "first_action": "adjust",
        "outcome": "adjusted",
        "final_points": {"S1": 100},
        "identified_stays": ("S1",),
        "evidence_seen": ("ledger", "stay_record"),
        "policies": {"S1": "p@v2"},
        "eligibility": "eligible",
        "approved": True,
        "executed": True,
    }
    return CaseResult(**(base | over))


def test_a_correct_case_succeeds_and_passes_every_link() -> None:
    assert case_success(good(), label()) and correct_action(good(), label())
    assert first_failed_link(good(), label()) is None


@pytest.mark.parametrize(
    ("over", "wants"),
    [
        ({"final_points": {"S1": 90}}, "under"),
        ({"final_points": {"S1": 110}}, "over"),
        ({"final_points": {"S1": 100, "S9": 5}}, "over"),
        ({"final_points": {}}, "under"),
    ],
)
def test_false_approvals_and_false_denials_are_kept_apart(over: dict[str, Any], wants: str) -> None:
    result = good(**over)
    assert false_approval(result, label()) is (wants == "over")
    assert false_denial(result, label()) is (wants == "under")
    assert not case_success(result, label())


def test_two_errors_cant_cancel_out_in_a_total() -> None:
    two = label(
        stays=[
            {"stay_id": "S1", "expected_final_points": 100, "policy_id": "p", "policy_version": 2},
            {"stay_id": "S2", "expected_final_points": 100, "policy_id": "p", "policy_version": 2},
        ]
    )
    result = good(final_points={"S1": 150, "S2": 50})
    assert false_approval(result, two) and false_denial(result, two) and not case_success(result, two)


def test_the_right_ledger_with_the_wrong_outcome_or_a_duplicate_isnt_success() -> None:
    assert not case_success(good(outcome="escalated"), label())
    assert not case_success(good(duplicate_credits=1), label())


def test_clarification_recall_only_counts_cases_that_need_it() -> None:
    needs = label(clarification_needed=True, next_action="request_info")
    assert clarification_found(good(first_action="request_info"), needs) is True
    assert clarification_found(good(), needs) is False
    assert clarification_found(good(), label()) is None
    assert unnecessary_request(good(first_action="request_info"), label())
    assert not unnecessary_request(good(first_action="request_info"), needs)


@pytest.mark.parametrize(
    ("over", "link"),
    [
        ({"identified_stays": ()}, "request_understood"),
        ({"evidence_seen": ("ledger",)}, "evidence_found"),
        ({"policies": {"S1": "p@v1"}}, "policy_version"),
        ({"eligibility": "ineligible"}, "eligibility"),
        ({"first_action": "deny"}, "action_proposed"),
        ({"approved": False}, "approval_decision"),
        ({"executed": False}, "execution"),
        ({"final_points": {"S1": 1}}, "final_ledger"),
    ],
)
def test_the_funnel_names_the_first_failure(over: dict[str, Any], link: str) -> None:
    assert first_failed_link(good(**over), label()) == link


def test_crediting_a_case_that_shouldnt_be_credited_fails_at_approval() -> None:
    no = label(expected_outcome="no_adjustment", next_action="no_adjustment_credited")
    assert first_failed_link(good(first_action="no_adjustment_credited"), no) == "approval_decision"


# ---------- the decision rule ----------


def diff(points: float, low: float, high: float) -> Difference:
    return Difference(points, low, high, 0, 0, 80)


@pytest.mark.parametrize(
    ("observed", "threshold", "verdict"),
    [
        (diff(12, 2, 22), 10, Verdict.SUPPORTED),
        (diff(10, 0.5, 20), 10, Verdict.SUPPORTED),
        (diff(12, 0, 22), 10, Verdict.INCONCLUSIVE),  # the lower bound must be above 0
        (diff(12, -2, 22), 10, Verdict.INCONCLUSIVE),
        (diff(4, -2, 11), 10, Verdict.INCONCLUSIVE),
        (diff(4, 1, 9), 10, Verdict.NOT_SUPPORTED),  # the data rule out a worthwhile gain
        (diff(0, -5, 12), 10, Verdict.NOT_SUPPORTED),
        (diff(-3, -9, 15), 10, Verdict.NOT_SUPPORTED),
    ],
)
def test_the_section_two_rule(observed: Difference, threshold: float, verdict: Verdict) -> None:
    assert section_two_rule(observed, threshold) is verdict


def test_the_interval_is_repeatable_and_centres_on_the_difference() -> None:
    a, b = [0.0] * 40 + [1.0] * 40, [0.0] * 20 + [1.0] * 60
    first = decide.paired_interval(a, b, resamples=2000)
    assert first == decide.paired_interval(a, b, resamples=2000)
    assert first[0] < 25 < first[1]


def test_identical_arms_have_an_interval_of_zero() -> None:
    assert decide.paired_interval([1.0, 0.0], [1.0, 0.0], resamples=200) == (0.0, 0.0)


def test_a_comparison_needs_the_same_cases() -> None:
    with pytest.raises(ValueError, match="same cases"):
        decide.paired_interval([1.0], [1.0, 0.0])
    labels = {"A": label("A"), "B": label("B")}
    with pytest.raises(ValueError, match="paired"):
        h1(Runs([good("A")], labels), Runs([good("B")], labels), 10)


# ---------- verdicts: mock never decides ----------

CASES = [f"X-{n}" for n in range(30)]
LABELS = {case: label(case) for case in CASES}


def runs(kind: str, arm: str, right: int, repeats: int = 1, **wrong: Any) -> Runs:
    """`right` of the cases correct in every run."""
    rows = []
    for run in range(1, repeats + 1):
        for number, case in enumerate(CASES):
            over = {} if number < right else {"first_action": "deny", "outcome": "denied", "final_points": {}} | wrong
            rows.append(good(case, arm=arm, run=run, kind=kind, **over))
    return Runs(rows, LABELS)


@pytest.mark.parametrize("kind", ["mock", "deterministic"])
def test_mock_results_never_decide_h2_to_h5_however_good_they_look(kind: str) -> None:
    b, c = runs("deterministic", "B", 10), runs(kind, "C", 30, repeats=3)
    for decision in (h2(b, c, 5), h3(b, c, 15), h4(b, c, 10, 0.2), h5(c, 0.02, 15)):
        assert decision.verdict is Verdict.NOT_TESTED, decision.hypothesis
        assert "mock" in decision.why or kind in decision.why


def test_mock_and_live_cant_be_mixed_in_one_set_of_runs() -> None:
    with pytest.raises(ValueError, match="mixed"):
        Runs([good(kind="mock"), good(kind="live", run=2)], {"X-1": label()})


def test_an_interrupted_live_run_is_never_extrapolated() -> None:
    c = runs("live", "C", 30, repeats=3)
    broken = Runs([replace(c.results[0], interrupted=True), *c.results[1:]], LABELS)
    assert h2(runs("deterministic", "B", 10), broken, 5).verdict is Verdict.NOT_TESTED


def test_h1_supported_on_a_clear_gain_and_shows_its_counts() -> None:
    decision = h1(runs("deterministic", "A", 5), runs("deterministic", "B", 28), 10)
    assert decision.verdict is Verdict.SUPPORTED
    assert decision.difference is not None
    assert (decision.difference.numerator_a, decision.difference.numerator_b, decision.difference.denominator) == (
        5,
        28,
        30,
    )


def test_any_increase_in_false_approvals_makes_h2_not_supported_whatever_the_gain() -> None:
    b = runs("deterministic", "B", 10)
    over = {"final_points": {"S1": 500}, "outcome": "adjusted"}
    rows = [
        replace(good(case, arm="C", run=run, kind="live"), **(over if case == "X-0" and run < 3 else {}))
        for run in (1, 2, 3)
        for case in CASES
    ]
    decision = h2(b, Runs(rows, LABELS), 5)
    assert decision.verdict is Verdict.NOT_SUPPORTED and "false approvals" in decision.why


def test_h2_needs_case_success_too() -> None:
    b = runs("deterministic", "B", 20)
    rows = [
        replace(good(case, arm="C", run=run, kind="live"), outcome="escalated", final_points={"S1": 100})
        for run in (1, 2, 3)
        for case in CASES
    ]
    assert h2(b, Runs(rows, LABELS), 5).why == "C's case success is below B's"


def test_a_c_case_counts_when_it_holds_in_two_of_three_runs() -> None:
    labels = {"X-1": label()}
    two = Runs(
        [good(kind="live", run=1), good(kind="live", run=2), good(kind="live", run=3, first_action="deny")], labels
    )
    one = Runs(
        [
            good(kind="live", run=1),
            good(kind="live", run=2, first_action="deny"),
            good(kind="live", run=3, first_action="deny"),
        ],
        labels,
    )
    assert two.holds("X-1", correct_action) and not one.holds("X-1", correct_action)


def test_h3_looks_only_at_the_unstructured_slice() -> None:
    assert (
        h3(
            Runs([good("X-1")], {"X-1": label("X-1")}), Runs([good("X-1", kind="live")], {"X-1": label("X-1")}), 15
        ).verdict
        is Verdict.NOT_TESTED
    )


def test_h5_is_per_correctly_resolved_case_not_per_case() -> None:
    rows = [good(case, kind="live", arm="C", cost_usd=0.01, latency_s=2.0) for case in CASES[:15]]
    rows += [good(case, kind="live", arm="C", cost_usd=0.01, latency_s=2.0, outcome="denied") for case in CASES[15:]]
    decision = h5(Runs(rows, LABELS), 0.02, 15)
    assert decision.verdict is Verdict.SUPPORTED and "$0.02000" in decision.why
    assert h5(Runs(rows, LABELS), 0.019, 15).verdict is Verdict.NOT_SUPPORTED


def test_h5_fails_on_latency_alone() -> None:
    rows = [good(case, kind="live", arm="C", cost_usd=0.001, latency_s=20.0) for case in CASES]
    assert h5(Runs(rows, LABELS), 0.02, 15).verdict is Verdict.NOT_SUPPORTED


def test_h6_is_a_hard_gate_one_occurrence_fails_it() -> None:
    assert h6([good()]).verdict is Verdict.SUPPORTED
    assert h6([good(), good(duplicate_credits=1)]).verdict is Verdict.NOT_SUPPORTED
    assert h6([good(), good(unauthorized_actions=1)]).verdict is Verdict.NOT_SUPPORTED
    assert h6([]).verdict is Verdict.NOT_TESTED


def test_h7_never_runs_on_scripted_timing() -> None:
    assert h7(0, 6).verdict is Verdict.NOT_TESTED
    assert h7(3, 6).verdict is Verdict.INCONCLUSIVE
