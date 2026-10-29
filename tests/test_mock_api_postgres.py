"""Real-PostgreSQL integration tests (spec D): idempotency atomicity, concurrent duplicates, conflicts, full seed.

They need TEST_MOCK_API_DATABASE_URL (the compose check points it at the throwaway stack's mock_customer_api_test
database). Without it they are SKIPPED with that reason; they never silently pass.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.domain.customer_records import AdjustmentRequest
from app.ports.customer_systems import UncertainOutcome
from customer_shapes import CustomerShape
from mock_customer_api import db, service
from mock_customer_api.api import create_app
from mock_customer_api.seed import seed
from mock_customer_api.service import Problem
from mock_customer_api.settings import Settings
from tests.conftest import ROOT, read_jsonl

URL = os.environ.get("TEST_MOCK_API_DATABASE_URL", "")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not URL.startswith("postgresql"), reason="TEST_MOCK_API_DATABASE_URL is not set to PostgreSQL"),
]
TOKEN = "pg-test-token"


@pytest.fixture(scope="module")
def pg(generated: Path) -> dict[str, Any]:
    cfg = Config(str(ROOT / "mock_customer_api/alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = db.make_engine(URL)
    factory = db.make_sessions(engine)
    counts = seed(factory, generated / "seed_data/v1")
    k01 = next(
        lab
        for lab in read_jsonl(generated / "benchmarks/datasets/v1/labels/heldout.jsonl")
        if lab["scenarios"] == ["K01"]
    )
    return {
        "engine": engine,
        "factory": factory,
        "counts": counts,
        "root": generated,
        "member": k01["facts"]["claimant"],
        "stay": k01["stays"][0]["stay_id"],
    }


def body(pg: dict[str, Any], points: int = 700) -> dict[str, Any]:
    return {
        "member_number": pg["member"],
        "stay_id": pg["stay"],
        "points": points,
        "reason_code": "missing_points",
        "requested_by": "agent-1",
        "note": None,
    }


def rows(pg: dict[str, Any], key: str) -> tuple[int, int, int]:
    with pg["engine"].connect() as conn:
        idem = conn.execute(text("select count(*) from idempotency_records where key = :k"), {"k": key}).scalar_one()
        adj = conn.execute(text("select count(*) from adjustments where idempotency_key = :k"), {"k": key}).scalar_one()
        led = conn.execute(
            text(
                "select count(*) from ledger_entries le join adjustments a on a.ledger_entry_id = "
                "le.entry_id where a.idempotency_key = :k"
            ),
            {"k": key},
        ).scalar_one()
    return idem, adj, led


def test_full_seed_matches_the_manifest(pg: dict[str, Any]) -> None:
    manifest = json.loads((pg["root"] / "benchmarks/datasets/v1/manifest.json").read_text(encoding="utf-8"))
    assert pg["counts"]["members"] == manifest["counts"]["members"]
    assert pg["counts"]["stays"] == manifest["counts"]["stay_records"]
    assert pg["counts"]["ledger_entries"] == manifest["counts"]["ledger_entries"]


def test_failure_before_commit_writes_nothing(pg: dict[str, Any]) -> None:
    with pytest.raises(Problem):
        service.submit_adjustment(
            pg["factory"], "pg-crash-1", body(pg), "2026-10-01T00:00:00Z", crash_before_commit=True
        )
    assert rows(pg, "pg-crash-1") == (0, 0, 0)


def test_twenty_concurrent_requests_with_one_key_apply_once(pg: dict[str, Any]) -> None:
    results: list[tuple[int, dict[str, Any], bool]] = []
    errors: list[BaseException] = []
    start = threading.Barrier(20)

    def worker() -> None:
        try:
            start.wait()
            results.append(service.submit_adjustment(pg["factory"], "pg-race-1", body(pg), "2026-10-01T00:00:00Z"))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len({r[1]["adjustment_id"] for r in results}) == 1
    assert sum(1 for r in results if not r[2]) == 1  # exactly one request applied; the other 19 replayed
    assert rows(pg, "pg-race-1") == (1, 1, 1)


def test_same_key_different_body_is_a_conflict(pg: dict[str, Any]) -> None:
    service.submit_adjustment(pg["factory"], "pg-conflict-1", body(pg, 100), "2026-10-01T00:00:00Z")
    with pytest.raises(Problem) as err:
        service.submit_adjustment(pg["factory"], "pg-conflict-1", body(pg, 200), "2026-10-01T00:00:00Z")
    assert err.value.status == 409
    assert rows(pg, "pg-conflict-1") == (1, 1, 1)


def test_different_keys_for_one_stay_both_apply(pg: dict[str, Any]) -> None:
    # The platform enforces only the idempotency key, as a real one might; stopping two cases from crediting one
    # stay is the app's job (Milestone 6). This is what lets the "A as-is" variant double-credit (ADR-0018).
    a = service.submit_adjustment(pg["factory"], "pg-twokeys-a", body(pg, 50), "2026-10-01T00:00:00Z")
    b = service.submit_adjustment(pg["factory"], "pg-twokeys-b", body(pg, 50), "2026-10-01T00:00:00Z")
    assert a[1]["adjustment_id"] != b[1]["adjustment_id"]


def test_commit_then_lost_over_http_on_postgres(pg: dict[str, Any]) -> None:
    settings = Settings(database_url=URL, token=TOKEN, faults_enabled=True)
    client = TestClient(create_app(settings, pg["engine"]), base_url="http://mock")
    shape = CustomerShape.load("hg-demo")
    req = AdjustmentRequest(pg["member"], pg["stay"], 900, "missing_points", "agent-1")
    with pytest.raises(UncertainOutcome):
        MockCustomerApiAdapter("http://mock", TOKEN, shape, client=client, fault="commit_then_lost").submit_adjustment(
            req, "pg-lost-1"
        )
    found = MockCustomerApiAdapter("http://mock", TOKEN, shape, client=client).find_adjustment("pg-lost-1")
    assert found is not None and rows(pg, "pg-lost-1") == (1, 1, 1)
