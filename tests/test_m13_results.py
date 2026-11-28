"""Milestone 13, Phase 3: the results script scores runs as Milestone 10 did, and applies the pre-registered pass
marks exactly (CACHE-03). Uses stored Milestone 10 runs and made-up numbers; no live call."""

from __future__ import annotations

from typing import Any

import pytest

from evaluations import m13_results as res
from evaluations.m13_baseline import _jsonl
from evaluations.run import read_labels


def test_a_stored_milestone_10_run_scores_as_its_committed_report_says() -> None:
    # benchmarks/reports/heldout/comparison.md: arm C live, run 1: 78/80 case success, 0/80 false approvals.
    stats = res.run_stats("c-heldout-r1", read_labels("heldout"), _jsonl(res.LEDGER))
    assert (stats["cases"], stats["case_success"], stats["false_approvals"]) == (80, 78, 0)
    assert stats["model_calls"] == 297 and stats["cost_usd"] == pytest.approx(0.13652, abs=1e-6)
    assert stats["cache_read_tokens"] == 0 and stats["later_calls_reading_cache"] == 0  # no caching then


def _run(success: int, approvals: int, p95: float, later: int, reading: int, cost: float) -> dict[str, Any]:
    return {
        "cases": 80,
        "case_success": success,
        "false_approvals": approvals,
        "latency_s": {"p50": 7.0, "p95": p95, "p99": p95 + 1},
        "later_calls": later,
        "later_calls_reading_cache": reading,
        "cost_usd": cost,
    }


def test_the_comparison_and_its_projections_come_from_the_run_numbers() -> None:
    a = [dict(_run(78, 0, 12.0, 220, 0, 0.140), run="a1", model_calls=300) for _ in range(2)]
    d = [dict(_run(78, 0, 11.0, 220, 210, 0.098), run="d1", model_calls=296) for _ in range(2)]
    c = res.comparison(a, d)
    assert (c["A"]["cost_usd_per_case"], c["D"]["cost_usd_per_case"]) == (0.00175, 0.001225)
    assert c["cost_change"] == -0.3  # 0.001225 / 0.00175 - 1
    hundred = c["projections"]["hundred_properties"]
    assert (hundred["cases_per_month"], hundred["saving_usd_per_month"], hundred["saving_usd_per_year"]) == (
        16000,
        8.4,
        100.8,
    )
    assert c["projection_label"] == "projection" and c["D"]["later_calls_reading_cache"] == [420, 440]


def test_all_pass_marks_met() -> None:
    a = [_run(78, 0, 11.0, 220, 0, 0.136), _run(77, 0, 11.5, 220, 0, 0.137), _run(78, 0, 11.2, 220, 0, 0.136)]
    d = [_run(77, 0, 11.4, 220, 210, 0.095), _run(78, 0, 10.9, 220, 215, 0.096), _run(76, 0, 11.5, 220, 212, 0.094)]
    marks = res.pass_marks(a, d)
    assert marks["case_success"]["floor"] == 76  # A's lowest (77) minus A's range (1)
    assert marks["all"]["pass"] is True


@pytest.mark.parametrize(
    ("change", "failed"),
    [
        ({"case_success": 75}, "case_success"),
        ({"false_approvals": 1}, "false_approvals"),
        ({"p95": 11.6}, "p95_draft_ready_s"),
        ({"reading": 160}, "cache_used"),  # 160 + 2 x 215 = 590 of 660 later calls: 89.4%, under 90%
        ({"cost": 0.130}, "cost_per_case"),  # D $0.330 vs A $0.409 over 240 cases: a 19.3% cut, under 20%
    ],
)
def test_each_pass_mark_can_fail_on_its_own(change: dict[str, Any], failed: str) -> None:
    a = [_run(78, 0, 11.0, 220, 0, 0.136), _run(77, 0, 11.5, 220, 0, 0.137), _run(78, 0, 11.2, 220, 0, 0.136)]
    first = {"success": 77, "approvals": 0, "p95": 11.4, "later": 220, "reading": 215, "cost": 0.100}
    first |= {
        "success" if k == "case_success" else "approvals" if k == "false_approvals" else k: v for k, v in change.items()
    }
    d = [_run(*first.values()), _run(78, 0, 10.9, 220, 215, 0.100), _run(77, 0, 11.0, 220, 215, 0.100)]
    marks = res.pass_marks(a, d)
    assert [k for k, m in marks.items() if not m["pass"]] == [failed, "all"]


def test_the_smoke_check_stops_unless_some_call_read_the_cache(capsys: pytest.CaptureFixture[str]) -> None:
    ledger = [
        {"run": "s", "input_tokens": 2100, "cache_read_tokens": 0},
        {"run": "s", "input_tokens": 300, "cache_read_tokens": 2200},
    ]
    assert res.smoke("s", ledger) == 0
    assert res.smoke("s", [dict(r, cache_read_tokens=0) for r in ledger]) == 1
    assert res.smoke("missing", ledger) == 1
    assert "SMOKE FAILED" in capsys.readouterr().out


def test_requeued_jobs_are_counted_from_either_log_encoding(tmp_path: Any) -> None:
    line = "  10/80 cases\njob requeued id=80 kind=investigate_case code=OperationalError\n  20/80 cases\n"
    (tmp_path / "a.log").write_bytes(b"\xff\xfe" + line.encode("utf-16-le"))  # Windows PowerShell's Tee-Object
    (tmp_path / "b.log").write_text(line * 2, encoding="utf-8")
    assert res.requeued_jobs("a", tmp_path) == 1
    assert res.requeued_jobs("b", tmp_path) == 2
    assert res.requeued_jobs("missing", tmp_path) is None


def test_a_requeue_is_placed_in_its_block_of_ten(tmp_path: Any) -> None:
    lines = ["  10/80 cases", "  20/80 cases", "job requeued id=80 kind=investigate_case code=OperationalError",
             "  30/80 cases", "job requeued id=91 kind=investigate_case code=OperationalError"]  # fmt: skip
    (tmp_path / "r.log").write_bytes(b"\xff\xfe" + "\r\n".join(lines).encode("utf-16-le"))
    assert res.requeue_blocks("r", tmp_path) == [20, 30]
    assert res.requeue_blocks("missing", tmp_path) == []
