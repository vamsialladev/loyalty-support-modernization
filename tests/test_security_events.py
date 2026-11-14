"""Security events (SEC-20, ENT-31): classified from the audit tables, minimal content, readers limited, a SIEM-ready
export with a documented field map, and retention that only the owner role can apply."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.roles import NotPermitted
from app.main import create_app
from app.persistence.models import SystemEvent
from app.services import cases as svc
from app.services import kill_switch, security_events
from app.services.instrumentation import record
from app.settings import AppSettings
from tests.arm_a import ArmA, Browser, make_arm_a
from tests.conftest import ROOT
from tests.test_api import Api

TYPED_AS_USERNAME = "correct-horse-battery-staple-pw"  # a password typed into the username box


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def _client(arm: ArmA) -> TestClient:
    return TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory()))


def _make_events(arm: ArmA) -> None:
    # A failed sign-in, with a password typed where the username goes.
    client = _client(arm)
    page = client.get("/login")
    token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
    assert token is not None
    client.post("/login", data={"username": TYPED_AS_USERNAME, "password": "x", "login_csrf": token.group(1)})
    # A denied page and a refused API write without its CSRF header.
    agent = Browser(_client(arm))
    agent.login("agent.ana", arm.password, "Points queue")
    assert agent.get("/metrics").status_code == 403
    api = Api(arm, "agent.ana")
    request = {"received_at_utc": "2026-07-01T10:00:00Z", "contact_channel": "email", "text": "Points."}
    assert api.post("/cases", request, csrf="wrong").status_code == 403
    with arm.sessions() as s:
        kill_switch.set_engaged(s, arm.who("admin.ada"), True, "Testing the security event export.")
        case = svc.create_case(
            s, arm.who("agent.ana"), svc.IntakeRequest("2026-07-01T10:00:00Z", "email", "Points."), arm="C"
        )
        record(s, case, arm.who("agent.ana"), "ai_run_finished", run=1, stop="budget_exhausted", turns=2, mock=True)
        s.commit()


def test_security_events_are_classified_from_what_the_app_already_records(arm: ArmA) -> None:
    _make_events(arm)
    with arm.sessions() as s:
        found = security_events.events(s, arm.who("auditor.abe"))
    by_action = {e.action: e for e in found}
    assert {
        "sign_in_failed",
        "authorization_denied",
        "csrf_failed",
        "kill_switch_changed",
        "ai_budget_exhausted",
    } <= set(by_action)
    assert (by_action["sign_in_failed"].category, by_action["sign_in_failed"].outcome) == ("authentication", "failure")
    assert by_action["authorization_denied"].detail == {"path": "/metrics", "method": "GET"}
    assert by_action["csrf_failed"].actor == "agent.ana" and by_action["csrf_failed"].category == "access"
    assert by_action["kill_switch_changed"].severity == 4 and by_action["kill_switch_changed"].actor == "admin.ada"
    assert by_action["ai_budget_exhausted"].case_reference is not None
    assert "case_created" not in by_action  # ordinary work isn't a security event


def test_no_event_or_export_holds_a_password_or_reason_text(arm: ArmA) -> None:
    _make_events(arm)
    with arm.sessions() as s:
        text = "".join(security_events.jsonl(security_events.events(s, arm.who("auditor.abe"))))
    assert TYPED_AS_USERNAME not in text
    assert "Testing the security event export" not in text  # the kill switch's reason stays in the audit row only
    assert arm.password not in text


def test_only_administrators_and_auditors_read_them(arm: ArmA) -> None:
    with arm.sessions() as s:
        for user in ("agent.ana", "supervisor.sam"):
            with pytest.raises(NotPermitted):
                security_events.events(s, arm.who(user))
    assert Api(arm, "supervisor.sam").get("/security/events").status_code == 403
    listed = Api(arm, "auditor.abe").get("/security/events")
    assert listed.status_code == 200 and isinstance(listed.json(), list)


def test_the_export_is_ecs_shaped_json_lines(arm: ArmA) -> None:
    _make_events(arm)
    with arm.sessions() as s:
        lines = list(security_events.jsonl(security_events.events(s, arm.who("admin.ada"))))
    docs = [json.loads(line) for line in lines]
    assert docs and all(line.endswith("\n") for line in lines)
    for doc in docs:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T[\d:.]+Z", doc["@timestamp"])
        assert doc["event"]["kind"] == "event" and isinstance(doc["event"]["category"], list)
        assert doc["event"]["outcome"] in {"success", "failure", "unknown"}
        assert doc["labels"]["synthetic"] == "true" and doc["user"]["name"]
    field_map = (ROOT / "docs/siem-field-map.md").read_text(encoding="utf-8")
    for name in ("@timestamp", "event.category", "event.action", "event.outcome", "event.severity", "user.name"):
        assert f"`{name}`" in field_map, name


def test_every_classified_action_is_really_recorded_somewhere() -> None:
    """No classification for an event the app never writes: that would claim coverage we don't have."""
    source = "\n".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py") if p.name != "security_events.py"
    )
    built = {
        "ai_budget_exhausted": '"ai_run_finished"',  # ai_run_finished with stop=budget_exhausted
        "adjustment_approved": 'f"adjustment_{decision}"',  # the write path's decision event
        "adjustment_rejected": 'f"adjustment_{decision}"',
    }
    missing = [a for a in security_events.KINDS if built.get(a, f'"{a}"') not in source]
    assert missing == []


def test_retention_deletes_only_old_refusals_and_keeps_the_audit_record(arm: ArmA) -> None:
    old, recent = "2025-01-01T00:00:00.000Z", "2026-11-01T00:00:00.000Z"
    with arm.sessions() as s:
        for action, at in (
            ("sign_in_failed", old),
            ("authorization_denied", old),
            ("sign_in_failed", recent),
            ("kill_switch_changed", old),
            ("api_token_revoked", old),
        ):
            s.add(SystemEvent(actor="system-test", actor_kind="system", action=action, detail={}, at_utc=at))
        s.commit()
        with pytest.raises(ValueError):
            security_events.purge(s, 7)
        assert security_events.purge(s, 400, now=datetime(2026, 11, 14, tzinfo=UTC)) == 2
        left = sorted((e.action, e.at_utc) for e in s.query(SystemEvent).filter(SystemEvent.actor == "system-test"))
    assert left == [
        ("api_token_revoked", old),
        ("kill_switch_changed", old),
        ("sign_in_failed", recent),
    ]
