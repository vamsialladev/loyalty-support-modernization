"""The eval-harness export: the harness's case schema, live runs only, and Stage 9's own verdicts (REUSE-03)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluations.export_eval_harness import PROJECT, export, property_of, scored
from evaluations.scoring import CaseResult

HARNESS_PROPERTIES = {"beach-resort", "mountain-lodge"}
HARNESS_SPLITS = {"dev", "held-out", "visitor"}
HARNESS_BEHAVIOURS = {"answer", "refuse", "escalate", "greeting", "off_topic"}


def test_every_case_fits_the_harness_schema(tmp_path: Path) -> None:
    cases, outputs = export(tmp_path)
    assert (cases, outputs) == (180, 340)
    rows = [json.loads(line) for line in (tmp_path / "p9.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len({row["id"] for row in rows}) == 180
    for row in rows:
        assert row["project"] == PROJECT and row["property"] in HARNESS_PROPERTIES
        assert row["split"] in HARNESS_SPLITS and row["expected"]["behaviour"] in HARNESS_BEHAVIOURS
        assert row["input"]["email"]["body"] and "SYNTHETIC" in row["notes"]


def test_only_complete_live_runs_go_out_and_the_meta_says_so(tmp_path: Path) -> None:
    export(tmp_path)
    meta = json.loads((tmp_path / "p9-arm-c-live-2026-11-07.meta.json").read_text(encoding="utf-8"))
    assert meta["mode"] == "live" and meta["project"] == PROJECT and "SYNTHETIC" in meta["description"]
    outputs = [
        json.loads(line)
        for line in (tmp_path / "p9-arm-c-live-2026-11-07.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all(o["api_calls"] >= 1 for o in outputs) and all(o["tokens_in"] > 0 for o in outputs)


def test_a_stay_prefix_gives_the_property_even_with_no_record() -> None:
    label = {"case_id": "X", "stays": [], "facts": {"claimed_stay_ids": ["ML-1234"]}}
    assert property_of(label) == "mountain-lodge"


def test_the_verdicts_are_the_pre_registered_definitions() -> None:
    label = {
        "expected_outcome": "adjusted",
        "next_action": "adjust",
        "stays": [{"stay_id": "S1", "expected_final_points": 100}],
    }
    over = CaseResult("X", "C", 1, "live", "adjust", "adjusted", final_points={"S1": 200})
    verdicts = scored(over, label)
    assert verdicts["no_false_approval"] is False and verdicts["case_success"] is False
    assert verdicts["no_duplicate_credit"] and verdicts["no_unauthorized_action"]
