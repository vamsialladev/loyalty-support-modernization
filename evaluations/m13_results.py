"""Milestone 13, Phase 3: score the pre-registered A/D runs against their pass marks (CACHE-03).

    uv run python -m evaluations.m13_results                  # after the six held-out runs
    uv run python -m evaluations.m13_results --smoke NAME     # after the smoke run: did any call read the cache?

Arms and pass marks are the ones in `docs/m13-phase3-plan.md`, committed before the runs; nothing here can change
them. Case success and false approvals use Milestone 10's scorer (`evaluations/scoring.py`) on the stored records.
Cost is what the spend ledger recorded per call, so it is the billed amount at the configured rates, cached tokens
included. Writes `benchmarks/reports/m13/phase3-results.json` and `.md`. Real model, SYNTHETIC cases.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluations.compare import load_run
from evaluations.m13_baseline import _jsonl, _pct, _segment, _wilson
from evaluations.run import read_labels
from evaluations.run_config import ROOT
from evaluations.scoring import case_success, false_approval

LIVE = ROOT / "benchmarks" / "results" / "live"
LEDGER = LIVE / "spend-ledger.jsonl"
OUT = ROOT / "benchmarks" / "reports" / "m13"
ARMS = {
    "A": ("m13-a-r1", "m13-a-r2", "m13-a-r3"),
    "D": ("m13-d-r1", "m13-d-r2", "m13-d-r3"),
}
LABEL = (
    "Real model (claude-haiku-5-5) · SYNTHETIC cases and personal data · paired A/D regression on the frozen "
    "held-out split, not a held-out claim"
)
CACHE_USE_MIN = 0.90  # share of calls after a case's first that read the cache
COST_CUT_MIN = 0.20  # D's cost per case at least this much below A's


def run_stats(name: str, labels: Mapping[str, Any], ledger: list[dict[str, Any]], live: Path = LIVE) -> dict[str, Any]:
    run = load_run(live / name)
    results = run.results
    groups = _segment(name, ledger, live)
    later = [call for calls in groups for call in calls[1:]]
    calls = [call for calls in groups for call in calls]
    read = sum(c.get("cache_read_tokens", 0) for c in calls)
    write = sum(c.get("cache_write_tokens", 0) for c in calls)
    plain = sum(c["input_tokens"] for c in calls)
    cost = sum(c["cost_usd"] for c in calls)
    success = sum(case_success(r, labels[r.case_id]) for r in results)
    latencies = [r.latency_s for r in results if r.latency_s is not None]
    return {
        "run": name,
        "cases": len(results),
        "interrupted": any(r.interrupted for r in results),
        "case_success": success,
        "case_success_wilson95": _wilson(success, len(results)),
        "false_approvals": sum(false_approval(r, labels[r.case_id]) for r in results),
        "latency_s": {"p50": _pct(latencies, 50), "p95": _pct(latencies, 95), "p99": _pct(latencies, 99)},
        "model_calls": len(calls),
        "calls_per_case": round(len(calls) / len(results), 3) if results else math.nan,
        "input_tokens_uncached": plain,
        "cache_read_tokens": read,
        "cache_write_tokens": write,
        "cache_read_share_of_input": round(read / (read + write + plain), 4) if calls else 0.0,
        "later_calls": len(later),
        "later_calls_reading_cache": sum(1 for c in later if c.get("cache_read_tokens", 0) > 0),
        "cost_usd": round(cost, 6),
        "cost_usd_per_1000_cases": round(cost / len(results) * 1000, 4) if results else math.nan,
    }


def pass_marks(a: Sequence[dict[str, Any]], d: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Exactly the table in docs/m13-phase3-plan.md."""
    a_success = [r["case_success"] for r in a]
    floor = min(a_success) - (max(a_success) - min(a_success))
    d_later = sum(r["later_calls"] for r in d)
    d_reading = sum(r["later_calls_reading_cache"] for r in d)
    a_cost = sum(r["cost_usd"] for r in a) / sum(r["cases"] for r in a)
    d_cost = sum(r["cost_usd"] for r in d) / sum(r["cases"] for r in d)
    marks = {
        "wrong_reuses": {"value": 0, "pass": True, "how": "none possible: tests/test_prompt_cache.py, request test"},
        "case_success": {
            "value": [r["case_success"] for r in d],
            "floor": floor,
            "pass": min(r["case_success"] for r in d) >= floor,
        },
        "false_approvals": {
            "value": [r["false_approvals"] for r in d],
            "pass": all(r["false_approvals"] == 0 for r in d),
        },
        "p95_draft_ready_s": {
            "value": [r["latency_s"]["p95"] for r in d],
            "ceiling": max(r["latency_s"]["p95"] for r in a),
            "pass": max(r["latency_s"]["p95"] for r in d) <= max(r["latency_s"]["p95"] for r in a),
        },
        "cache_used": {
            "value": round(d_reading / d_later, 4) if d_later else 0.0,
            "minimum": CACHE_USE_MIN,
            "pass": bool(d_later) and d_reading / d_later >= CACHE_USE_MIN,
        },
        "cost_per_case": {
            "a_usd": round(a_cost, 6),
            "d_usd": round(d_cost, 6),
            "change": round(d_cost / a_cost - 1, 4) if a_cost else None,
            "pass": bool(a_cost) and d_cost <= a_cost * (1 - COST_CUT_MIN),
        },
    }
    marks["all"] = {"pass": all(m["pass"] for m in marks.values())}
    return marks


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Milestone 13, Phase 3: arm A (no cache) vs arm D (provider prompt caching)",
        "",
        f"> {LABEL}. Written by `python -m evaluations.m13_results`; pass marks from `docs/m13-phase3-plan.md`.",
        "",
        "| Run | Cases | Case success | False approvals | p50 / p95 / p99 s | Calls | Cache-read share "
        "| Later calls reading cache | $ per 1,000 cases |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        for r in result["runs"][arm]:
            lat = r["latency_s"]
            lines.append(
                f"| {r['run']} | {r['cases']} | {r['case_success']} | {r['false_approvals']} | "
                f"{lat['p50']} / {lat['p95']} / {lat['p99']} | {r['model_calls']} | "
                f"{r['cache_read_share_of_input']:.1%} | {r['later_calls_reading_cache']}/{r['later_calls']} | "
                f"${r['cost_usd_per_1000_cases']:.2f} |"
            )
    lines += ["", "| Pass mark | Result | Pass |", "|---|---|---|"]
    for key, mark in result["pass_marks"].items():
        if key == "all":
            continue
        shown = {k: v for k, v in mark.items() if k != "pass"}
        lines.append(f"| {key} | `{json.dumps(shown)}` | {'yes' if mark['pass'] else '**no**'} |")
    verdict = (
        "all pass marks met"
        if result["pass_marks"]["all"]["pass"]
        else "**at least one pass mark missed: L3 stays off**"
    )
    lines += ["", f"**Verdict:** {verdict}.", ""]
    return "\n".join(lines)


def smoke(name: str, ledger: list[dict[str, Any]]) -> int:
    rows = [r for r in ledger if r["run"] == name]
    reading = sum(1 for r in rows if r.get("cache_read_tokens", 0) > 0)
    print(f"{name}: {len(rows)} calls, {reading} read the cache")
    if not rows or reading == 0:
        print("SMOKE FAILED: no call read the cache. Stop and look before the full runs.")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.m13_results")
    parser.add_argument("--smoke", default="")
    args = parser.parse_args(argv)
    ledger = _jsonl(LEDGER)
    if args.smoke:
        return smoke(args.smoke, ledger)
    labels = read_labels("heldout")
    runs = {arm: [run_stats(name, labels, ledger) for name in names] for arm, names in ARMS.items()}
    if any(r["interrupted"] for rs in runs.values() for r in rs):
        print("An interrupted run is never scored (RFC-0003).")
        return 1
    result = {"label": LABEL, "runs": runs, "pass_marks": pass_marks(runs["A"], runs["D"])}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase3-results.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    (OUT / "phase3-results.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    print(markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
