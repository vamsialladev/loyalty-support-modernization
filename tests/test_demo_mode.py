"""Public demo mode (spec C.8; SEC-18; ADR-0087): no shared admin, no passwords, a daily cap, mock AI only, a reset
only from inside, and the label on every page."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.adapters.local_demo_identity import ensure_demo_users
from app.main import create_app
from app.persistence.models import Case, CaseEvent, PolicyVersionRow, User
from app.services import demo
from app.services.assisted import runtime_from_settings
from app.settings import AppSettings
from benchmarks.agents.conventional_scripted import ScriptedConventionalAgent
from benchmarks.intake import load_case, read_split
from tests.arm_a import ArmA, make_arm_a


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    built = make_arm_a(mock_template, tmp_path)
    with built.sessions() as s:
        ensure_demo_users(s, built.password, public_demo=True)
    return built


def _client(arm: ArmA, public: bool = True) -> TestClient:
    settings = AppSettings(database_url=arm.app_url, sim_clock=True, public_demo_mode=public)
    return TestClient(create_app(settings, arm.factory()), base_url="https://testserver")  # demo cookies are Secure


def _demo_sign_in(client: TestClient, role: str) -> Any:
    page = client.get("/login")
    token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
    assert token is not None
    return client.post("/demo/sign-in", data={"role": role, "login_csrf": token.group(1)}, follow_redirects=False)


def test_the_public_demo_has_no_administrator_or_auditor(arm: ArmA) -> None:
    with arm.sessions() as s:
        active = {u.username: u.role for u in s.scalars(select(User).where(User.active.is_(True)))}
    assert set(active.values()) == {"agent", "supervisor"}
    assert "admin.ada" not in active and "auditor.abe" not in active


def test_visitors_sign_in_by_button_and_never_with_a_password(arm: ArmA) -> None:
    client = _client(arm)
    page = client.get("/login")
    assert 'data-testid="demo-agent"' in page.text and 'name="password"' not in page.text
    assert demo.LABEL in page.text
    token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
    assert token is not None
    refused = client.post(
        "/login", data={"username": "agent.ana", "password": arm.password, "login_csrf": token.group(1)}
    )
    assert refused.status_code == 409 and "buttons" in refused.text
    signed = _demo_sign_in(client, "agent")
    assert signed.status_code == 303 and signed.headers["location"] == "/queue"
    queue = client.get("/queue")
    assert queue.status_code == 200 and demo.LABEL in queue.text


def test_there_is_no_way_to_sign_in_as_anything_but_agent_or_supervisor(arm: ArmA) -> None:
    for role in ("admin", "administrator", "auditor", "agent.ana"):
        assert _demo_sign_in(_client(arm), role).status_code == 404
    assert _demo_sign_in(_client(arm), "supervisor").status_code == 303
    assert _demo_sign_in(_client(arm, public=False), "agent").status_code == 404  # off outside the demo


def test_the_daily_case_cap_answers_503_with_retry_after(arm: ArmA, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MAX_CASES_PER_DAY", "1")
    client = _client(arm)
    _demo_sign_in(client, "agent")
    csrf = client.get("/api/v1/me").json()["csrf_token"]
    body = {"received_at_utc": "2026-07-01T10:00:00Z", "contact_channel": "email", "text": "Points.", "arm": "B"}
    first = client.post("/api/v1/cases", json=body, headers={"X-CSRF-Token": csrf})
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/cases", json=body, headers={"X-CSRF-Token": csrf})
    assert second.status_code == 503 and second.json()["code"] == "demo_limit"
    assert int(second.headers["Retry-After"]) > 0


def test_the_demo_runs_mock_ai_whatever_the_settings_say() -> None:
    settings = AppSettings(
        database_url="sqlite://",
        public_demo_mode=True,
        ai_provider="anthropic",
        feature_live_ai=True,
        anthropic_model="claude-haiku-5-5",
    )
    runtime = runtime_from_settings(settings)
    assert runtime.provider is not None and runtime.provider.is_mock


def test_the_reset_empties_cases_and_keeps_accounts_and_policies(arm: ArmA) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    with arm.sessions() as s:
        case = load_case(s, item, arm="B")[0]
        ScriptedConventionalAgent(s, arm.factory()).run(case)
        before = (s.scalar(select(func.count(Case.id))), s.scalar(select(func.count(CaseEvent.id))))
        users = s.scalar(select(func.count(User.id)))
        policies = s.scalar(select(func.count(PolicyVersionRow.id)))
        assert before[0] and before[1]
        removed = demo.reset(s)
        after = (s.scalar(select(func.count(Case.id))), s.scalar(select(func.count(CaseEvent.id))))
        assert removed == before[0] and after == (0, 0)
        assert s.scalar(select(func.count(User.id))) == users
        assert s.scalar(select(func.count(PolicyVersionRow.id))) == policies


def test_no_route_resets_the_demo() -> None:
    root = Path(__file__).resolve().parent.parent
    for path in (root / "app" / "web").rglob("*.py"):
        assert "demo.reset" not in path.read_text(encoding="utf-8"), path
    assert "demo.reset" not in (root / "app" / "api" / "router.py").read_text(encoding="utf-8")
