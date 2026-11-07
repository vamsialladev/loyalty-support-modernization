"""One command compares runs (spec E.3, Appendix B; BENCH-03, -05, -06). It reports. It only ever decides on held-out.

    uv run python -m evaluations.compare benchmarks/results/deterministic/a-dev benchmarks/results/deterministic/b-dev

Always counts and denominators, false approvals and false denials apart, and per-scenario tables, so a dangerous error
can't hide in a total. A run's kind (deterministic, mock or live) labels its column, and kinds are never pooled.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any

from evaluations import member
from evaluations.decide import difference, latency_p95
from evaluations.run import DATASET, read_labels
from evaluations.run_config import ROOT
from evaluations.scoring import (
    LINKS,
    CaseResult,
    Label,
    case_success,
    clarification_found,
    correct_action,
    false_approval,
    false_denial,
    first_failed_link,
    ledger_correct,
    unnecessary_request,
)

REPORTS = ROOT / "benchmarks" / "reports"
HEADER = (
    "> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human "
    "timing and not real people. Labels come from scenario facts, and aren't independently reviewed yet."
)
Labels = Mapping[str, Label]
IGNORED_IN_REPEATS = ("latency_s",)  # a repeat must match on everything but the clock


@dataclass(frozen=True)
class Run:
    name: str
    manifest: dict[str, Any]
    results: tuple[CaseResult, ...]

    @property
    def title(self) -> str:
        variant = " (second look)" if "second look" in self.manifest.get("after_stop", "") else ""
        return f"{self.results[0].arm}{variant} [{self.manifest['kind']}]" if self.results else self.name


def load_run(folder: Path) -> Run:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    lines = (folder / "results.jsonl").read_text(encoding="utf-8").splitlines()
    return Run(folder.name, manifest, tuple(CaseResult(**json.loads(line)) for line in lines if line.strip()))


def _count(results: Sequence[CaseResult], labels: Labels, test: Any) -> int:
    return sum(1 for r in results if test(r, labels[r.case_id]))


def _percent(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator} ({numerator / denominator * 100:.1f}%)" if denominator else f"{numerator}/0"


def summary_rows(run: Run, labels: Labels) -> dict[str, str]:
    results = run.results
    total = len(results)
    needing = [r for r in results if clarification_found(r, labels[r.case_id]) is not None]
    found = sum(1 for r in needing if clarification_found(r, labels[r.case_id]))
    proxies = [
        member.satisfaction_proxy(r.contacts, r.reopened, false_denial(r, labels[r.case_id]), r.simulated_days)
        for r in results
    ]
    latencies = [r.latency_s for r in results if r.latency_s is not None]
    return {
        "Case success (final ledger, outcome, no duplicate)": _percent(_count(results, labels, case_success), total),
        "Final ledger correct": _percent(_count(results, labels, ledger_correct), total),
        "Correct first action": _percent(_count(results, labels, correct_action), total),
        "False approvals (over-credit)": _percent(_count(results, labels, false_approval), total),
        "False denials (under-credit)": _percent(_count(results, labels, false_denial), total),
        "Left unresolved": _percent(sum(1 for r in results if r.outcome == "unresolved"), total),
        "Duplicate credits": str(sum(r.duplicate_credits for r in results)),
        "Unauthorized actions": str(sum(r.unauthorized_actions for r in results)),
        "Clarification found": _percent(found, len(needing)),
        "Unnecessary information requests": str(_count(results, labels, unnecessary_request)),
        "Simulated contacts per case": f"{sum(r.contacts for r in results) / total:.2f}" if total else "n/a",
        "Simulated days per case": f"{sum(r.simulated_days for r in results) / total:.2f}" if total else "n/a",
        "Modelled satisfaction proxy (not real sentiment)": f"{sum(proxies) / total:.2f}" if total else "n/a",
        "Script time p50 / p95 (not human timing)": (
            f"{median(latencies):.2f} s / {latency_p95(latencies):.2f} s" if latencies else "n/a"
        ),
    }


def funnel(run: Run, labels: Labels) -> Counter[str]:
    """Where each case first went wrong (F7)."""
    return Counter(first_failed_link(r, labels[r.case_id]) or "every link held" for r in run.results)


def by_scenario(run: Run, labels: Labels) -> dict[str, tuple[int, int, int, int, int]]:
    """Scenario -> cases, successes, right ledgers, false approvals, false denials."""
    out: dict[str, list[int]] = {}
    for r in run.results:
        label = labels[r.case_id]
        row = out.setdefault("+".join(label["scenarios"]), [0, 0, 0, 0, 0])
        row[0] += 1
        row[1] += case_success(r, label)
        row[2] += ledger_correct(r, label)
        row[3] += false_approval(r, label)
        row[4] += false_denial(r, label)
    return {key: (v[0], v[1], v[2], v[3], v[4]) for key, v in sorted(out.items())}


def repeat_differences(first: Run, second: Run) -> list[str]:
    """A deterministic arm's repeat must match exactly, on everything but the clock."""
    other = {r.case_id: asdict(r) for r in second.results}
    different = []
    for result in first.results:
        row = asdict(result)
        theirs = other.get(result.case_id, {})
        fields = [k for k in row if k not in (*IGNORED_IN_REPEATS, "run") and row[k] != theirs.get(k)]
        if fields:
            different.append(f"{result.case_id}: {', '.join(fields)}")
    return different


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "|" + "---|" * len(headers),
        *("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows),
    ]


