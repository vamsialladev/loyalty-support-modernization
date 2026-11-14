"""The release gate for a prompt, model or AI change (spec E.6, E5; BENCH-13, ENT-22; ADR-0082).

Any change to what can alter arm C's behaviour re-runs the frozen mock regression: arm C on the dev split with the
mock provider, compared case by case with the committed known-good run `benchmarks/results/mock/c-mock-dev`. A
difference in any decision field fails the gate and lists the cases, so a person reviews them before release. That
same committed run is the known-good configuration to roll back to (its manifest names the commit).

    uv run python scripts/release_gate.py --base origin/main      # what CI runs on a pull request
    uv run python scripts/release_gate.py --force                 # run it whatever changed

Mock provider only (no API key, no cost). A candidate prompt or model is judged the same way in shadow: a person
runs it into its own folder and compares (`--candidate <run folder>`), and nothing of it reaches a case.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "benchmarks" / "results" / "mock" / "c-mock-dev"
GATE_RUN = "release-gate"
# Paths whose change can alter arm C's decisions. Scoring and reports aren't here: they don't change an arm.
AI_PATHS = (
    "config/prompts/",
    "config/ai/",
    "app/ai/",
    "app/adapters/mock_model.py",
    "app/adapters/anthropic_model.py",
    "app/services/assisted.py",
    "app/domain/eligibility.py",
    "policies/",
)
DECISION_FIELDS = (
    "outcome",
    "final_points",
    "first_action",
    "approved",
    "executed",
    "eligibility",
    "identified_stays",
    "policies",
    "duplicate_credits",
    "unauthorized_actions",
    "ai_stops",
    "ai_fallbacks",
)


def changed_files(base: str) -> list[str]:
    git = shutil.which("git") or "git"
    out = subprocess.run(  # noqa: S603 - fixed arguments, no shell
        [git, "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def ai_changes(files: list[str]) -> list[str]:
    return [f for f in files if f.startswith(AI_PATHS)]


def load(folder: Path) -> dict[tuple[str, int], dict[str, Any]]:
    records: dict[tuple[str, int], dict[str, Any]] = {}
    for line in (folder / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[(record["case_id"], int(record.get("run", 1)))] = record
    return records


def compare(
    baseline: dict[tuple[str, int], dict[str, Any]], candidate: dict[tuple[str, int], dict[str, Any]]
) -> list[str]:
    """Every difference in a decision field, as one line each. Missing or extra cases are differences too."""
    lines: list[str] = []
    for key in sorted(set(baseline) | set(candidate)):
        before, after = baseline.get(key), candidate.get(key)
        if before is None or after is None:
            lines.append(f"{key[0]} run {key[1]}: {'missing from the candidate' if after is None else 'new case'}")
            continue
        for name in DECISION_FIELDS:
            if before.get(name) != after.get(name):
                lines.append(f"{key[0]} run {key[1]}: {name} {before.get(name)!r} -> {after.get(name)!r}")
    return lines


def run_candidate() -> Path:
    folder = ROOT / "benchmarks" / "results" / "mock" / GATE_RUN
    if folder.exists():
        shutil.rmtree(folder)
    command = [sys.executable, "-m", "evaluations.run", "--arm", "c-mock", "--split", "dev", "--name", GATE_RUN]
    subprocess.run(command, cwd=ROOT, check=True)  # noqa: S603 - fixed arguments, no shell
    return folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts/release_gate.py")
    parser.add_argument("--base", default="origin/main", help="compare with this ref to see what changed")
    parser.add_argument("--force", action="store_true", help="run whatever changed")
    parser.add_argument("--candidate", type=Path, help="an existing run folder to compare (shadow), instead of a run")
    parser.add_argument("--keep", action="store_true", help="keep the gate's run folder")
    args = parser.parse_args(argv)

    if args.candidate is None and not args.force:
        touched = ai_changes(changed_files(args.base))
        if not touched:
            print(f"release gate: nothing that can change arm C changed since {args.base}; not needed")
            return 0
        print("release gate: AI-relevant changes: " + ", ".join(touched))
    folder = args.candidate or run_candidate()
    try:
        differences = compare(load(BASELINE), load(folder))
    finally:
        if args.candidate is None and not args.keep:
            shutil.rmtree(folder, ignore_errors=True)
    if differences:
        print(f"release gate FAILED: {len(differences)} difference(s) from {BASELINE.relative_to(ROOT)}:")
        for line in differences[:50]:
            print("  " + line)
        print("A person reviews these. If they're intended, re-baseline with a reviewed commit (docs/release-gate.md).")
        return 1
    cases = len(load(BASELINE))
    print(f"release gate passed: {cases} case runs match {BASELINE.relative_to(ROOT)} on every decision field")
    return 0


if __name__ == "__main__":
    sys.exit(main())
