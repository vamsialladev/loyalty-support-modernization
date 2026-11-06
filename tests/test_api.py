"""The JSON API over HTTP (API-01, API-02): the console's permissions, consistent errors, a published contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.persistence.models import AdjustmentRequestRow, Job
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath
from app.settings import AppSettings
from app.worker import Worker
from benchmarks.intake import load_case, read_split
from tests.arm_a import ArmA, Browser, make_arm_a
from tests.conftest import ROOT

CONTRACT = ROOT / "app/api/contracts/openapi-v1.json"


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


class Api:
    def __init__(self, arm: ArmA, user: str | None = None) -> None:
        self.client = TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory()))
        self.csrf = ""
        if user:
            landing = "Configuration" if user.startswith("admin") else "Points queue"
            Browser(self.client).login(user, arm.password, landing)
            self.csrf = self.client.get("/api/v1/me").json()["csrf_token"]

    def get(self, url: str, **params: Any) -> Any:
        return self.client.get(f"/api/v1{url}", params=params)

    def post(self, url: str, body: Any = None, csrf: str | None = None) -> Any:
        headers = {"X-CSRF-Token": self.csrf if csrf is None else csrf}
        return self.client.post(f"/api/v1{url}", json=body, headers=headers)


def drain(arm: ArmA) -> None:
    Worker(arm.sessions, build_handlers(SharedWritePath("hg-demo"), arm.factory())).drain()


def load(arm: ArmA, case_id: str = "DV-001", name: str = "B") -> int:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == case_id)
    with arm.sessions() as s:
        return load_case(s, item, arm=name)[0].id


def is_problem(resp: Any, status: int, code: str) -> None:
    assert resp.status_code == status, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == status and body["code"] == code and body["title"]


def test_the_whole_path_over_the_api(arm: ArmA) -> None:
    agent, supervisor = Api(arm, "agent.ana"), Api(arm, "supervisor.sam")
    created = agent.post(
        "/cases",
        {
            "received_at_utc": "2026-06-18T13:44:00Z",
            "contact_channel": "email",
            "text": "Points are missing. Confirmation BR-6638.\nThanks, Clara Kowalski",
            "sender_email": "clara.kowalski4@example.com",
        },
    )
    assert created.status_code == 201
    case = created.json()
    assert case["reference"].startswith("B-") and case["status"] == "New"

    started = agent.post(f"/cases/{case['id']}/investigation")
    assert started.status_code == 202 and started.json()["status"] == "queued"
    assert agent.get(f"/cases/{case['id']}").json()["investigation"] == "queued"
    drain(arm)
    detail = agent.get(f"/cases/{case['id']}").json()
    assert detail["investigation"] == "none" and detail["status"] == "Investigating"
    rec = detail["recommendation"]
    assert rec["action"] == "adjust" and rec["points_owed"] > 0
    assert detail["evidence"]["stay_id"] == "BR-6638"
    excerpt = agent.client.get(rec["citations"][0]["url"])
    assert excerpt.status_code == 200 and excerpt.json()["text"]
    assert [r["id"] for r in agent.get(f"/cases/{case['id']}/recommendations").json()] == [rec["id"]]

    requested = agent.post(f"/cases/{case['id']}/adjustment-request")
    assert requested.status_code == 201
    adjustment = requested.json()["adjustment"]
    assert adjustment["points"] == rec["points_owed"] and adjustment["status"] == "pending"

    is_problem(agent.post(f"/adjustments/{adjustment['id']}/decision", {"decision": "approve"}), 403, "not_permitted")
    decided = supervisor.post(f"/adjustments/{adjustment['id']}/decision", {"decision": "approve"})
    assert decided.status_code == 200 and decided.json()["status"] == "approved"
    assert supervisor.post(f"/adjustments/{adjustment['id']}/execution").status_code == 202
    drain(arm)
    final = agent.get(f"/adjustments/{adjustment['id']}").json()
    assert (
        final["status"] == "executed" and final["upstream_adjustment_id"] and final["approved_by"] == "supervisor.sam"
    )
    assert agent.get(f"/cases/{case['id']}").json()["status"] == "Resolved"
    actions = [e["action"] for e in agent.get(f"/cases/{case['id']}/audit").json()]
    assert actions[0] == "case_created" and "adjustment_approved" in actions
    assert any("execut" in a or a == "adjustment_applied" for a in actions), actions


def test_a_second_start_returns_the_same_job(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    cid = load(arm)
    first = agent.post(f"/cases/{cid}/investigation").json()
    second = agent.post(f"/cases/{cid}/investigation").json()
    assert first["job_id"] == second["job_id"]
    with arm.sessions() as s:
        assert len(list(s.scalars(select(Job).where(Job.case_id == cid)))) == 1


def test_an_investigation_on_arm_a_is_refused(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    is_problem(agent.post(f"/cases/{load(arm, name='A')}/investigation"), 409, "not_possible")


def test_no_amount_can_be_sent(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    cid = load(arm)
    agent.post(f"/cases/{cid}/investigation")
    drain(arm)
    owed = agent.get(f"/cases/{cid}").json()["recommendation"]["points_owed"]
    agent.post(f"/cases/{cid}/adjustment-request", {"points": 999999})
    with arm.sessions() as s:
        rows = list(s.scalars(select(AdjustmentRequestRow)))
    assert [r.points for r in rows] == [owed]


def test_a_body_with_unknown_fields_is_refused(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    body = {
        "received_at_utc": "2026-06-18T13:44:00Z",
        "contact_channel": "email",
        "text": "Points.",
        "status": "Resolved",
    }
    resp = agent.post("/cases", body)
    is_problem(resp, 422, "invalid_request")
    assert "status" in resp.json()["detail"]


@pytest.mark.parametrize(
    "bad",
    [
        {"received_at_utc": "yesterday", "contact_channel": "email", "text": "x"},
        {"received_at_utc": "2026-06-18T13:44:00Z", "contact_channel": "carrier pigeon", "text": "x"},
        {"received_at_utc": "2026-06-18T13:44:00Z", "contact_channel": "email", "text": ""},
        {"received_at_utc": "2026-06-18T13:44:00Z", "contact_channel": "email", "text": "x", "arm": "Z"},
    ],
)
def test_bad_input_is_a_problem_document(arm: ArmA, bad: dict[str, str]) -> None:
    is_problem(Api(arm, "agent.ana").post("/cases", bad), 422, "invalid_request")


def test_a_body_that_isnt_json_is_a_problem_document(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    resp = agent.client.post(
        "/api/v1/cases", content=b"not json", headers={"X-CSRF-Token": agent.csrf, "Content-Type": "application/json"}
    )
    is_problem(resp, 422, "invalid_request")


def test_every_route_needs_a_session(arm: ArmA) -> None:
    anonymous = Api(arm)
    for url in (
        "/me",
        "/cases",
        "/cases/1",
        "/cases/1/audit",
        "/cases/1/recommendations",
        "/adjustments/1",
        "/metrics",
    ):
        is_problem(anonymous.get(url), 401, "not_signed_in")
    is_problem(anonymous.post("/cases", {}, csrf="x"), 401, "not_signed_in")


def test_changes_need_the_csrf_header(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    cid = load(arm)
    is_problem(agent.post(f"/cases/{cid}/investigation", csrf=""), 403, "csrf_failed")
    is_problem(agent.post(f"/cases/{cid}/investigation", csrf="wrong"), 403, "csrf_failed")
    with arm.sessions() as s:
        assert list(s.scalars(select(Job))) == []


def test_roles_are_the_same_as_on_the_console(arm: ArmA) -> None:
    cid = load(arm)
    auditor, admin = Api(arm, "auditor.abe"), Api(arm, "admin.ada")
    assert auditor.get(f"/cases/{cid}").status_code == 200
    is_problem(auditor.post(f"/cases/{cid}/investigation"), 403, "not_permitted")
    is_problem(admin.get("/cases"), 403, "not_permitted")
    is_problem(admin.get(f"/cases/{cid}"), 403, "not_permitted")
    assert admin.get("/metrics").status_code == 200
    is_problem(Api(arm, "agent.ana").get("/metrics"), 403, "not_permitted")


def test_missing_things_are_404_problems(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    is_problem(agent.get("/cases/99999"), 404, "not_found")
    is_problem(agent.get("/policies/none/v1/1"), 404, "not_found")
    is_problem(agent.get("/nothing-here"), 404, "not_found")


def test_paging_covers_every_case_once(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    expected = sorted(load(arm, f"DV-00{n}") for n in range(1, 8))
    seen: list[int] = []
    page = agent.get("/cases", limit=3).json()
    while True:
        seen += [c["id"] for c in page["items"]]
        if page["next_cursor"] is None:
            break
        page = agent.get("/cases", limit=3, cursor=page["next_cursor"]).json()
    assert sorted(seen) == expected and len(seen) == len(set(seen))
    assert agent.get("/cases", arm="A").json()["items"] == []
    is_problem(agent.get("/cases", cursor="%%%"), 400, "invalid_cursor")
    is_problem(agent.get("/cases", limit=1000), 422, "invalid_request")


def test_supplying_information_and_feedback(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    cid = load(arm)
    agent.post(f"/cases/{cid}/investigation")
    drain(arm)
    is_problem(agent.post(f"/cases/{cid}/information", {"booking_channel": "x"}), 422, "invalid_request")
    is_problem(agent.post(f"/cases/{cid}/information", {}), 409, "not_possible")
    assert agent.post(f"/cases/{cid}/information", {"reply_text": "It was direct."}).status_code == 202
    drain(arm)
    assert agent.post(f"/cases/{cid}/feedback", {"rating": "helpful"}).json()["kind"] == "feedback"
    is_problem(agent.post(f"/cases/{cid}/feedback", {"rating": "meh"}), 422, "invalid_request")


def test_closing_against_the_engine_needs_a_reason(arm: ArmA) -> None:
    agent = Api(arm, "agent.ana")
    cid = load(arm)
    agent.post(f"/cases/{cid}/investigation")
    drain(arm)
    is_problem(agent.post(f"/cases/{cid}/closure", {"code": "deny_other"}), 409, "not_possible")
    closed = agent.post(f"/cases/{cid}/closure", {"code": "deny_other", "reason": "The member withdrew this by phone."})
    assert closed.json() == {"status": "Resolved", "override": True}


def test_the_published_contract_matches_the_service(arm: ArmA) -> None:
    current = Api(arm).client.get("/api/v1/openapi.json").json()
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert current == committed, "contract drift: run python -m app.api.contract --write"
    paths = current["paths"]
    for route in (
        "/api/v1/cases",
        "/api/v1/cases/{case_id}",
        "/api/v1/cases/{case_id}/investigation",
        "/api/v1/cases/{case_id}/information",
        "/api/v1/cases/{case_id}/recommendations",
        "/api/v1/adjustments/{request_id}/decision",
        "/api/v1/adjustments/{request_id}/execution",
        "/api/v1/adjustments/{request_id}",
        "/api/v1/cases/{case_id}/audit",
        "/api/v1/metrics",
        "/api/v1/cases/{case_id}/feedback",
    ):
        assert route in paths, route
    assert not [p for p in paths if not p.startswith("/api/v1")]


def test_no_request_body_can_carry_an_amount() -> None:
    schemas = json.loads(CONTRACT.read_text(encoding="utf-8"))["components"]["schemas"]
    for name in ("CaseCreate", "InformationSupplied", "Decision", "CloseCase", "FeedbackGiven"):
        assert schemas[name]["additionalProperties"] is False, name
        assert "points" not in schemas[name]["properties"], name
