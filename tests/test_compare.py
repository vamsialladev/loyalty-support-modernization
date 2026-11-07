"""The comparison report on hand-built runs: what it must show, and no verdict outside held-out (BENCH-05, -06)."""

from __future__ import annotations

from typing import Any

from evaluations import sensitivity
from evaluations.compare import Run, by_scenario, funnel, repeat_differences, report, summary_rows
from evaluations.scoring import CaseResult

LABELS: dict[str, Any] = {
    case: {
        "case_id": case,
        "clarification_needed": False,
        "eligibility": "eligible",
        "expected_outcome": "adjusted",
        "next_action": "adjust",
        "required_evidence": [],
        "scenarios": [scenario],
        "stays": [{"stay_id": "S" + case, "expected_final_points": 100, "policy_id": "p", "policy_version": 1}],
    }
    for case, scenario in (("1", "K01"), ("2", "D06"))
}


def result(case: str, arm: str = "A", **over: Any) -> CaseResult:
    base: dict[str, Any] = {
        "case_id": case,
        "arm": arm,
        "run": 1,
        "kind": "deterministic",
        "first_action": "adjust",
        "outcome": "adjusted",
        "final_points": {"S" + case: 100},
        "identified_stays": ("S" + case,),
        "eligibility": "eligible",
        "approved": True,
        "executed": True,
        "latency_s": 1.0,
    }
    return CaseResult(**(base | over))


def run(*results: CaseResult, kind: str = "deterministic", after: str = "script as written") -> Run:
    return Run("r", {"kind": kind, "split": "dev", "after_stop": after}, results)


def test_false_approvals_and_denials_stay_apart_with_their_denominators() -> None:
    rows = summary_rows(run(result("1", final_points={"S1": 200}), result("2", final_points={})), LABELS)
    assert rows["False approvals (over-credit)"] == "1/2 (50.0%)"
    assert rows["False denials (under-credit)"] == "1/2 (50.0%)"
    assert rows["Case success (final ledger, outcome, no duplicate)"] == "0/2 (0.0%)"


def test_a_right_ledger_on_an_open_case_shows_in_its_own_row() -> None:
    rows = summary_rows(run(result("1", outcome="unresolved")), LABELS)
    assert rows["Final ledger correct"] == "1/1 (100.0%)"
    assert rows["Left unresolved"] == "1/1 (100.0%)"
    assert rows["Case success (final ledger, outcome, no duplicate)"] == "0/1 (0.0%)"


def test_a_dangerous_error_cant_hide_in_a_total() -> None:
    table = by_scenario(run(result("1"), result("2", final_points={"S2": 200})), LABELS)
    assert table["K01"] == (1, 1, 1, 0, 0)
    assert table["D06"] == (1, 0, 0, 1, 0)


def test_the_funnel_counts_first_failures() -> None:
    counts = funnel(run(result("1"), result("2", first_action="deny")), LABELS)
    assert counts["every link held"] == 1 and counts["action_proposed"] == 1


def test_no_verdict_outside_held_out_and_the_labels_are_there() -> None:
    text = report([run(result("1"))], {"1": LABELS["1"]}, "dev")
    assert "**No verdict.**" in text and "SYNTHETIC" in text and "not human" in text
    assert "aren't independently reviewed" in text


def test_a_columns_kind_and_variant_are_on_it() -> None:
    assert run(result("1")).title == "A [deterministic]"
    assert run(result("1", kind="mock"), kind="mock").title == "A [mock]"
    assert run(result("1"), after="second look (sensitivity variant)").title == "A (second look) [deterministic]"


def test_a_repeat_must_match_on_everything_but_the_clock() -> None:
    assert repeat_differences(run(result("1", latency_s=1.0)), run(result("1", latency_s=9.0))) == []
    assert repeat_differences(run(result("1")), run(result("1", outcome="denied"))) == ["1: outcome"]


def test_paired_differences_need_the_same_cases() -> None:
    text = report(
        [run(result("1"), result("2")), run(result("1", arm="B"))],
        LABELS,
        "dev",
    )
    assert "not the same cases" in text


def test_the_sensitivity_report_shows_all_three_variants_and_what_changed() -> None:
    open_case = {"outcome": "unresolved"}
    a, b = run(result("1", **open_case)), run(result("1", arm="B", **open_case))
    a_look = run(result("1"), after="second look (sensitivity variant)")
    b_look = run(result("1", arm="B"), after="second look (sensitivity variant)")
    labels = {"1": LABELS["1"]}
    text = sensitivity.report(a, b, a_look, b_look, labels, "dev")
    assert "**(main analysis)**" in text and "**(biased, for comparison only)**" in text
    assert "Arm A: 1." in text and "Arm B: 1." in text
    assert sensitivity.changed_cases(a, a) == []


def test_over_credits_are_counted_within_a_scenario() -> None:
    assert sensitivity.over_credits_in(run(result("2", final_points={"S2": 200})), LABELS, "D06") == "1/1"
