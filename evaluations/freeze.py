"""The freeze: what's fixed before any held-out run (spec E.1, F9; RFC-0003; BENCH-13).

    uv run python -m evaluations.freeze --write      # once, when dev and validation are done; then commit the file

It records a hash of everything that could change an arm's behaviour, and the 10 cases for the variability repeat,
chosen by a fixed seed from case IDs alone. `evaluations.run` refuses a held-out run if anything has changed since.
Scoring and reporting aren't frozen, on purpose: raw records are kept, so a corrected metric re-scores the same runs,
and never touches an arm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import yaml

from evaluations.run_config import ROOT

FREEZE = ROOT / "benchmarks" / "configs" / "freeze.yaml"
FROZEN_FOLDERS = (
    "app",
    "config",
    "policies",
    "mock_customer_api",
    "customer_shapes",
    "benchmarks/agents",
    "benchmarks/configs",
)
FROZEN_FILES = (
    "benchmarks/benchmark-thresholds.yaml",
    "benchmarks/intake.py",
    "evaluations/journey.py",
    "evaluations/live_model.py",
    "evaluations/member.py",
    "evaluations/run.py",
    "evaluations/world.py",
)
SUFFIXES = (".py", ".yaml", ".yml", ".md", ".toml", ".json")
VARIABILITY_SEED = 9
VARIABILITY_CASES = 10


def _sha256(path: Path) -> str:
    """Line endings don't count: the same text must hash the same on Windows and on CI."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def frozen_hashes(root: Path = ROOT) -> dict[str, str]:
    files = [root / name for name in FROZEN_FILES]
    for folder in FROZEN_FOLDERS:
        files += [path for path in (root / folder).rglob("*") if path.is_file() and path.suffix in SUFFIXES]
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(files)
        if path != root / "benchmarks/configs/freeze.yaml" and "__pycache__" not in path.parts
    }


def variability_cases(dataset: Path) -> list[str]:
    """From case IDs alone, so nobody can pick the easy ones."""
    lines = (dataset / "heldout.jsonl").read_text(encoding="utf-8").splitlines()
    ids = sorted(json.loads(line)["case_id"] for line in lines if line.strip())
    return sorted(random.Random(VARIABILITY_SEED).sample(ids, VARIABILITY_CASES))  # noqa: S311 - a fixed seed, not security


def changes_since_freeze(path: Path = FREEZE, root: Path = ROOT) -> list[str]:
    """What differs from the freeze. Empty means a held-out run may start."""
    if not path.exists():
        return ["no freeze has been committed"]
    frozen: dict[str, str] = yaml.safe_load(path.read_text(encoding="utf-8"))["files"]
    current = frozen_hashes(root)
    return sorted(name for name in set(frozen) | set(current) if frozen.get(name) != current.get(name))


def write_freeze(dataset: Path, path: Path = FREEZE) -> None:
    document = {
        "purpose": "Fixed before any held-out run. SYNTHETIC data. Changing any of these files makes a new experiment.",
        "variability_cases": variability_cases(dataset),
        "files": frozen_hashes(),
    }
    path.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.freeze")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        write_freeze(ROOT / "benchmarks" / "datasets" / "v1")
    changed = changes_since_freeze()
    print("frozen, and nothing has changed" if not changed else f"changed since the freeze: {changed[:10]}")
    return 0 if not changed else 1


if __name__ == "__main__":
    sys.exit(main())
