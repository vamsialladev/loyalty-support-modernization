"""The runner's mechanics on a few dev cases, chosen by scenario. Scores come from `evaluations.compare`, not here."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.arms.legacy.rules import LegacyRules
from benchmarks.intake import read_split
from evaluations import member
from evaluations.journey import arm_a_first_action, combined_outcome
from evaluations.run import RunRefused, read_labels, refuse_unless_frozen, run_cases, write_run
from evaluations.run_config import load
from evaluations.scoring import CaseResult, case_success, correct_action, false_denial, first_failed_link
from evaluations.world import seed_template
from tests.conftest import ROOT


@pytest.fixture(scope="module")
def data(generated: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    dataset = generated / "benchmarks/datasets/v1"
    template = seed_template(generated / "seed_data/v1", tmp_path_factory.mktemp("template"))
    labels = read_labels("dev", dataset)
    return {"dataset": dataset, "template": template, "labels": labels, "items": read_split("dev", dataset)}


def scenario(data: dict[str, Any], code: str) -> str:
    return next(cid for cid, label in sorted(data["labels"].items()) if label["scenarios"] == [code])


def run_one(
    data: dict[str, Any], arm: str, code: str, folder: Path, *, second_look: bool = False
) -> tuple[CaseResult, dict[str, Any]]:
    case_id = scenario(data, code)
    items = [item for item in data["items"] if item.case_id == case_id]
    config = load({"A": "arm-a", "B": "arm-b"}[arm])
    results = run_cases(config, items, data["labels"], data["template"], folder, second_look=second_look)
    return results[0], data["labels"][case_id]


@pytest.mark.parametrize("arm", ["A", "B"])
def test_a_plain_missing_points_case_ends_with_the_right_ledger(data: dict[str, Any], arm: str, tmp_path: Path) -> None:
    result, label = run_one(data, arm, "K01", tmp_path)
    assert case_success(result, label), result
    assert correct_action(result, label)
    assert result.executed and result.approved
    assert first_failed_link(result, label) is None, result


@pytest.mark.parametrize("arm", ["A", "B"])
def test_an_already_credited_case_changes_nothing(data: dict[str, Any], arm: str, tmp_path: Path) -> None:
    result, label = run_one(data, arm, "K02", tmp_path)
    assert case_success(result, label), result
    assert not result.executed


def test_arm_b_answers_the_channel_question_and_counts_the_contact(data: dict[str, Any], tmp_path: Path) -> None:
    result, label = run_one(data, "B", "D03", tmp_path)
    assert result.first_action == "request_info"
    assert result.contacts == 2
    assert case_success(result, label), result


@pytest.mark.parametrize("arm", ["A", "B"])
def test_the_re_check_stops_a_planted_late_posting_and_the_script_ends_there(
    data: dict[str, Any], arm: str, tmp_path: Path
) -> None:
    """The main analysis: scripts as written. The ledger is right, and nobody has closed the case."""
    result, label = run_one(data, arm, "D11", tmp_path)
    assert result.first_action == "adjust" and not result.duplicate_credits and not result.executed
    assert result.final_points == {stay["stay_id"]: stay["expected_final_points"] for stay in label["stays"]}
    assert result.outcome == "unresolved" and not case_success(result, label)


@pytest.mark.parametrize("arm", ["A", "B"])
def test_the_sensitivity_variant_closes_it_for_both_arms(data: dict[str, Any], arm: str, tmp_path: Path) -> None:
    result, label = run_one(data, arm, "D11", tmp_path, second_look=True)
    assert not result.executed and case_success(result, label), result


@pytest.mark.parametrize("arm", ["A", "B"])
def test_the_second_look_only_ever_acts_on_a_stopped_credit(data: dict[str, Any], arm: str, tmp_path: Path) -> None:
    """Arm A's catalog prediction on D06 and D15 can't depend on this choice: no re-check stops those credits."""
    for code in ("D06", "D15", "K01", "K02"):
        plain, _ = run_one(data, arm, code, tmp_path / f"{code}-plain")
        looked, _ = run_one(data, arm, code, tmp_path / f"{code}-looked", second_look=True)
        assert (plain.outcome, plain.final_points, plain.first_action) == (
            looked.outcome,
            looked.final_points,
            looked.first_action,
        ), code


@pytest.mark.parametrize("arm", ["A", "B"])
def test_nothing_unauthorized_or_duplicated_on_a_duplicate_submission(
    data: dict[str, Any], arm: str, tmp_path: Path
) -> None:
    result, _label = run_one(data, arm, "D10", tmp_path)
    assert result.duplicate_credits == 0 and result.unauthorized_actions == 0


def test_arm_b_handles_the_other_stay_once_the_member_names_it(data: dict[str, Any], tmp_path: Path) -> None:
    result, label = run_one(data, "B", "D16", tmp_path)
    assert result.contacts == 2
    assert case_success(result, label), result


def test_arm_a_handles_only_one_stay_as_the_catalog_predicts(data: dict[str, Any], tmp_path: Path) -> None:
    result, label = run_one(data, "A", "D16", tmp_path)
    assert not case_success(result, label) and false_denial(result, label)


def test_a_member_told_to_wait_is_credited_when_they_come_back(data: dict[str, Any], tmp_path: Path) -> None:
    """DV-023 was claimed at 00:29 UTC, which is the evening before at the hotel."""
    items = [item for item in data["items"] if item.case_id == "DV-023"]
    result = run_cases(load("arm-b"), items, data["labels"], data["template"], tmp_path)[0]
    assert result.reopened and result.contacts == 2
    assert case_success(result, data["labels"]["DV-023"]), result


def test_a_new_world_starts_clean_each_run(data: dict[str, Any], tmp_path: Path) -> None:
    first, _ = run_one(data, "B", "K01", tmp_path / "one")
    second, _ = run_one(data, "B", "K01", tmp_path / "two")
    assert first.final_points == second.final_points and second.duplicate_credits == 0


def test_a_run_is_stored_with_its_versions_in_its_own_kind_of_folder(data: dict[str, Any], tmp_path: Path) -> None:
    result, _ = run_one(data, "B", "K01", tmp_path / "run")
    folder = write_run("name", load("arm-b"), "dev", [result], data["dataset"], tmp_path / "results")
    assert folder == tmp_path / "results" / "deterministic" / "name"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "deterministic" and manifest["app_commit"] and manifest["dataset_sha256"]
    assert "SYNTHETIC" in manifest["label"]
    assert json.loads((folder / "results.jsonl").read_text(encoding="utf-8"))["case_id"] == result.case_id


def test_held_out_needs_a_deliberate_flag_and_a_clean_tree() -> None:
    refuse_unless_frozen("dev", False, " M something")
    with pytest.raises(RunRefused, match="confirm-frozen"):
        refuse_unless_frozen("heldout", False, "")
    with pytest.raises(RunRefused, match="clean working tree"):
        refuse_unless_frozen("heldout", True, " M something")
    refuse_unless_frozen("heldout", True, "")


# ---------- pure parts ----------


LABEL: dict[str, Any] = {
    "member_reply": None,
    "facts": {
        "reply_channel": "phone",
        "claimed_stay_ids": ["BR-1"],
        "claimant": "GR-1",
        "unclaimed_stay_ids": ["BR-2"],
    },
}


@pytest.mark.parametrize(
    ("question", "field", "value"),
    [
        ("booking_channel", "booking_channel", "phone"),
        ("confirmation", "confirmation", "BR-1"),
        ("asked_for_confirmation", "confirmation", "BR-1"),
        ("second_identifier", "member_number", "GR-1"),
        ("asked_for_member_number", "member_number", "GR-1"),
    ],
)
def test_the_member_answers_what_the_scenario_holds(question: str, field: str, value: str) -> None:
    answer = member.answer(question, LABEL, "original")
    assert getattr(answer, field) == value and not answer.repeated


def test_the_member_repeats_themselves_otherwise() -> None:
    answer = member.answer("asked_for_english", LABEL, "original")
    assert answer.repeated and answer.text == "original"


def test_the_member_says_what_the_scenario_says_about_a_vague_stay() -> None:
    label = {**LABEL, "member_reply": "It was the stay that checked out on 2025-10-23."}
    assert member.answer("which_stay", label, "x").text.endswith("2025-10-23.")


def test_the_member_names_only_stays_they_claimed_and_not_yet_handled() -> None:
    label = {"facts": {"claimed_stay_ids": ["BR-1", "ML-2"], "unclaimed_stay_ids": ["BR-9"]}}
    assert member.other_stays(label, {"BR-1"}) == ["ML-2"]
    assert member.other_stays(label, {"BR-1", "ML-2"}) == []


def test_a_member_comes_back_on_the_date_they_were_given() -> None:
    assert member.return_moment("2026-02-21") == "2026-02-21T15:00:00Z"


def test_the_proxy_is_the_synthetic_historys_formula() -> None:
    assert member.satisfaction_proxy(1, False, False, 5) == 5.0
    assert member.satisfaction_proxy(2, False, False, 5) == 4.3
    assert member.satisfaction_proxy(1, True, True, 5) == 2.5
    assert member.satisfaction_proxy(1, False, False, 15) == 3.5
    assert member.satisfaction_proxy(9, True, True, 99) == 1.0


def test_days_add_up_from_the_historys_delays() -> None:
    assert member.simulated_days(0) == 1
    assert member.simulated_days(2, waited_days=7, sat_in_the_wrong_queue=True) == 18


@pytest.mark.parametrize(
    ("path", "action"),
    [
        (["asked_for_confirmation"], "request_info"),
        (["member_not_found"], "deny"),
        (["checklist:adjust", "supervisor:approved"], "adjust"),
        (["checklist:wait_until"], "wait_until"),
        (["in_billing_queue"], "none"),
    ],
)
def test_arm_as_first_action_uses_the_labels_words(path: list[str], action: str) -> None:
    assert arm_a_first_action(path) == action


def test_a_credit_on_any_case_means_it_was_adjusted() -> None:
    assert combined_outcome(["no_adjustment", "adjusted"]) == "adjusted"
    assert combined_outcome(["unresolved", "denied"]) == "denied"
    assert combined_outcome([]) == "unresolved"


def test_arm_as_rule_revisions_match_the_policy_versions_one_to_one() -> None:
    """`Journey._policies_a` reads arm A's version from the position of its rules revision."""
    rules = LegacyRules.load("hg-demo")
    effective = sorted(
        {
            str(yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])["effective_from"])
            for path in (ROOT / "policies/hg-demo").rglob("*.md")
            if "missing-points" in path.name
        }
    )
    assert [r.effective_from.isoformat() for r in rules.revisions] == effective
