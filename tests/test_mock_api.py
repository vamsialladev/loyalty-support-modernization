"""Contract tests for the mock customer API and the app's adapter (spec B.3, D). In-process, SQLite, no Docker.

The database is created by the real Alembic migration and seeded from a fresh generation, so these tests also check
the migration and the seed. Real-PostgreSQL behaviour (concurrency, atomicity) is in test_mock_api_postgres.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.domain.customer_records import AdjustmentRequest, Member, StayRecord
from app.ports.customer_systems import (
    AuthenticationFailed,
    IdempotencyConflict,
    MalformedResponse,
    PartialResult,
    RateLimited,
    RecordNotFound,
    RequestRejected,
    SchemaMismatch,
    TemporarilyUnavailable,
    UncertainOutcome,
    UpstreamTimeout,
)
from customer_shapes import CustomerShape, ShapeError
from mock_customer_api import db, service
from mock_customer_api.api import ENTITY_TABLES, create_app, export_contract, output_model
from mock_customer_api.faults import FaultBook
from mock_customer_api.seed import seed
from mock_customer_api.settings import Settings
from tests.conftest import ROOT, read_jsonl

TOKEN = "contract-test-token"
SHAPE = CustomerShape.load("hg-demo")


def migrate(url: str) -> None:
    cfg = Config(str(ROOT / "mock_customer_api/alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def world(generated: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    url = f"sqlite:///{(tmp_path_factory.mktemp('mock') / 'mock.db').as_posix()}"
    migrate(url)
    engine = db.make_engine(url)
    counts = seed(db.make_sessions(engine), generated / "seed_data/v1")
    labels = [
        row
        for s in ("dev", "heldout", "stress")
        for row in read_jsonl(generated / "benchmarks/datasets/v1/labels" / f"{s}.jsonl")
    ]
    return {"url": url, "engine": engine, "counts": counts, "labels": labels, "root": generated}


def case(world: dict[str, Any], scenario: str) -> dict[str, Any]:
    return next(lab for lab in world["labels"] if lab["scenarios"] == [scenario])


def make_client(world: dict[str, Any], **overrides: Any) -> TestClient:
    options: dict[str, Any] = {"faults_enabled": True, "sim_clock_enabled": True, "timeout_fault_seconds": 0.01}
    settings = Settings(database_url=world["url"], token=TOKEN, **{**options, **overrides})
    return TestClient(create_app(settings, world["engine"]), base_url="http://mock")


@pytest.fixture
def client(world: dict[str, Any]) -> TestClient:
    return make_client(world)


def adapter(client: httpx.Client, **kw: Any) -> MockCustomerApiAdapter:
    sleeps: list[float] = []
    ad = MockCustomerApiAdapter("http://mock", TOKEN, SHAPE, client=client, sleep=sleeps.append, **kw)
    ad.sleeps = sleeps  # type: ignore[attr-defined]
    return ad


AUTH = {"Authorization": f"Bearer {TOKEN}"}


# ---------- schema, migration, contract ----------


def test_seed_loads_the_whole_world(world: dict[str, Any]) -> None:
    manifest = json.loads((world["root"] / "benchmarks/datasets/v1/manifest.json").read_text(encoding="utf-8"))
    assert world["counts"]["members"] == manifest["counts"]["members"]
    assert world["counts"]["stays"] == manifest["counts"]["stay_records"]
    assert world["counts"]["ledger_entries"] == manifest["counts"]["ledger_entries"]
    assert world["counts"]["posting_queue"] == manifest["counts"]["posting_queue_items"]


def test_migration_matches_the_table_definitions(world: dict[str, Any]) -> None:
    inspector = inspect(world["engine"])
    for table in db.Base.metadata.sorted_tables:
        migrated = {c["name"]: c["nullable"] for c in inspector.get_columns(table.name)}
        defined = {c.name: c.nullable for c in table.columns}
        assert migrated == defined, table.name


def test_committed_contract_matches_the_service() -> None:
    committed = (ROOT / "mock_customer_api/contracts/openapi-v1.json").read_text(encoding="utf-8")
    assert export_contract() == committed, "contract drift: run python -m mock_customer_api.contract --write"


def test_contract_uses_the_customers_field_names() -> None:
    schemas = json.loads(export_contract())["components"]["schemas"]
    for entity in ENTITY_TABLES:
        name = "".join(part.title() for part in entity.split("_"))
        assert set(schemas[name]["properties"]) == set(SHAPE.upstream_names(entity).values()), entity


def test_responses_match_the_contract_models(client: TestClient, world: dict[str, Any]) -> None:
    k01, d06 = case(world, "K01"), case(world, "D06")
    member, stay = k01["facts"]["claimant"], k01["stays"][0]["stay_id"]
    checks = [
        ("member", client.get(f"/v1/members/{member}", headers=AUTH).json()),
        *[("stay", s) for s in client.get(f"/v1/stays/{stay}", headers=AUTH).json()["items"]],
        *[
            ("posting_queue_item", q)
            for q in client.get(
                "/v1/posting-queue",
                params={"confirmationNumber": d06["stays"][0]["stay_id"]},
                headers={**AUTH, "X-Sim-Time": d06["facts"]["received_at_utc"]},
            ).json()["items"]
        ],
    ]
    assert len(checks) >= 3
    for entity, body in checks:
        output_model(SHAPE, entity).model_validate(body)


def test_mapping_round_trips_every_entity(world: dict[str, Any]) -> None:
    with db.make_sessions(world["engine"])() as s:
        samples = {
            "member": s.query(db.Member).first(),
            "stay": s.query(db.Stay).first(),
            "ledger_entry": s.query(db.LedgerEntry).first(),
            "posting_queue_item": s.query(db.PostingQueueItem).first(),
        }
    for entity, row in samples.items():
        canonical = {k: v for k, v in service.as_dict(row).items() if k in SHAPE.upstream_names(entity)}
        assert SHAPE.to_canonical(entity, SHAPE.to_upstream(entity, canonical), required=()) == canonical


def test_mapping_rejects_unknown_codes_and_bad_money() -> None:
    with pytest.raises(ShapeError, match="unknown accountStatus"):
        SHAPE.to_canonical("member", {"loyaltyId": "GR-1", "accountStatus": "FROZEN"}, required=())
    with pytest.raises(ShapeError, match="not a dollar amount"):
        SHAPE.to_canonical("stay", {"roomRevenue": "lots"}, required=())


# ---------- reads ----------


def test_adapter_reads_map_to_canonical_records(client: TestClient, world: dict[str, Any]) -> None:
    k01 = case(world, "K01")
    ad = adapter(client)
    member = ad.get_member(k01["facts"]["claimant"])
    assert isinstance(member, Member) and member.member_number == k01["facts"]["claimant"]
    stays = ad.get_stay_records(k01["stays"][0]["stay_id"])
    assert isinstance(stays[0], StayRecord) and isinstance(stays[0].room_revenue_cents, int)
    assert stays[0].room_revenue_cents == k01["facts"]["records"][0]["room_revenue_cents"]


def test_duplicate_stay_records_are_all_returned(client: TestClient, world: dict[str, Any]) -> None:
    d25 = case(world, "D25")
    records = adapter(client).get_stay_records(d25["stays"][0]["stay_id"])
    assert len(records) == 2 and len({r.record_id for r in records}) == 2


def test_member_search_is_exact_like_the_legacy_tool(client: TestClient, world: dict[str, Any]) -> None:
    k01 = case(world, "K01")
    ad = adapter(client)
    member = ad.get_member(k01["facts"]["claimant"])
    assert [m.member_number for m in ad.find_members(email=member.email)] == [member.member_number]
    assert ad.find_members(email=member.email.upper()) == []
    with pytest.raises(RecordNotFound):
        ad.get_member("GR-00000")


def test_ledger_pagination_is_complete(client: TestClient, world: dict[str, Any]) -> None:
    s04 = case(world, "S04")
    member = s04["facts"]["claimant"]
    full = adapter(client).get_ledger(member)
    assert len(full) >= 8
    paged = adapter(client, page_size=3).get_ledger(member)
    assert [e.entry_id for e in paged] == [e.entry_id for e in full]
    assert [e.posted_at_utc for e in full] == sorted(e.posted_at_utc for e in full)


def test_sim_clock_hides_the_future(client: TestClient, world: dict[str, Any]) -> None:
    d06 = case(world, "D06")
    stay = d06["stays"][0]["stay_id"]
    at_claim = adapter(client, sim_time=d06["facts"]["received_at_utc"]).get_pending_postings(stay)
    assert len(at_claim) == 1
    assert adapter(client, sim_time="2027-06-01T00:00:00Z").get_pending_postings(stay) == []
    s04 = case(world, "S04")
    early = adapter(client, sim_time="2025-01-01T00:00:00Z").get_ledger(s04["facts"]["claimant"])
    assert early == []


# ---------- writes and idempotency ----------


def request_for(lab: dict[str, Any], points: int = 500) -> AdjustmentRequest:
    return AdjustmentRequest(lab["facts"]["claimant"], lab["stays"][0]["stay_id"], points, "missing_points", "agent-1")


def test_idempotency_replays_and_rejects_a_changed_body(client: TestClient, world: dict[str, Any]) -> None:
    k01 = case(world, "K01")
    ad = adapter(client)
    first = ad.submit_adjustment(request_for(k01), "idem-replay-1")
    again = ad.submit_adjustment(request_for(k01), "idem-replay-1")
    assert first == again
    with pytest.raises(IdempotencyConflict):
        ad.submit_adjustment(request_for(k01, points=999), "idem-replay-1")
    ledger = [e for e in ad.get_ledger(k01["facts"]["claimant"]) if e.entry_id == first.ledger_entry_id]
    assert len(ledger) == 1


def test_missing_idempotency_key_is_rejected(client: TestClient, world: dict[str, Any]) -> None:
    body = SHAPE.to_upstream(
        "adjustment",
        {"member_number": "GR-1", "stay_id": "BR-1", "points": 1, "reason_code": "x1", "requested_by": "a"},
    )
    resp = client.post("/v1/adjustments", json=body, headers=AUTH)
    assert resp.status_code == 400 and resp.json()["code"] == "idempotency_key_required"
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_merged_account_cannot_be_credited(client: TestClient, world: dict[str, Any]) -> None:
    d02 = case(world, "D02")
    retired = d02["facts"]["merged_profiles"][0]
    req = AdjustmentRequest(retired, d02["stays"][0]["stay_id"], 100, "missing_points", "agent-1")
    with pytest.raises(RequestRejected) as err:
        adapter(client).submit_adjustment(req, "idem-merged-1")
    assert err.value.code == "account_merged"


def test_validation_errors_name_the_field(client: TestClient) -> None:
    body = SHAPE.to_upstream(
        "adjustment",
        {"member_number": "GR-10000", "stay_id": "BR-1000", "points": 0, "reason_code": "x1", "requested_by": "a"},
    )
    resp = client.post("/v1/adjustments", json=body, headers={**AUTH, "Idempotency-Key": "k-validate"})
    assert resp.status_code == 422 and "points" in resp.json()["detail"]


def test_crash_before_commit_leaves_nothing(client: TestClient, world: dict[str, Any]) -> None:
    k01 = case(world, "K01")
    with db.make_sessions(world["engine"])() as s:
        before = service.counts(s)
    with pytest.raises(UncertainOutcome):
        adapter(client, fault="crash_before_commit").submit_adjustment(request_for(k01), "idem-crash-1")
    with db.make_sessions(world["engine"])() as s:
        assert service.counts(s) == before
    assert adapter(client).find_adjustment("idem-crash-1") is None


def test_commit_then_lost_is_uncertain_and_then_found(client: TestClient, world: dict[str, Any]) -> None:
    k01 = case(world, "K01")
    with pytest.raises(UncertainOutcome):
        adapter(client, fault="commit_then_lost").submit_adjustment(request_for(k01), "idem-lost-1")
    found = adapter(client).find_adjustment("idem-lost-1")
    assert found is not None and found.points == 500
    assert adapter(client).submit_adjustment(request_for(k01), "idem-lost-1") == found  # retry replays


def test_duplicate_delivery_applies_once(client: TestClient, world: dict[str, Any]) -> None:
    k01 = case(world, "K01")
    result = adapter(client, fault="duplicate").submit_adjustment(request_for(k01, 321), "idem-dup-1")
    with db.make_sessions(world["engine"])() as s:
        assert s.query(db.Adjustment).filter_by(idempotency_key="idem-dup-1").count() == 1
        assert s.query(db.LedgerEntry).filter_by(entry_id=result.ledger_entry_id).count() == 1


def test_ticket_creation(client: TestClient) -> None:
    ticket = adapter(client).create_ticket(subject="Missing points", body="Stay BR-1000", member_number="GR-10000")
    assert ticket.ticket_id.startswith("TCK-") and ticket.member_number == "GR-10000"


# ---------- injected faults map to typed errors ----------


@pytest.mark.parametrize(
    ("fault", "error"),
    [
        ("auth_failure", AuthenticationFailed),
        ("rate_limited", RateLimited),
        ("unavailable", TemporarilyUnavailable),
        ("malformed", MalformedResponse),
        ("schema_v1_1", SchemaMismatch),
    ],
)
def test_faults_raise_typed_errors(client: TestClient, world: dict[str, Any], fault: str, error: type) -> None:
    ad = adapter(client, fault=fault)
    with pytest.raises(error):
        ad.get_member(case(world, "K01")["facts"]["claimant"])
    if error in (RateLimited, TemporarilyUnavailable):
        assert len(ad.sleeps) == ad.max_retries  # bounded retries, then give up
    else:
        assert ad.sleeps == []  # never retry auth, malformed or schema errors


def test_rate_limit_retry_honours_retry_after(client: TestClient, world: dict[str, Any]) -> None:
    ad = adapter(client, fault="rate_limited")
    with pytest.raises(RateLimited):
        ad.get_member(case(world, "K01")["facts"]["claimant"])
    assert ad.sleeps == [1.0, 1.0]


def test_partial_ledger_is_never_returned_as_complete(client: TestClient, world: dict[str, Any]) -> None:
    with pytest.raises(PartialResult):
        adapter(client, fault="partial", page_size=2).get_ledger(case(world, "S04")["facts"]["claimant"])


def test_timeout_fault_delays_then_answers_server_side(world: dict[str, Any]) -> None:
    import time

    client = make_client(world, timeout_fault_seconds=0.3)
    start = time.perf_counter()
    resp = client.get(
        f"/v1/members/{case(world, 'K01')['facts']['claimant']}", headers={**AUTH, "X-Mock-Fault": "timeout"}
    )
    assert resp.status_code == 200 and time.perf_counter() - start >= 0.3


def test_unknown_fault_and_disabled_switches_are_refused(world: dict[str, Any]) -> None:
    member = case(world, "K01")["facts"]["claimant"]
    resp = make_client(world).get(f"/v1/members/{member}", headers={**AUTH, "X-Mock-Fault": "meteor"})
    assert resp.status_code == 400 and resp.json()["code"] == "unknown_fault"
    plain = TestClient(create_app(Settings(database_url=world["url"], token=TOKEN), world["engine"]))
    assert plain.get(f"/v1/members/{member}", headers={**AUTH, "X-Mock-Fault": "timeout"}).json()["code"] == (
        "faults_disabled"
    )
    assert (
        plain.get(f"/v1/members/{member}", headers={**AUTH, "X-Sim-Time": "2026-01-01T00:00:00Z"}).json()["code"]
        == "sim_clock_disabled"
    )


def test_auth_is_required(client: TestClient, world: dict[str, Any]) -> None:
    member = case(world, "K01")["facts"]["claimant"]
    assert client.get(f"/v1/members/{member}").status_code == 401
    wrong = client.get(f"/v1/members/{member}", headers={"Authorization": "Bearer wrong"})
    assert wrong.status_code == 401 and wrong.headers["content-type"].startswith("application/problem+json")
    with pytest.raises(AuthenticationFailed):
        MockCustomerApiAdapter("http://mock", "wrong", SHAPE, client=client).get_member(member)


def test_seeded_fault_rules_fire_a_limited_number_of_times(tmp_path: Path) -> None:
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules:\n  - fault: unavailable\n    stay_suffix: '43'\n    times: 1\n", encoding="utf-8")
    book = FaultBook.load(True, rules)
    assert book.pick(None, stay="BR-1043") == "unavailable"
    assert book.pick(None, stay="BR-2043") is None  # times: 1
    assert FaultBook.load(False, rules).pick("timeout") is None  # disabled: nothing fires


# ---------- adapter behaviour on the wire (fake transport) ----------


def fake(responses: list[httpx.Response | Exception]) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = responses[min(len(seen) - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://fake"), seen


MEMBER = {
    "loyaltyId": "GR-10000",
    "givenName": "A",
    "familyName": "B",
    "emailAddress": "a@example.com",
    "phoneNumber": "+1 201 555 0100",
    "tierCode": "Gold",
    "accountStatus": "ACTIVE",
}


def test_read_timeout_is_retried_then_raised() -> None:
    client, seen = fake([httpx.ReadTimeout("slow")])
    with pytest.raises(UpstreamTimeout):
        adapter(client).get_member("GR-10000")
    assert len(seen) == 3  # first try + 2 retries


def test_transient_failure_then_success() -> None:
    client, seen = fake([httpx.Response(503, json={"code": "unavailable"}), httpx.Response(200, json=MEMBER)])
    ad = adapter(client)
    assert ad.get_member("GR-10000").tier == "Gold" and len(seen) == 2 and len(ad.sleeps) == 1


def test_write_timeout_is_never_retried() -> None:
    client, seen = fake([httpx.ReadTimeout("slow")])
    with pytest.raises(UncertainOutcome):
        adapter(client).submit_adjustment(AdjustmentRequest("GR-1", "BR-1", 1, "x1", "a"), "k-timeout")
    assert len(seen) == 1


def test_write_429_is_retried_with_the_same_key() -> None:
    result = {
        "adjustmentId": "ADJ-1",
        "idempotencyKey": "k-429",
        "loyaltyId": "GR-1",
        "confirmationNumber": "BR-1",
        "points": 1,
        "adjustmentStatus": "APPLIED",
        "createdTimestampUtc": "2026-01-01T00:00:00Z",
        "transactionId": "L-ADJ-1",
        "reasonCode": "x1",
        "requestedBy": "a",
        "note": None,
    }
    client, seen = fake(
        [
            httpx.Response(429, headers={"Retry-After": "2"}, json={"code": "rate_limited"}),
            httpx.Response(201, json=result),
        ]
    )
    out = adapter(client).submit_adjustment(AdjustmentRequest("GR-1", "BR-1", 1, "x1", "a"), "k-429")
    assert out.adjustment_id == "ADJ-1"
    assert [r.headers["Idempotency-Key"] for r in seen] == ["k-429", "k-429"]


def test_connect_error_on_write_is_safe_to_retry() -> None:
    client, seen = fake([httpx.ConnectError("refused")])
    with pytest.raises(TemporarilyUnavailable):
        adapter(client).submit_adjustment(AdjustmentRequest("GR-1", "BR-1", 1, "x1", "a"), "k-connect")
    assert len(seen) == 3


def test_schema_change_missing_field_and_extra_field() -> None:
    renamed = {("loyalty_id" if k == "loyaltyId" else k): v for k, v in MEMBER.items()}
    client, _ = fake([httpx.Response(200, json=renamed)])
    with pytest.raises(SchemaMismatch, match="loyaltyId"):
        adapter(client).get_member("GR-10000")
    client, _ = fake([httpx.Response(200, json={**MEMBER, "marketingOptIn": True})])
    assert adapter(client).get_member("GR-10000").member_number == "GR-10000"  # extra fields are tolerated


def test_wrong_structure_is_malformed() -> None:
    client, _ = fake([httpx.Response(200, json=["not", "an", "object"])])
    with pytest.raises(MalformedResponse):
        adapter(client).get_member("GR-10000")
    client, _ = fake([httpx.Response(200, json={"no_items": []})])
    with pytest.raises(MalformedResponse):
        adapter(client).find_members(email="a@example.com")


# ---------- health, control, settings ----------


def test_readyz_reports_seeded_and_empty(world: dict[str, Any], tmp_path: Path) -> None:
    assert make_client(world).get("/readyz").status_code == 200
    empty_url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    migrate(empty_url)
    empty = TestClient(create_app(Settings(database_url=empty_url, token=TOKEN), db.make_engine(empty_url)))
    resp = empty.get("/readyz")
    assert resp.status_code == 503 and resp.json()["status"] == "not_seeded"
    assert empty.get("/healthz").json()["status"] == "ok"


def test_control_seed_and_reset(world: dict[str, Any], tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'ctl.db').as_posix()}"
    migrate(url)
    settings = Settings(database_url=url, token=TOKEN, seed_dir=world["root"] / "seed_data/v1")
    ctl = TestClient(create_app(settings, db.make_engine(url)))
    assert ctl.post("/_control/seed", headers=AUTH).json()["counts"]["members"] == world["counts"]["members"]
    assert ctl.post("/_control/seed", headers=AUTH).json()["code"] == "already_seeded"
    assert ctl.post("/_control/reset", headers=AUTH).json()["counts"]["members"] == 0
    demo = Settings(database_url=url, token=TOKEN, public_demo_mode=True)
    assert TestClient(create_app(demo, db.make_engine(url))).post("/_control/reset", headers=AUTH).status_code == 403


def test_settings_refuse_test_switches_in_public_demo() -> None:
    with pytest.raises(ValueError, match="PUBLIC_DEMO_MODE"):
        Settings(database_url="sqlite://", token=TOKEN, public_demo_mode=True, faults_enabled=True)
