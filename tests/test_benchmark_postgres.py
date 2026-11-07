"""The confirming pass RFC-0003 commits to: arms A and B on real Postgres must match the stored runs, case for case.

The benchmark runs on SQLite, and Milestone 9 showed the two databases can behave differently. This repeats the
deterministic arms' held-out runs on Postgres, as the runtime role, and compares. It's a regression gate too (BENCH-13):
a change that moves a deterministic result fails here. Without the TEST_*_DATABASE_URL settings these are SKIPPED.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from benchmarks.intake import read_split
from evaluations.compare import load_run
from evaluations.journey import Journey
from evaluations.run import read_labels
from evaluations.world import World
from mock_customer_api import db as mock_db
from tests.conftest import ARM_A_TOKEN, ROOT
from tests.pg_stack import MOCK_URL, OWNER_URL, make_pg_arm, needs_postgres

pytestmark = [pytest.mark.postgres, needs_postgres]
STORED = ROOT / "benchmarks" / "results" / "deterministic"


@pytest.mark.parametrize(("arm", "run"), [("A", "a-heldout"), ("B", "b-heldout")])
def test_postgres_matches_the_stored_held_out_run_case_for_case(generated: Path, arm: str, run: str) -> None:
    pg, owner = make_pg_arm(generated)
    with owner.begin() as connection:
        connection.execute(text("SELECT 1"))
    assert OWNER_URL.startswith("postgresql")
    dataset = generated / "benchmarks/datasets/v1"
    labels = read_labels("heldout", dataset)
    stored = {r.case_id: r for r in load_run(STORED / run).results}
    mock_client: TestClient = pg.mock_client
    world = World(
        pg.sessions,
        pg.sessions.kw["bind"],
        mock_db.make_engine(MOCK_URL),
        mock_client,
        ARM_A_TOKEN,
        secrets.token_urlsafe(32),
    )
    differences = []
    with pg.sessions() as s:
        journey = Journey(world, s, arm)
        for item in read_split("heldout", dataset):
            result = journey.run(item, labels[item.case_id], 1, "deterministic")
            mine = (result.first_action, result.outcome, dict(result.final_points), result.duplicate_credits)
            theirs = stored[item.case_id]
            wanted = (theirs.first_action, theirs.outcome, dict(theirs.final_points), theirs.duplicate_credits)
            if mine != wanted:
                differences.append(f"{item.case_id}: Postgres {mine}, stored {wanted}")
    owner.dispose()
    assert differences == []
