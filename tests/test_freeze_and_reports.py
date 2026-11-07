"""The freeze holds, and the final reports list what they must, on hand-built runs (BENCH-13, LGF-14, ENT-04)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evaluations import final_report as fr
from evaluations.decide import Runs, Verdict
from evaluations.freeze import changes_since_freeze, frozen_hashes, variability_cases, write_freeze
from evaluations.run import DATASET, RunRefused, refuse_unless_frozen
from evaluations.scoring import CaseResult


def label(case: str, scenario: str = "K01", **slices: str) -> dict[str, Any]:
    return {
        "case_id": case,
        "clarification_needed": False,
        "eligibility": "eligible",
        "expected_outcome": "adjusted",
        "next_action": "adjust",
        "required_evidence": [],
        "scenarios": [scenario],
        "slices": {"tier": "Gold", "language": "en"} | slices,
        "stays": [{"stay_id": f"S{case}", "expected_final_points": 100, "policy_id": "p", "policy_version": 1}],
    }


LABELS = {"1": label("1", "K01"), "2": label("2", "D06", tier="Silver"), "3": label("3", "D16")}


def result(
    case: str, arm: str, *, right: bool = True, run: int = 1, kind: str = "deterministic", **over: Any
) -> CaseResult:
    wrong = {"first_action": "deny", "outcome": "denied", "final_points": {}}
    base = {
        "case_id": case,
        "arm": arm,
        "run": run,
        "kind": kind,
        "first_action": "adjust",
        "outcome": "adjusted",
        "final_points": {f"S{case}": 100},
        "identified_stays": (f"S{case}",),
        "eligibility": "eligible",
        "approved": True,
        "executed": True,
        "latency_s": 1.0,
        "cost_usd": 0.002,
    }
    return CaseResult(**(base | ({} if right else wrong) | over))


def runs(arm: str, wrong: tuple[str, ...] = (), kind: str = "deterministic", repeats: int = 1) -> Runs:
    rows = [
        result(case, arm, right=case not in wrong, run=run, kind=kind)
        for run in range(1, repeats + 1)
        for case in sorted(LABELS)
    ]
    return Runs(rows, LABELS)


def test_every_slice_where_a_or_b_beats_c_is_listed_including_c_losing_to_a() -> None:
    rows = fr.beats_c_rows(runs("A"), runs("B", ("3",)), runs("C", ("2",), "live", 3), LABELS)
    text = str(rows)
    assert "scenario D06" in text and "tier = Silver" in text
    assert any(row[2] == "A" and row[1] == "Case success" for row in rows)
    assert any(row[2] == "B" and row[1] == "Case success" for row in rows)


def test_no_rows_when_c_is_never_beaten() -> None:
    assert fr.beats_c_rows(runs("A", ("1",)), runs("B", ("1",)), runs("C", (), "live", 3), LABELS) == []


def test_a_false_approval_count_lower_than_cs_counts_as_beating_it() -> None:
    over = Runs([result("1", "C", final_points={"S1": 900}, run=n, kind="live") for n in (1, 2, 3)], {"1": LABELS["1"]})
    plain = Runs([result("1", "B")], {"1": LABELS["1"]})
    rows = fr.beats_c_rows(plain, plain, over, {"1": LABELS["1"]})
    assert any(row[1] == "False approvals" for row in rows)


def test_mock_arm_c_leaves_h2_to_h5_not_tested_in_the_decisions() -> None:
    decisions = fr.decisions(runs("A"), runs("B"), runs("C", (), "mock", 3), list(runs("A").results))
    verdicts = {d.hypothesis: d.verdict for d in decisions}
    for hypothesis in ("H2", "H3", "H4", "H5"):
        assert verdicts[hypothesis] is Verdict.NOT_TESTED
    assert verdicts["H7"] is Verdict.NOT_TESTED and verdicts["H6"] is Verdict.SUPPORTED


def test_the_re_weighting_table_is_the_one_the_generator_wrote() -> None:
    table = fr.weights()
    assert table["K"] == pytest.approx(1.944) and table["D06"] == pytest.approx(0.530)
    assert len(table) == 25


def test_re_weighting_counts_a_control_more_than_a_rare_defect() -> None:
    table = {"D06": 0.5, "K": 2.0}
    labels = {"1": label("1", "K01"), "2": label("2", "D06")}
    assert fr.weighted_rate({"1": True, "2": False}, labels, table) == pytest.approx(80.0)


def test_the_catalog_table_parses_and_covers_every_defect_it_lists() -> None:
    rows = fr.catalog_rows()
    assert len(rows) == 25 and {r[0] for r in rows} >= {"D01", "D06", "D11", "D25"}


@pytest.mark.parametrize(
    ("prediction", "successes", "total", "expected"),
    [
        ("Wrong (over-credits)", 1, 3, "yes"),
        ("Wrong (over-credits)", 3, 3, "**no: it got them all right**"),
        ("Fixes", 3, 3, "yes"),
        ("Fixes", 2, 3, "**no: 1 missed**"),
        ("Escalates (correct)", 2, 2, "yes"),
        ("Partial", 1, 3, "read the note"),
        ("Fixes", 0, 0, "not in held-out"),
    ],
)
def test_predicted_against_actual_wording(prediction: str, successes: int, total: int, expected: str) -> None:
    assert fr.as_predicted(prediction, successes, total) == expected


def test_arm_as_failures_are_attributed_to_who_fixed_them() -> None:
    fixed = fr.attribution(runs("A", ("2", "3")), runs("B", ("3",)), runs("C", (), "live", 3), LABELS)
    assert fixed["Fixed by B"][0] == 1 and fixed["Fixed only by C"][0] == 1 and fixed["Fixed by neither"][0] == 0


def test_the_freeze_covers_what_can_change_an_arm_and_not_the_scoring() -> None:
    hashes = frozen_hashes()
    for name in (
        "app/services/assisted.py",
        "config/prompts/arm_c_v1.md",
        "config/ai/hg-demo.yaml",
        "evaluations/journey.py",
    ):
        assert name in hashes
    assert "evaluations/scoring.py" not in hashes and "evaluations/final_report.py" not in hashes


def test_a_held_out_run_is_refused_without_a_freeze_or_after_a_change(tmp_path: Path) -> None:
    assert changes_since_freeze(tmp_path / "missing.yaml") == ["no freeze has been committed"]
    frozen = tmp_path / "freeze.yaml"
    write_freeze(DATASET, frozen)
    assert changes_since_freeze(frozen) == []
    frozen.write_text(
        frozen.read_text(encoding="utf-8").replace("app/services/assisted.py: ", "app/services/assisted.py: x"),
        encoding="utf-8",
    )
    assert changes_since_freeze(frozen) == ["app/services/assisted.py"]


def test_held_out_without_the_flag_is_still_refused_first() -> None:
    with pytest.raises(RunRefused, match="confirm-frozen"):
        refuse_unless_frozen("heldout", False, "")


def test_the_variability_cases_come_from_ids_alone_and_are_stable() -> None:
    chosen = variability_cases(DATASET)
    assert len(chosen) == 10 and chosen == variability_cases(DATASET) and chosen == sorted(chosen)
