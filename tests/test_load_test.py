"""The load-test report (OPS-01, ADR-0083): its numbers come from the samples, and it carries its label."""

from __future__ import annotations

from scripts.load_test import LABEL, Results, Sample, Stage, pct, report


def test_percentiles_use_the_samples_themselves() -> None:
    values = [float(v) for v in range(1, 101)]
    assert pct(values, 50) == 51 and pct(values, 95) == 95 and pct(values, 99) == 99
    assert pct([7.0], 95) == 7.0


def test_the_report_counts_requests_failures_and_investigations_per_stage() -> None:
    stage = Stage("baseline", 2, 1, 10)
    results = Results(
        samples=[
            Sample("baseline", "api", "GET /queue", 200, 40.0, 0),
            Sample("baseline", "api", "GET /queue", 200, 60.0, 0),
            Sample("baseline", "api", "GET /queue", 503, 900.0, 0),
            Sample("baseline", "api", "POST /api/v1/cases", 0, 30000.0, 0),  # a transport error counts as a failure
            Sample("baseline", "investigation", "none", 200, 1500.0, 0),
            Sample("baseline", "investigation", "failed", 200, 2500.0, 0),
        ],
        queue=[("baseline", 0.0, 3, 4.0), ("baseline", 2.0, 1, 1.0)],
        db={
            "baseline": {
                "connections": 6,
                "commits": 10,
                "rollbacks": 1,
                "cache_hit": 0.99,
                "deadlocks": 0,
                "tables": {"case_events": {"seq_scan": 4}},
            }
        },
    )
    text = report([stage], results, "2026-11-14T00:00:00+00:00", "2026-11-14T00:01:00+00:00")
    assert LABEL in text and "not production capacity" in text
    assert "| baseline | `GET /queue` | 3 | 1 |" in text
    assert "| baseline | 2 + 1 | 10 | 4 | 0.4 | 50.00% |" in text
    # Nearest rank: of two samples (1.5 s, 2.5 s), p50 is the lower and p95 the higher.
    assert "| baseline | 2 | 1.5 | 2.5 | 2.5 | {'none': 1, 'failed': 1} |" in text
    assert "| baseline | 2 | 3 | 4 | 2.0 |" in text
    assert "| baseline | 6 | 10 | 1 | 0.99 | 0 | 4 |" in text
