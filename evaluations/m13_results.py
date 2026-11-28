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
import re
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
RUN_LOGS = OUT / "run-logs"


def requeued_jobs(name: str, logs: Path = RUN_LOGS) -> int | None:
    """Worker jobs the runner requeued during a run ("job requeued ... OperationalError"), from its console log.

    A requeue is the system's own recovery (TD-57), but it adds time to that case, so it's reported per run. None when
    the log is missing. Windows PowerShell writes the log as UTF-16; anything else is read as UTF-8.
    """
    path = logs / f"{name}.log"
    if not path.exists():
        return None
    return _log_text(path).count("job requeued")


def _log_text(path: Path) -> str:
    raw = path.read_bytes()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")


_PROGRESS = re.compile(r"^\s*(\d+)/\d+ cases\s*$")


def requeue_blocks(name: str, logs: Path = RUN_LOGS) -> list[int]:
    """For each requeue line, the number of cases finished before it (the start of its block of 10).

    The runner prints progress after every 10 cases, and worker lines arrive in order, so a requeue between "50/80"
    and "60/80" happened while cases 51 to 60 ran. Fixed on 2026-11-27, before the D2 re-run, because the frozen
    runner records no job-to-case link (verification log, Milestone 13).
    """
    path = logs / f"{name}.log"
    if not path.exists():
        return []
    done, blocks = 0, []
    for line in _log_text(path).splitlines():
        found = _PROGRESS.match(line)
        if found:
            done = int(found.group(1))
        elif "job requeued" in line:
            blocks.append(done)
    return blocks


