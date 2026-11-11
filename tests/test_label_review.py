"""The label review's sensitivity check: in-memory readings only, regenerable, and the baseline is the published one."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from evaluations import label_review
from evaluations.run import DATASET, read_labels

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "benchmarks" / "reports" / "heldout"


def test_a_reading_changes_a_copy_and_never_the_label_files() -> None:
    before = (DATASET / "labels" / "heldout.jsonl").read_bytes()
    labels = read_labels("heldout", DATASET)
    changed = label_review.apply(labels, [label_review.ho078_as_pending_posting, label_review.ho062_without_the_reply])
    assert changed["HO-078"]["next_action"] == "no_adjustment_pending"
    assert changed["HO-062"]["expected_outcome"] == "no_adjustment"
    assert labels["HO-078"]["next_action"] == "wait_until" and labels["HO-062"]["expected_outcome"] == "adjusted"
    assert (DATASET / "labels" / "heldout.jsonl").read_bytes() == before


def test_the_waiting_period_reading_touches_only_wait_cases() -> None:
    labels = read_labels("heldout", DATASET)
    changed = label_review.apply(labels, [label_review.waiting_period_as_eligible])
    moved = {case for case in labels if labels[case]["eligibility"] != changed[case]["eligibility"]}
    assert moved and all(labels[case]["next_action"] == "wait_until" for case in moved)


def test_the_report_regenerates_from_the_stored_runs_and_starts_from_the_published_verdicts(tmp_path: Path) -> None:
    label_review.main(tmp_path)
    stored = json.loads((REPORTS / "label-review-sensitivity.json").read_text(encoding="utf-8"))
    fresh = json.loads((tmp_path / "label-review-sensitivity.json").read_text(encoding="utf-8"))
    assert fresh == stored
    assert (tmp_path / "label-review-sensitivity.md").read_text(encoding="utf-8") == (
        REPORTS / "label-review-sensitivity.md"
    ).read_text(encoding="utf-8")
    published = json.loads((REPORTS / "summary.json").read_text(encoding="utf-8"))
    baseline = stored["readings"]["As labelled (the published results)"]["verdicts"]
    assert baseline == {d["hypothesis"]: d["verdict"] for d in published["decisions"]}


REVIEWER_COLUMNS = ("reviewer_verdict", "reviewer_corrected_fields", "reviewer_note")


def _sheet(path: Path) -> list[dict[str, str]]:
    """Rows of a review sheet, with line breaks inside cells normalized (git stores the CSV as LF, checks out CRLF)."""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [{k: v.replace("\r\n", "\n") for k, v in row.items()} for row in csv.DictReader(fh)]


def _facts(row: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in row.items() if k not in REVIEWER_COLUMNS}


def test_the_owners_filled_sheet_keeps_its_verdicts_and_the_generated_facts(generated: Path) -> None:
    """The owner's filled sheet (2026-11-11): a regeneration that blanks it, or an edit to its facts, fails here."""
    filled = _sheet(ROOT / "evaluations/label-review/review-sheet.csv")
    fresh = _sheet(generated / "evaluations/label-review/review-sheet.csv")
    assert [_facts(row) for row in filled] == [_facts(row) for row in fresh]
    assert [row["reviewer_verdict"] for row in filled] == ["agree"] * 30
    assert all(row["reviewer_corrected_fields"] == "" and row["reviewer_note"] for row in filled)


def test_every_results_text_says_h2_rests_on_ho_062_alone() -> None:
    """The owner's rule (2026-11-10): wherever results appear, so does H2's dependence on one case."""
    from evaluations.compare import H2_RESTS_ON_HO_062

    for path in (REPORTS / "hypotheses.md", REPORTS / "business-value.md", ROOT / "docs/business-value-report.md"):
        assert H2_RESTS_ON_HO_062 in path.read_text(encoding="utf-8"), path
    assert "rests on a single test case" in (ROOT / "docs/executive-brief.md").read_text(encoding="utf-8")
