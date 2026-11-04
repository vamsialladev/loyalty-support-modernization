"""The console over HTTP: sign-in, sessions, CSRF, roles from the session only, the banner, security headers and
output escaping (spec B.2, B.10, C.4, C.7; ADR-0045). Requests go through the real routes with TestClient.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.domain.case_states import CaseState
from app.main import create_app
from app.persistence.models import Case, User, UserSession
from app.services import cases as svc
from app.settings import AppSettings
from tests.arm_a import ArmA, Browser, field, make_arm_a
from tests.conftest import ARM_A_TOKEN


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def browser(arm: ArmA, user: str | None = None) -> Browser:
    client = TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory()))
    b = Browser(client)
    if user:
        b.login(user, arm.password)
    return b


def pending_case(arm: ArmA, requester: str) -> tuple[int, int]:
    """DV-001 worked up to 'Pending approval' by `requester`. Returns (case id, adjustment request id)."""
    with arm.sessions() as s:
        (case,) = arm.load(s, "DV-001")
        who, systems = arm.who(requester), arm.systems(case.received_at_utc)
        svc.start_work(s, who, case)
        svc.attach_member(s, who, case, systems, "GR-85640")
        svc.attach_stay(s, who, case, systems, "GR-85640", "BR-6638")
        svc.attach_ledger(s, who, case, systems, "GR-85640", True)
        svc.attach_policy(s, who, case, arm.index, "missing-points-requests#1")
        return case.id, svc.request_adjustment(s, who, case, arm.rules).id


def test_pages_need_a_session(arm: ArmA) -> None:
    b = browser(arm)
    for url in ("/queue", "/cases/1", "/approvals", "/cases/new"):
        resp = b.client.get(url, follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"] == "/login", url


def test_a_wrong_password_or_unknown_user_is_refused_the_same_way(arm: ArmA) -> None:
    b = browser(arm)
    for username, password in (("agent.ana", "wrong-password-123"), ("nobody", arm.password)):
        page = b.client.get("/login")
        token = page.text.split('name="login_csrf" value="')[1].split('"')[0]
        resp = b.client.post("/login", data={"username": username, "password": password, "login_csrf": token})
        assert resp.status_code == 401 and "don't match an active account" in resp.text
        assert "lsm_session" not in b.client.cookies


def test_login_form_needs_its_csrf_cookie(arm: ArmA) -> None:
    b = browser(arm)
    resp = b.client.post("/login", data={"username": "agent.ana", "password": arm.password, "login_csrf": "forged"})
    assert resp.status_code == 403


def test_session_cookie_is_httponly_and_strict(arm: ArmA) -> None:
    b = browser(arm)
    page = b.client.get("/login")
    token = page.text.split('name="login_csrf" value="')[1].split('"')[0]
    resp = b.client.post(
        "/login",
        data={"username": "agent.ana", "password": arm.password, "login_csrf": token},
        follow_redirects=False,
    )
    cookie = resp.headers["set-cookie"].lower()
    assert "lsm_session=" in cookie and "httponly" in cookie and "samesite=strict" in cookie


def test_logout_revokes_the_session_on_the_server(arm: ArmA) -> None:
    b = browser(arm, "agent.ana")
    stolen = b.client.cookies.get("lsm_session")
    assert b.post("/logout").status_code == 200
    thief = browser(arm)
    thief.client.cookies.set("lsm_session", stolen or "")
    assert thief.client.get("/queue", follow_redirects=False).status_code == 303


def test_an_expired_session_or_a_deactivated_account_signs_out(arm: ArmA) -> None:
    b = browser(arm, "agent.ana")
    with arm.sessions() as s:
        s.execute(update(UserSession).values(expires_at_utc="2000-01-01T00:00:00Z"))
        s.commit()
    assert b.client.get("/queue", follow_redirects=False).status_code == 303
    b = browser(arm, "agent.ben")
    with arm.sessions() as s:
        s.execute(update(User).where(User.username == "agent.ben").values(active=False))
        s.commit()
    assert b.client.get("/queue", follow_redirects=False).status_code == 303


@pytest.mark.parametrize("token", ["", "not-the-session-token"])
def test_state_changes_need_the_sessions_csrf_token(arm: ArmA, token: str) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, "DV-001")
    b = browser(arm, "agent.ana")
    resp = b.client.post(f"/cases/{case.id}/start", data={"csrf": token} if token else {})
    assert resp.status_code == 403
    with arm.sessions() as s:
        assert s.get(Case, case.id).status == CaseState.NEW  # type: ignore[union-attr]


def test_requester_sees_no_approve_button_and_a_forged_post_is_refused(arm: ArmA) -> None:
    case_id, request_id = pending_case(arm, "supervisor.sam")
    b = browser(arm, "supervisor.sam")
    page = b.get(f"/cases/{case_id}")
    assert field(page.text, "refusal").startswith("You requested this adjustment")
    assert 'value="approve"' not in page.text
    forged = b.post(f"/adjustments/{request_id}/decide", decision="approve")  # valid CSRF token
    assert forged.status_code == 403 and "another supervisor" in forged.text
    other = browser(arm, "supervisor.sky")
    other.get(f"/cases/{case_id}")
    assert field(other.post(f"/adjustments/{request_id}/decide", decision="approve").text, "case-status") == "Approved"


def test_a_role_in_the_form_is_ignored(arm: ArmA) -> None:
    _case_id, request_id = pending_case(arm, "agent.ana")
    b = browser(arm, "agent.ben")
    resp = b.post(f"/adjustments/{request_id}/decide", decision="approve", role="supervisor", username="supervisor.sky")
    assert resp.status_code == 403 and "only a supervisor" in resp.text


def test_every_page_has_the_banner_and_security_headers(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, "DV-001")
    b = browser(arm, "agent.ana")
    for url in ("/queue", f"/cases/{case.id}", f"/cases/{case.id}/member", "/cases/new", "/approvals"):
        resp = b.get(url)
        assert resp.status_code == 200, url
        assert "SYNTHETIC DATA" in resp.text and "AI mode: none (arm A, legacy)" in resp.text, url
        assert "customer: hg-demo" in resp.text, url
        csp = resp.headers["content-security-policy"]
        assert "script-src 'self'" in csp and "unsafe" not in csp
        assert resp.headers["x-frame-options"] == "DENY" and resp.headers["x-content-type-options"] == "nosniff"
    assert f"simulated time: {case.received_at_utc}" in b.get(f"/cases/{case.id}").text
    login = browser(arm).client.get("/login")
    assert "SYNTHETIC DATA" in login.text


def test_member_text_is_escaped_not_executed(arm: ArmA) -> None:
    b = browser(arm, "agent.ana")
    page = b.get("/cases/new")
    resp = b.post(
        "/cases",
        received_at_utc="2026-07-20T14:00:00Z",
        contact_channel="phone_note",
        text='My points are missing <script>alert("x")</script> <img src=x onerror=alert(1)>',
    )
    assert page.status_code == 200 and resp.status_code == 200
    assert "<script>alert" not in resp.text and "&lt;script&gt;alert" in resp.text
    assert "<img src=x" not in resp.text


def test_create_case_validates_the_received_time(arm: ArmA) -> None:
    b = browser(arm, "agent.ana")
    b.get("/cases/new")
    bad = b.post("/cases", received_at_utc="yesterday", contact_channel="email", text="points missing")
    assert bad.status_code == 409 and "UTC" in bad.text
    ok = b.post("/cases", received_at_utc="2026-07-20T14:00", contact_channel="email", text="points missing")
    assert ok.status_code == 200 and field(ok.text, "case-status") == "New"
    with arm.sessions() as s:
        assert s.scalars(select(Case)).one().received_at_utc == "2026-07-20T14:00:00Z"


def test_an_incomplete_form_gets_a_page_not_a_stack_trace(arm: ArmA) -> None:
    b = browser(arm, "agent.ana")
    b.get("/cases/new")
    resp = b.post("/cases", contact_channel="email")
    assert resp.status_code == 400 and "received_at_utc" in resp.text and "Traceback" not in resp.text


def test_an_upstream_failure_shows_a_safe_error(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, "DV-001")
        svc.start_work(s, arm.who("agent.ana"), case)
    app = create_app(
        AppSettings(database_url=arm.app_url, sim_clock=True), lambda sim: arm.systems(sim, fault="auth_failure")
    )
    b = Browser(TestClient(app))
    b.login("agent.ana", arm.password)
    resp = b.get(f"/cases/{case.id}/member", member_number="GR-85640")
    assert resp.status_code == 502 and "did not answer as expected" in resp.text
    assert ARM_A_TOKEN not in resp.text and "Traceback" not in resp.text


def test_an_evidence_free_close_is_neither_offered_nor_accepted(arm: ArmA) -> None:
    """The A-000010 path (TD-17, ADR-0054): the page hides it and a forged POST with a valid CSRF token is refused."""
    with arm.sessions() as s:
        case_row = arm.load(s, "DV-001")[0]
    b = browser(arm, "agent.ana")
    case = f"/cases/{case_row.id}"
    page = b.post(f"{case}/start").text
    assert 'value="deny_not_found"' in page and 'value="deny_other"' in page
    assert 'value="deny_claim_window"' not in page
    forged = b.post(f"{case}/close", code="deny_claim_window", note="Outside the twelve-month claim window.")
    assert forged.status_code == 409 and "evidence is incomplete" in forged.text
    no_search = b.post(f"{case}/close", code="deny_not_found")
    assert no_search.status_code == 409 and "search the member screen first" in no_search.text
    assert "together" in b.get(f"{case}/member", first_name="Clara").text  # a rejected input is not a search
    assert "search the member screen first" in b.post(f"{case}/close", code="deny_not_found").text
    assert "No member matches exactly" in b.get(f"{case}/member", member_number="GR-00000").text
    closed = b.post(f"{case}/close", code="deny_not_found")
    assert field(closed.text, "case-status") == "Resolved" and field(closed.text, "resolution") == "deny_not_found"


def test_every_visible_control_works_over_http(arm: ArmA) -> None:
    """Spec B.13: every visible control has implemented behaviour. Drives each form and screen through the routes."""
    with arm.sessions() as s:
        first, second = arm.load(s, "DV-001")[0], arm.load(s, arm.scenario("K02"))[0]
    b = browser(arm, "agent.ana")
    assert "A-000001" in b.get("/queue", status="New").text
    assert "A-000001" not in b.get("/queue", mine="true").text
    assert b.get("/queue", queue="billing").status_code == 200

    case = f"/cases/{first.id}"
    assert field(b.post(f"{case}/start").text, "case-status") == "Investigating"
    assert "A-000001" in b.get("/queue", mine="true").text
    # Each screen: a search that finds nothing, an incomplete search, then the real one and its attach button.
    assert "No member matches exactly" in b.get(f"{case}/member", member_number="GR-00000").text
    assert "together" in b.get(f"{case}/member", first_name="Clara").text
    assert "GR-85640" in b.get(f"{case}/member", member_number="GR-85640").text
    b.post(f"{case}/member/attach", member_number="GR-85640")
    assert "No stay with that confirmation" in b.get(f"{case}/stay", confirmation="BR-0000").text
    assert "Attach to case" in b.get(f"{case}/stay", confirmation="BR-6638").text
    b.post(f"{case}/stay/attach", member_number="GR-85640", confirmation="BR-6638")
    recent = b.get(f"{case}/ledger")
    assert "from 2026-03-20" in recent.text  # 90 days before the request (2026-06-18)
    b.post(f"{case}/ledger/attach", member_number="GR-85640")
    page = b.get(case)
    assert "show older entries" in page.text and field(page.text, "checklist-outcome") == "incomplete_evidence"
    assert "all entries" in b.get(f"{case}/ledger", show_older="true").text
    b.post(f"{case}/ledger/attach", member_number="GR-85640", show_older="true")
    assert "No section contains" in b.get(f"{case}/policy", q="retro credit").text
    b.get(f"{case}/policy", q="missing points")
    b.post(f"{case}/policy/attach", ref="missing-points-requests#1")
    assert field(b.post(f"{case}/notes", body="Checked all four screens.").text, "message") == "Note added."
    refused = b.post(f"{case}/close", code="deny_other")
    assert refused.status_code == 409 and "override" in refused.text
    short = b.post(f"{case}/close", code="deny_other", note="too short")
    assert short.status_code == 409 and "at least 20 characters" in short.text
    info = b.post(f"{case}/request-info", message="Please confirm your stay dates.")
    assert field(info.text, "case-status") == "Awaiting information"
    assert field(b.post(f"{case}/resume").text, "case-status") == "Investigating"
    assert field(b.post(f"{case}/request-adjustment").text, "case-status") == "Pending approval"

    other = f"/cases/{second.id}"
    b.post(f"{other}/start")
    assert field(b.post(f"{other}/escalate", reason="Two records disagree.").text, "case-status") == "Escalated"
    assert "disabled" in b.get(f"{other}/member").text  # screens are read-only once the case has moved on

    sup = browser(arm, "supervisor.sam")
    assert "Yes: open the case" in sup.get("/approvals").text
    sup.get(case)
    rejected = sup.post("/adjustments/1/decide", decision="reject")
    assert rejected.status_code == 409 and "reason" in rejected.text
    assert sup.post("/adjustments/1/decide", decision="maybe").status_code == 409
    assert field(sup.post("/adjustments/1/decide", decision="approve").text, "case-status") == "Approved"
    done = sup.post("/adjustments/1/execute")
    assert field(done.text, "case-status") == "Resolved" and field(done.text, "message").startswith("Adjustment")
    assert sup.post("/adjustments/1/check-status").status_code == 409  # nothing uncertain to check
    assert sup.get("/cases/999").status_code == 404
    assert sup.client.get("/", follow_redirects=False).headers["location"] == "/queue"