def requeued_cases(name: str, others: Sequence[str], live: Path = LIVE, logs: Path = RUN_LOGS) -> tuple[list[str], str]:
    """Which cases a run's requeues hit, by the rule fixed before the re-run: in the requeue's block of 10, the case
    whose `ai_runs` is higher than in every other run named (the no-cache runs). A requeued investigation runs the AI
    loop again. If that doesn't single out exactly one case per requeue, the whole block counts, and the reason says so.
    """
    order = [r.case_id for r in load_run(live / name).results]
    runs = {r.case_id: r.ai_runs for r in load_run(live / name).results}
    elsewhere: dict[str, int] = {}
    for other in others:
        for r in load_run(live / other).results:
            elsewhere[r.case_id] = max(elsewhere.get(r.case_id, 0), r.ai_runs)
    chosen: list[str] = []
    notes = []
    for start in requeue_blocks(name, logs):
        block = order[start : start + 10]
        higher = [c for c in block if runs[c] > elsewhere.get(c, 0)]
        if len(higher) == 1:
            chosen += higher
            notes.append(f"cases {start + 1}-{start + 10}: {higher[0]} (more AI runs than in every no-cache run)")
        else:
            chosen += block
            notes.append(f"cases {start + 1}-{start + 10}: {len(higher)} candidates, so the whole block is left out")
    return sorted(set(chosen)), "; ".join(notes)


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
        "requeued_jobs": requeued_jobs(name),
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
        "| Later calls reading cache | $ per 1,000 cases | Requeued jobs |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        for r in result["runs"][arm]:
            lat = r["latency_s"]
            lines.append(
                f"| {r['run']} | {r['cases']} | {r['case_success']} | {r['false_approvals']} | "
                f"{lat['p50']} / {lat['p95']} / {lat['p99']} | {r['model_calls']} | "
                f"{r['cache_read_share_of_input']:.1%} | {r['later_calls_reading_cache']}/{r['later_calls']} | "
                f"${r['cost_usd_per_1000_cases']:.2f} | {r['requeued_jobs']} |"
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
    for key, title in (
        ("comparison_all_runs", "All three runs per arm"),
        (
            "comparison_clean_runs_1_2",
            "Runs 1 and 2 only (the clean comparison: before the requeue and the shared load)",
        ),
    ):
        c = result.get(key)
        if not c:
            continue
        lines += [
            f"## {title}",
            "",
            "| | No cache (A) | Prompt caching (D) |",
            "|---|---|---|",
            f"| Case success | {c['A']['case_success']} of {c['A']['cases'] // len(c['A']['runs'])} | "
            f"{c['D']['case_success']} of {c['D']['cases'] // len(c['D']['runs'])} |",
            f"| False approvals | {c['A']['false_approvals']} | {c['D']['false_approvals']} |",
            f"| p50 / p95 draft-ready (s) | {c['A']['p50_s']} / {c['A']['p95_s']} | "
            f"{c['D']['p50_s']} / {c['D']['p95_s']} |",
            f"| Model calls per case | {c['A']['model_calls_per_case']} | {c['D']['model_calls_per_case']} |",
            f"| Later calls reading the cache | {c['A']['later_calls_reading_cache'][0]} of "
            f"{c['A']['later_calls_reading_cache'][1]} | {c['D']['later_calls_reading_cache'][0]} of "
            f"{c['D']['later_calls_reading_cache'][1]} |",
            f"| Cost per case | ${c['A']['cost_usd_per_case']:.6f} | ${c['D']['cost_usd_per_case']:.6f} "
            f"(**{c['cost_change']:+.1%}**) |",
        ]
        for volume, p in c["projections"].items():
            lines.append(
                f"| Per month at {p['cases_per_month']:,} cases ({volume.replace('_', ' ')}; **projection**) | "
                f"${p['a_usd_per_month']:.2f} | ${p['d_usd_per_month']:.2f} (saves ${p['saving_usd_per_month']:.2f}; "
                f"${p['saving_usd_per_year']:.2f} a year) |"
            )
        lines.append("")
    flagged = result.get("requeue_sensitivity") or []
    if flagged:
        lines += [
            "## Flagged: runs with requeued jobs (kept, as the owner decided on 2026-11-27)",
            "",
            "A requeue is the worker recovering from a database error (likely TD-57, the SQLite lock race in the "
            "benchmark environment). The pass marks above use every case; this shows how much the requeues moved p95.",
            "",
            "| Run | Requeued jobs | p95, all cases (s) | p95 without the requeued cases (s) | Cases left out | How |",
            "|---|---:|---:|---:|---|---|",
        ]
        for f in flagged:
            lines.append(
                f"| {f['run']} | {f['requeued_jobs']} | {f['p95_all_cases']} | {f['p95_without_requeued_cases']} | "
                f"{', '.join(f['cases_left_out'])} | {f['how']} |"
            )
        lines.append("")
    return "\n".join(lines)


def smoke(name: str, ledger: list[dict[str, Any]]) -> int:
    rows = [r for r in ledger if r["run"] == name]
    reading = sum(1 for r in rows if r.get("cache_read_tokens", 0) > 0)
    print(f"{name}: {len(rows)} calls, {reading} read the cache")
    if not rows or reading == 0:
        print("SMOKE FAILED: no call read the cache. Stop and look before the full runs.")
        return 1
    return 0


MONTHLY_CASES = {"two_properties": 320, "hundred_properties": 16000}  # docs/load-profile.md; 100 = 50 x 320
CLEAN_RUNS = 2  # the owner's reading (2026-11-28): runs 1 and 2 of each arm, before the requeue and the shared load


def comparison(a: Sequence[dict[str, Any]], d: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Arm against arm over the runs given: quality, latency, calls, cache use, cost, and the monthly cost at the
    stated volumes. The monthly figures are projections: measured cost per case times an assumed volume."""

    def side(rs: Sequence[dict[str, Any]]) -> dict[str, Any]:
        cases = sum(r["cases"] for r in rs)
        cost = sum(r["cost_usd"] for r in rs)
        return {
            "runs": [r["run"] for r in rs],
            "cases": cases,
            "case_success": [r["case_success"] for r in rs],
            "false_approvals": [r["false_approvals"] for r in rs],
            "p50_s": [r["latency_s"]["p50"] for r in rs],
            "p95_s": [r["latency_s"]["p95"] for r in rs],
            "model_calls_per_case": round(sum(r["model_calls"] for r in rs) / cases, 3),
            "later_calls_reading_cache": [
                sum(r["later_calls_reading_cache"] for r in rs),
                sum(r["later_calls"] for r in rs),
            ],
            "cost_usd_per_case": round(cost / cases, 6),
            "cost_usd_per_1000_cases": round(cost / cases * 1000, 2),
        }

    sa, sd = side(a), side(d)
    change = sd["cost_usd_per_case"] / sa["cost_usd_per_case"] - 1
    projections = {
        volume: {
            "cases_per_month": n,
            "a_usd_per_month": round(sa["cost_usd_per_case"] * n, 2),
            "d_usd_per_month": round(sd["cost_usd_per_case"] * n, 2),
            "saving_usd_per_month": round((sa["cost_usd_per_case"] - sd["cost_usd_per_case"]) * n, 2),
            "saving_usd_per_year": round((sa["cost_usd_per_case"] - sd["cost_usd_per_case"]) * n * 12, 2),
        }
        for volume, n in MONTHLY_CASES.items()
    }
    return {
        "A": sa,
        "D": sd,
        "cost_change": round(change, 4),
        "projection_label": "projection",
        "projections": projections,
    }


def requeue_sensitivity(runs: Mapping[str, Sequence[dict[str, Any]]], live: Path = LIVE) -> list[dict[str, Any]]:
    """The owner's rule (2026-11-27): a run with requeues is kept, and its p95 is shown with and without the requeued
    cases, flagged. The pass marks themselves use every case."""
    out = []
    for arm, stats in runs.items():
        others = ARMS["A"] if arm == "D" else ARMS["D"]
        for r in stats:
            if not r.get("requeued_jobs"):
                continue
            cases, how = requeued_cases(r["run"], others, live)
            kept = [x.latency_s for x in load_run(live / r["run"]).results if x.case_id not in cases and x.latency_s]
            out.append(
                {
                    "run": r["run"],
                    "requeued_jobs": r["requeued_jobs"],
                    "cases_left_out": cases,
                    "how": how,
                    "p95_all_cases": r["latency_s"]["p95"],
                    "p95_without_requeued_cases": _pct(kept, 95),
                }
            )
    return out


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
    result: dict[str, Any] = {"label": LABEL, "runs": runs, "pass_marks": pass_marks(runs["A"], runs["D"])}
    result["requeue_sensitivity"] = requeue_sensitivity(runs)
    result["comparison_all_runs"] = comparison(runs["A"], runs["D"])
    result["comparison_clean_runs_1_2"] = comparison(runs["A"][:CLEAN_RUNS], runs["D"][:CLEAN_RUNS])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase3-results.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    (OUT / "phase3-results.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    print(markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
