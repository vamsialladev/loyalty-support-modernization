"""The label review's sensitivity check: in-memory readings only, regenerable, and the baseline is the published one."""

from __future__ import annotations

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
