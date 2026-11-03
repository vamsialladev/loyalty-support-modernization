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


# ---------- arm A (Milestone 5): a seeded mock customer API and a fresh app database per test ----------

ARM_A_TOKEN = "arm-a-test-token-0001"


@pytest.fixture(scope="session")
def mock_template(generated: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The mock customer API's SQLite database, migrated and seeded once; each test gets its own copy."""
    from alembic import command
    from alembic.config import Config

    from mock_customer_api import db
    from mock_customer_api.seed import seed

    path = tmp_path_factory.mktemp("arm-a-mock") / "mock.db"
    url = f"sqlite:///{path.as_posix()}"
    cfg = Config(str(ROOT / "mock_customer_api/alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = db.make_engine(url)
    seed(db.make_sessions(engine), generated / "seed_data/v1")
    engine.dispose()
    labels = {
        row["case_id"]: row
        for split in ("dev", "validation", "heldout", "stress")
        for row in read_jsonl(generated / "benchmarks/datasets/v1/labels" / f"{split}.jsonl")
    }
    return {"path": path, "labels": labels, "datasets": generated / "benchmarks/datasets/v1"}