def paired(first: Run, second: Run, labels: Labels, test: Any) -> str:
    a = {r.case_id: test(r, labels[r.case_id]) for r in first.results}
    b = {r.case_id: test(r, labels[r.case_id]) for r in second.results}
    if set(a) != set(b) or not a:
        return "not the same cases"
    cases = sorted(a)
    d = difference([a[c] for c in cases], [b[c] for c in cases])
    counts = f"{d.numerator_a} vs {d.numerator_b} of {d.denominator}"
    return f"{d.points:+.1f} pp (95% interval {d.low:+.1f} to {d.high:+.1f}; {counts})"


def _cells(table: dict[str, tuple[int, int, int, int, int]], name: str) -> str:
    return " / ".join(str(value) for value in table.get(name, ()))


def report(runs: Sequence[Run], labels: Labels, split: str) -> str:
    lines = [f"# Comparison on the {split} split", "", HEADER, ""]
    if split != "heldout":
        lines += [f"**No verdict.** Hypotheses are decided on the held-out split only. This is {split}.", ""]
    titles = [run.title for run in runs]
    rows = [summary_rows(run, labels) for run in runs]
    lines += [*_table(["Metric", *titles], [[key, *(row[key] for row in rows)] for key in rows[0]]), ""]

    lines += ["## Where each case first went wrong (failure funnel)", ""]
    counts = [funnel(run, labels) for run in runs]
    links = (*LINKS, "every link held")
    lines += [*_table(["First failed link", *titles], [[link, *(str(c[link]) for c in counts)] for link in links]), ""]

    lines += ["## By scenario: cases, successes, right ledgers, false approvals, false denials", ""]
    scenarios = [by_scenario(run, labels) for run in runs]
    names = sorted({name for table in scenarios for name in table})
    lines += [*_table(["Scenario", *titles], [[name, *(_cells(t, name) for t in scenarios)] for name in names]), ""]

    if len(runs) >= 2:
        lines += ["## Paired differences (later column minus earlier column)", ""]
        for first, second in pairwise(runs):
            lines += [
                f"- **{second.title} minus {first.title}**",
                f"- Case success: {paired(first, second, labels, case_success)}",
                f"- Correct first action: {paired(first, second, labels, correct_action)}",
            ]
        lines += [""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.compare")
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, help="where to write the markdown report")
    args = parser.parse_args(argv)
    runs = [load_run(folder) for folder in args.runs]
    splits = {run.manifest["split"] for run in runs}
    if len(splits) != 1:
        print(f"REFUSED: these runs are on different splits: {sorted(splits)}")
        return 2
    split = splits.pop()
    text = report(runs, read_labels(split, DATASET), split)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
