"""Shared fixtures. Full generation runs once per test session (it takes a while on slow machines)."""

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="session")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A full default generation (seed 20261102, scale 1.0) in a temp folder, plus its label-review sheet."""
    from seed_data.generator import DEFAULT_SEED
    from seed_data.generator.generate import generate
    from seed_data.generator.review_sheet import write_sheet

    root = tmp_path_factory.mktemp("gen")
    generate(DEFAULT_SEED, 1.0, root)
    write_sheet(root / "benchmarks/datasets/v1", root / "evaluations/label-review/review-sheet.csv", DEFAULT_SEED)
    return root
