"""The benchmark's stored results and documents agree, and claim nothing they can't back (BENCH-06, BIZ-04, UI-02)."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from evaluations import dashboard, final_report
from evaluations.compare import load_run
from evaluations.decide import Runs
from evaluations.run import DATASET, RESULTS, read_labels
from evaluations.run_config import hard_cap_usd
from evaluations.spend import LEDGER, spent_usd
from tests.conftest import ROOT

REPORTS = ROOT / "benchmarks" / "reports" / "heldout"
SUMMARY: dict[str, Any] = json.loads((REPORTS / "summary.json").read_text(encoding="utf-8"))


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def stored() -> tuple[Runs, Runs, Runs, dict[str, Any]]:
    labels = read_labels("heldout", DATASET)
    deterministic, live = RESULTS / "deterministic", RESULTS / "live"
    return (
        Runs(load_run(deterministic / "a-heldout").results, labels),
        Runs(load_run(deterministic / "b-heldout").results, labels),
        Runs([r for n in (1, 2, 3) for r in load_run(live / f"c-heldout-r{n}").results], labels),
        labels,
    )


def test_the_verdicts_can_be_regenerated_from_the_stored_runs() -> None:
    a, b, c, _labels = stored()
    gate = [r for run in (a, b, c) for r in run.results]
    decisions = final_report.decisions(a, b, c, gate)
    found = {d.hypothesis: d.verdict.value for d in decisions}
    assert found == {row["hypothesis"]: row["verdict"] for row in SUMMARY["decisions"]}


def test_the_decisive_runs_came_from_the_frozen_commit_and_were_complete() -> None:
    for folder in (
        "deterministic/a-heldout",
        "deterministic/b-heldout",
        "live/c-heldout-r1",
        "live/c-heldout-r2",
        "live/c-heldout-r3",
    ):
        manifest = json.loads((RESULTS / folder / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["tree_clean"] is True and manifest["interrupted"] is False, folder
        assert manifest["cases"] == manifest["planned_cases"] == 80, folder
        assert manifest["app_commit"].startswith("dd7ecb7"), folder


def test_arm_cs_decisive_runs_are_live_and_kept_apart_from_mock() -> None:
    assert json.loads((RESULTS / "live/c-heldout-r1/manifest.json").read_text(encoding="utf-8"))["kind"] == "live"
    assert json.loads((RESULTS / "mock/c-mock-dev/manifest.json").read_text(encoding="utf-8"))["kind"] == "mock"
    assert not (RESULTS / "mock/c-heldout-r1").exists()


def test_the_ledger_is_under_the_owners_cap() -> None:
    assert LEDGER.exists() and 0 < spent_usd() <= hard_cap_usd()


def test_nothing_changed_a_threshold_or_a_hypothesis_after_the_data() -> None:
    assert "None yet." in read("docs/hypotheses.md").split("## Change log")[1]


@pytest.mark.parametrize(
    "path",
    [
        "docs/error-analysis.md",
        "docs/business-value-report.md",
        "docs/root-cause-analysis.md",
        "docs/timing-protocol.md",
    ],
)
def test_each_document_says_its_synthetic(path: str) -> None:
    assert "SYNTHETIC" in read(path).upper()


def test_the_business_report_chooses_a_conclusion_and_keeps_kinds_of_number_apart() -> None:
    text = read("docs/business-value-report.md")
    assert "Non-AI fixes deliver most of the value. AI helps only in certain categories." in text
    for heading in ("What was observed", "What was estimated", "What was assumed", "What wasn't measured"):
        assert f"## {heading}" in text
    assert "nobody saved" in text.lower() and "**not tested**" in text


def test_the_error_analysis_doesnt_hide_what_h3_rests_on() -> None:
    text = read("docs/error-analysis.md")
    assert "**not supported**" in text and "+4.5 pp" in text and "77 vs 78 of 80" in text


@pytest.mark.parametrize(
    ("document", "number"),
    [
        ("docs/business-value-report.md", "68.6%"),
        ("docs/business-value-report.md", "99.8%"),
        ("docs/business-value-report.md", "$953.72"),
        ("docs/business-value-report.md", "$0.55"),
    ],
)
def test_the_business_reports_numbers_are_the_generated_ones(document: str, number: str) -> None:
    assert number in read(document) and number in read("benchmarks/reports/heldout/business-value.md")


def test_every_slice_report_says_what_it_covers() -> None:
    assert "every scenario, tier, region, channel, language and style" in read(
        "benchmarks/reports/heldout/a-or-b-beats-c.md"
    )


def test_the_dashboard_escapes_and_labels_and_isnt_served_by_the_app() -> None:
    assert "&lt;script&gt;" in dashboard.inline("<script>")
    assert "Independent portfolio simulation" in dashboard.build()
    for path in (ROOT / "app").rglob("*.py"):
        assert not re.search(r"dashboard\.html", path.read_text(encoding="utf-8")), path
