"""Milestone 13, Phase 1: the caching baseline is measured from stored files and reproduces (CACHE-01)."""

from __future__ import annotations

import json

import pytest

from evaluations import m13_baseline as baseline


def test_masking_removes_names_emails_codes_and_numbers() -> None:
    text = "Hi, I'm Leila Sato (leila.sato3@mail.test). Stay BR-6754, June 14-16, member GR-97315."
    masked = baseline.mask(text, {"leila", "sato"})
    words = masked.split()
    for leaked in ("leila", "sato", "leila.sato3@mail.test", "br", "6754", "97315", "june", "14"):
        assert leaked not in words
    assert "<name>" in masked and "<email>" in masked and "<code>" in masked and "<month>" in masked


@pytest.mark.parametrize("run", baseline.FROZEN_RUNS)
def test_every_stored_case_is_matched_to_its_own_model_calls(run: str) -> None:
    ledger = baseline._jsonl(baseline.LEDGER)
    groups = baseline._segment(run, ledger)
    rows = baseline._jsonl(baseline.LIVE / run / "results.jsonl")
    assert len(groups) == len(rows)
    for calls, row in zip(groups, rows, strict=True):
        assert sum(c["input_tokens"] for c in calls) == row["input_tokens"]
        assert sum(c["output_tokens"] for c in calls) == row["output_tokens"]


def test_a_ledger_that_does_not_add_up_is_refused() -> None:
    ledger = [c for c in baseline._jsonl(baseline.LEDGER) if c["run"] == "c-fairness"]
    with pytest.raises(ValueError):
        baseline._segment("c-fairness", ledger[1:])


def test_the_cache_projection_reads_only_what_the_previous_call_sent() -> None:
    calls = [[{"input_tokens": 100}, {"input_tokens": 150}, {"input_tokens": 200}]]
    p = baseline._cache_projection(calls, read=0.1, write=1.25)
    assert p["resent_from_previous_call"] == 250  # 100 then 150
    # 100 x 1.25 + (100 x 0.1 + 50 x 1.25) + (150 x 0.1 + 50 x 1.25)
    assert p["input_cost_units_cached"] == pytest.approx(275.0)


def test_the_committed_baseline_is_reproduced() -> None:
    committed = json.loads(baseline.OUT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(baseline.build())) == committed  # tuples come back as lists
