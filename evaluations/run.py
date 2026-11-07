"""One command runs a benchmark (spec E.3, Appendix B; BENCH-03). It stores what happened, and decides nothing.

    uv run python -m evaluations.run --arm b --split dev --provider none

Results go to `benchmarks/results/<deterministic|mock|live>/<run name>/`: `results.jsonl`, one record per case, and
`manifest.json`, with the versions that produced them. Raw records are kept, so a corrected metric can re-score old runs
without spending anything. **The held-out split needs `--confirm-frozen`, and a clean tree.** Live runs aren't here yet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks.intake import DatasetCase, read_split
from evaluations.journey import Journey
from evaluations.run_config import ROOT, RunConfig, load
from evaluations.scoring import CaseResult
from evaluations.world import make_world, seed_template

DATASET = ROOT / "benchmarks" / "datasets" / "v1"
SEED_DATA = ROOT / "seed_data" / "v1"
RESULTS = ROOT / "benchmarks" / "results"
CONFIG_BY_ARM = {"a": "arm-a", "a-as-is": "arm-a-as-is", "b": "arm-b", "c-mock": "arm-c-mock", "c-live": "arm-c-live"}
SYNTHETIC = "SYNTHETIC data. Scripted agents and a simulated member and supervisor: not human timing, not real people."


class RunRefused(Exception):
    pass


def read_labels(split: str, dataset_dir: Path = DATASET) -> dict[str, dict[str, Any]]:
    """Evaluator only: `tests/test_generator.py` keeps this out of the app."""
    lines = (dataset_dir / "labels" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
    return {row["case_id"]: row for row in (json.loads(line) for line in lines if line.strip())}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603, S607


def tree_status() -> str:
    """What's changed in the code and data. A run's own results don't make the tree dirty."""
    return _git("status", "--porcelain", "--", ".", ":!benchmarks/results", ":!benchmarks/reports")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refuse_unless_frozen(split: str, confirm_frozen: bool, tree_status: str) -> None:
    """Never tune on held-out data (spec E.1, F9): that run needs a deliberate flag, and a commit that says what ran."""
    if split != "heldout":
        return
    if not confirm_frozen:
        raise RunRefused("the held-out split needs --confirm-frozen: it's only for a frozen configuration")
    if tree_status.strip():
        raise RunRefused("the held-out split needs a clean working tree, so the commit says exactly what ran")


def run_cases(
    config: RunConfig,
    items: Sequence[DatasetCase],
    labels: dict[str, dict[str, Any]],
    template: Path,
    folder: Path,
    run_number: int = 1,
    *,
    second_look: bool = False,
) -> list[CaseResult]:
    """A fresh world per run: no run can see another's credits."""
    if config.arm not in ("A", "B"):
        raise RunRefused(f"arm {config.arm} isn't wired to the runner yet")
    world = make_world(template, folder)
    try:
        with world.sessions() as s:
            journey = Journey(world, s, config.arm, second_look=second_look)
            return [journey.run(item, labels[item.case_id], run_number, config.kind) for item in items]
    finally:
        world.close()


def write_run(
    name: str,
    config: RunConfig,
    split: str,
    results: Sequence[CaseResult],
    dataset_dir: Path,
    root: Path = RESULTS,
    *,
    second_look: bool = False,
) -> Path:
    folder = root / config.kind / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "results.jsonl").open("w", encoding="utf-8", newline="\n") as out:
        for result in results:
            out.write(json.dumps(asdict(result), sort_keys=True) + "\n")
    manifest = {
        "name": name,
        "kind": config.kind,
        "after_stop": "second look (sensitivity variant)" if second_look else "script as written",
        "label": SYNTHETIC,
        "split": split,
        "cases": len(results),
        "config": asdict(config),
        "dataset_version": config.dataset_version,
        "dataset_sha256": _sha256(dataset_dir / f"{split}.jsonl"),
        "labels_sha256": _sha256(dataset_dir / "labels" / f"{split}.jsonl"),
        "app_commit": _git("rev-parse", "HEAD"),
        "tree_clean": not tree_status(),
        "finished_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.run")
    parser.add_argument("--arm", required=True, choices=sorted(CONFIG_BY_ARM))
    parser.add_argument("--split", required=True, choices=("dev", "validation", "heldout", "stress", "fairness"))
    parser.add_argument("--cases", default="", help="comma-separated case IDs, for a smoke run")
    parser.add_argument("--name", default="", help="the run's folder name")
    parser.add_argument("--confirm-frozen", action="store_true")
    parser.add_argument(
        "--second-look",
        action="store_true",
        help="sensitivity variant: work a case again after the re-check stops its credit (RFC-0003)",
    )
    args = parser.parse_args(argv)

    config = load(CONFIG_BY_ARM[args.arm])
    try:
        refuse_unless_frozen(args.split, args.confirm_frozen, tree_status())
        items = read_split(args.split, DATASET)
        wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
        if wanted:
            items = [item for item in items if item.case_id in wanted]
        labels = read_labels(args.split)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        name = args.name or f"{args.arm}-{args.split}-{stamp}"
        with tempfile.TemporaryDirectory(prefix="benchmark-", ignore_cleanup_errors=True) as tmp:
            folder = Path(tmp)
            template = seed_template(SEED_DATA, folder)
            results = run_cases(config, items, labels, template, folder / "run", second_look=args.second_look)
    except RunRefused as refused:
        print(f"REFUSED: {refused}")
        return 2
    out = write_run(name, config, args.split, results, DATASET, second_look=args.second_look)
    print(f"{config.kind} run: {len(results)} cases, stored in {out.relative_to(ROOT)}. {SYNTHETIC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
