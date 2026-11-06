"""The routing baseline reproduces, and its decision rule came first (ML-01 to ML-03; Appendix I4)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from evaluations.routing_baseline import label_class, rules_predict, run
from tests.conftest import ROOT

REPORT = ROOT / "evaluations/routing/report-v1.json"


def test_the_stored_report_reproduces_from_the_seed(generated: Path) -> None:
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    fresh = run(generated)
    for key in ("train_support", "rules", "classifier", "decision", "drift_check_on_stress"):
        assert fresh[key] == stored[key], key


def test_rules_stay_under_the_preset_rule() -> None:
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    assert stored["decision"]["chosen"] == "rules"
    assert stored["not_run"]["llm_zero_and_few_shot"].startswith("NOT RUN")
    assert stored["classes_not_in_the_dataset"] == ["out_of_scope", "complaint_only"]


def test_the_rule_was_committed_before_the_report() -> None:
    def first_commit(path: str) -> int:
        done = subprocess.run(
            ["git", "log", "--follow", "--format=%ct", "--", path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        lines = done.stdout.split()
        if done.returncode != 0 or not lines:
            pytest.skip("no Git history here")
        return int(lines[-1])

    assert first_commit("config/routing/thresholds.yaml") <= first_commit("evaluations/routing/report-v1.json")


def test_labels_come_from_scenario_facts() -> None:
    assert label_class({"scenarios": ["S01"]}) == "suspected_injection"
    assert label_class({"scenarios": ["D23"]}) == "non_english"
    assert label_class({"scenarios": ["D20"]}) == "multi_issue"
    assert label_class({"scenarios": ["K01"]}) == "missing_points"


def test_the_rules_baseline_is_arm_bs_rules() -> None:
    assert rules_predict("Bonjour, merci pour votre aide") == "non_english"
    assert rules_predict("My points are missing, and I want a refund.") == "multi_issue"
    assert rules_predict("My points are missing.") == "missing_points"


def test_the_app_doesnt_import_the_classifier() -> None:
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "sklearn" not in text and "routing_baseline" not in text, path.name
