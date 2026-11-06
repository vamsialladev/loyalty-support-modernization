"""Authorization on every operation (spec C.5; SEC-07, SEC-12, SEC-16, SEC-17; ENT-09, ENT-10, ENT-27; ACC-08).

The route tests walk the app's real routes, so a new route is covered, or fails, without anyone remembering to add it.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain.roles import Identity, NotPermitted, Role
from app.main import create_app
from app.outbound import BlockedUrl, check_external_url, check_url
from app.persistence.models import Case, CaseEvent, CaseNote, CaseRequest, SystemEvent, User
from app.ports.customer_systems import AuthenticationFailed
from app.services import accounts, conventional, jobs, metrics, rate_limit, retention
from app.services import cases as svc
from app.settings import AppSettings
from benchmarks.intake import load_case, read_split
from tests.arm_a import ArmA, Browser, make_arm_a

OTHER_CUSTOMER = "other-co"
PUBLIC = {
    "/",
    "/login",
    "/healthz",
    "/readyz",
    "/recover",
    "/auth/oidc/start",
    "/auth/oidc/callback",
    "/api/v1/openapi.json",
}
ADMIN_ONLY = ("/admin", "/admin/users", "/admin/access-review.csv")


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def app_for(arm: ArmA, **settings: Any) -> Any:
    return create_app(AppSettings(database_url=arm.app_url, sim_clock=True, **settings), arm.factory())


def browser(arm: ArmA, user: str | None = None, landing: str = "Points queue", **settings: Any) -> Browser:
    b = Browser(TestClient(app_for(arm, **settings)))
    if user:
        b.login(user, arm.password, "Configuration" if user.startswith("admin") else landing)
    return b


def console_routes(app: Any) -> list[tuple[str, str]]:
    out = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                out.append((method, route.path))
    return sorted(out)


def fill(path: str) -> str:
    for name in ("case_id", "request_id", "user_id", "row_id", "version"):
        path = path.replace("{" + name + "}", "1")
    return path.replace("{policy_id}", "x").replace("{section_id}", "1").replace("{name}", "x")


def test_every_console_route_needs_a_session_unless_its_listed_public(arm: ArmA) -> None:
    app = app_for(arm)
    client = TestClient(app, follow_redirects=False)
    checked = 0
    for method, path in console_routes(app):
        if path in PUBLIC:
            continue
        resp = client.request(method, fill(path))
        assert resp.status_code in (303, 400, 401, 403, 422), (method, path, resp.status_code)
        if method == "GET":
            assert resp.status_code == 303 and resp.headers["location"] == "/login", (method, path)
        checked += 1
    assert checked > 30


def test_no_console_post_works_without_its_csrf_token(arm: ArmA) -> None:
    app = app_for(arm)
    agent = browser(arm, "agent.ana")
    client = agent.client
    with arm.sessions() as s:
        request = svc.IntakeRequest(received_at_utc="2026-07-01T10:00:00Z", contact_channel="email", text="Points.")
        svc.create_case(s, arm.who("agent.ana"), request, arm="B")
    for method, path in console_routes(app):
        if method != "POST" or path.startswith("/api/") or path in ("/login", "/recover"):
            continue
        fields = {
            "body": "x", "reason": "x" * 30, "code": "deny_other", "note": "x" * 30, "message": "x", "decision":
            "approve", "engage": "on", "source": "x", "rating": "helpful", "name": "x", "value": "off",
            "member_number": "x", "reference": "x", "hold": "on", "confirm": "x", "received_at_utc":
            "2026-07-01T10:00:00Z", "contact_channel": "email", "text": "x", "ref": "x", "confirmation": "x",
        }  # fmt: skip
        resp = client.post(fill(path), data={**fields, "csrf": "wrong"}, follow_redirects=False)
        # 400 or 422: a required part is missing, so it was refused before the token was even looked at.
        assert resp.status_code in (400, 403, 422), (path, resp.status_code)


@pytest.mark.parametrize(
    ("user", "landing"),
    [("agent.ana", "Points queue"), ("supervisor.sam", "Points queue"), ("auditor.abe", "Points queue")],
)
def test_only_an_administrator_reaches_configuration(arm: ArmA, user: str, landing: str) -> None:
    b = browser(arm, user, landing)
    for url in ADMIN_ONLY:
        assert b.get(url).status_code == 403, url
    assert b.post("/admin/kill-switch", engage="on", reason="x" * 20).status_code == 403
    assert b.post("/admin/api-tokens", name="x").status_code == 403
    assert b.post("/admin/legal-hold", reference="x", hold="on", reason="x").status_code == 403
    assert b.post("/admin/data-subject/erase", member_number="x", confirm="x").status_code == 403


def test_an_administrator_doesnt_read_or_work_cases(arm: ArmA) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    with arm.sessions() as s:
        cid = load_case(s, item, arm="B")[0].id
    admin = browser(arm, "admin.ada")
    assert admin.get(f"/cases/{cid}").status_code == 403
    assert admin.post(f"/cases/{cid}/investigate").status_code == 403


def test_an_auditor_reads_and_changes_nothing(arm: ArmA) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    with arm.sessions() as s:
        cid = load_case(s, item, arm="B")[0].id
    auditor = browser(arm, "auditor.abe")
    assert auditor.get(f"/cases/{cid}").status_code == 200
    for url, fields in (
        (f"/cases/{cid}/investigate", {}),
        (f"/cases/{cid}/notes", {"body": "x"}),
        (f"/cases/{cid}/escalate", {"reason": "x"}),
        (f"/cases/{cid}/feedback", {"rating": "helpful"}),
    ):
        assert auditor.post(url, **fields).status_code == 403, url


def test_a_form_field_cant_set_a_role(arm: ArmA) -> None:
    agent = browser(arm, "agent.ana")
    resp = agent.post("/admin/kill-switch", engage="on", reason="x" * 20, role="administrator", is_admin="true")
    assert resp.status_code == 403


# ---------- another customer's records don't exist ----------


def _other_customers_case(arm: ArmA) -> tuple[int, int]:
    """A case and a pending request belonging to another customer, in the same database."""
    from app.clock import utc_now
    from app.persistence.models import AdjustmentRequestRow

    with arm.sessions() as s:
        who = Identity(0, "intake", "Intake", Role.AGENT, OTHER_CUSTOMER)
        request = svc.IntakeRequest(
            received_at_utc="2026-07-01T10:00:00Z", contact_channel="email", text="Secret text."
        )
        case = svc.create_case(s, who, request, customer_id=OTHER_CUSTOMER, arm="B")
        case.status = "Pending approval"
        row = AdjustmentRequestRow(
            case_id=case.id,
            member_number="GR-99999",
            stay_id="BR-9999",
            points=100,
            reason_code="missing_points",
            checklist={},
            requested_by="someone",
            requested_at_utc=utc_now(),
            status="pending",
        )
        s.add(row)
        s.commit()
        return case.id, row.id


def test_another_customers_case_doesnt_exist_on_the_console(arm: ArmA) -> None:
    cid, rid = _other_customers_case(arm)
    supervisor = browser(arm, "supervisor.sam")
    assert supervisor.get(f"/cases/{cid}").status_code == 404
    assert "Secret text" not in supervisor.get("/queue").text
    assert supervisor.post(f"/cases/{cid}/notes", body="x").status_code == 404
    assert supervisor.post(f"/adjustments/{rid}/decide", decision="approve").status_code == 404
    assert supervisor.post(f"/adjustments/{rid}/execute").status_code == 404
    assert "BR-9999" not in supervisor.get("/approvals").text


def test_another_customers_case_doesnt_exist_on_the_api(arm: ArmA) -> None:
    cid, rid = _other_customers_case(arm)
    b = browser(arm, "supervisor.sam")
    client = b.client
    assert client.get(f"/api/v1/cases/{cid}").status_code == 404
    assert client.get(f"/api/v1/cases/{cid}/audit").status_code == 404
    assert client.get(f"/api/v1/adjustments/{rid}").status_code == 404
    assert cid not in [c["id"] for c in client.get("/api/v1/cases").json()["items"]]
    csrf = client.get("/api/v1/me").json()["csrf_token"]
    decided = client.post(
        f"/api/v1/adjustments/{rid}/decision", json={"decision": "approve"}, headers={"X-CSRF-Token": csrf}
    )
    assert decided.status_code == 404


def test_metrics_and_cases_stay_inside_the_customer(arm: ArmA) -> None:
    _other_customers_case(arm)
    with arm.sessions() as s:
        found = metrics.collect(s, arm.who("supervisor.sam"))
        assert found.rows == []
        with pytest.raises(NotPermitted):
            request = svc.IntakeRequest(received_at_utc="2026-07-01T10:00:00Z", contact_channel="email", text="x")
            svc.create_case(s, arm.who("agent.ana"), request, customer_id=OTHER_CUSTOMER)


def test_an_administrator_of_one_customer_cant_touch_anothers_accounts(arm: ArmA) -> None:
    from app.clock import utc_now

    with arm.sessions() as s:
        other = User(
            username="other.admin",
            display_name="x",
            role="administrator",
            password_hash="x",
            customer_id=OTHER_CUSTOMER,
            created_at_utc=utc_now(),
        )
        s.add(other)
        s.commit()
        admin = arm.who("admin.ada")
        with pytest.raises(accounts.AccountError):
            accounts.set_active(s, admin, other.id, False)
        with pytest.raises(accounts.AccountError):
            accounts.issue_recovery(s, admin, other.id)
        assert "other.admin" not in [u.username for u in accounts.users_of(s, admin)]


# ---------- rate limits ----------


def _login_attempts(arm: ArmA) -> Callable[[str], Any]:
    b = browser(arm)

    def attempt(password: str) -> Any:
        page = b.client.get("/login")
        token = page.text.split('name="login_csrf" value="')[1].split('"')[0]
        return b.client.post(
            "/login", data={"username": "agent.ana", "password": password, "login_csrf": token}, follow_redirects=False
        )

    return attempt


def _freeze_limits(monkeypatch: pytest.MonkeyPatch, now: list[float]) -> None:
    """A fixed clock. With a real one, slow sign-ins can straddle a window's edge, which made this test fail once."""
    monkeypatch.setattr(rate_limit, "time", SimpleNamespace(time=lambda: now[0]))


def test_login_is_limited_per_account_and_a_right_password_doesnt_get_through_either(
    arm: ArmA, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_limits(monkeypatch, [1_200.0])
    attempt = _login_attempts(arm)
    for _ in range(rate_limit.LOGIN_FAILURES_PER_ACCOUNT):
        assert attempt("wrong-password-123").status_code == 303
    refused = attempt("wrong-password-123")
    assert refused.status_code == 429 and refused.headers["retry-after"]
    assert attempt(arm.password).status_code == 429
    with arm.sessions() as s:
        assert s.scalars(select(SystemEvent).where(SystemEvent.action == "sign_in_failed")).first()


def test_a_new_window_starts_counting_again_which_is_the_cost_of_fixed_windows(
    arm: ArmA, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An attacker can spend one window's failures just before its edge and the next window's just after.

    `docs/known-limitations.md` states this. The test pins the number: at most twice the limit, close together.
    """
    now = [1_200.0 + rate_limit.LOGIN_WINDOW_SECONDS - 1]
    _freeze_limits(monkeypatch, now)
    attempt = _login_attempts(arm)
    for _ in range(rate_limit.LOGIN_FAILURES_PER_ACCOUNT):
        assert attempt("wrong-password-123").status_code == 303
    assert attempt("wrong-password-123").status_code == 429
    now[0] += 2  # past the edge
    for _ in range(rate_limit.LOGIN_FAILURES_PER_ACCOUNT):
        assert attempt("wrong-password-123").status_code == 303
    assert attempt("wrong-password-123").status_code == 429


def test_a_good_sign_in_clears_the_failures(arm: ArmA) -> None:
    b = browser(arm)
    with arm.sessions() as s:
        for _ in range(rate_limit.LOGIN_FAILURES_PER_ACCOUNT - 1):
            rate_limit.record_login_failure(s, "agent.ana", "testclient")
    b.login("agent.ana", arm.password)
    with arm.sessions() as s:
        rate_limit.check_login(s, "agent.ana", "testclient")


def test_requests_are_limited_per_person_on_the_console_and_the_api(arm: ArmA) -> None:
    b = browser(arm, "agent.ana", rate_limit_per_minute=3)
    codes = [b.get("/queue").status_code for _ in range(5)]
    assert 429 in codes
    b2 = browser(arm, "agent.ben", rate_limit_per_minute=3)
    codes = [b2.client.get("/api/v1/me").status_code for _ in range(5)]
    assert 429 in codes
    last = b2.client.get("/api/v1/me")
    assert last.headers["content-type"].startswith("application/problem+json") and last.headers["retry-after"]


def test_the_window_resets(arm: ArmA) -> None:
    now = [1200.0]
    with arm.sessions() as s:
        rate_limit.hit(s, "k", 1, 60, clock=lambda: now[0])
        with pytest.raises(rate_limit.RateLimited) as refused:
            rate_limit.hit(s, "k", 1, 60, clock=lambda: now[0] + 10)
        assert refused.value.retry_after_seconds == 50
        now[0] += 60
        rate_limit.hit(s, "k", 1, 60, clock=lambda: now[0])


# ---------- accounts ----------


def test_deactivating_ends_sessions_at_once(arm: ArmA) -> None:
    b = browser(arm, "agent.ben")
    assert b.get("/queue").status_code == 200
    admin = browser(arm, "admin.ada")
    page = admin.get("/admin/users")
    assert "agent.ben" in page.text
    with arm.sessions() as s:
        ben = s.scalars(select(User).where(User.username == "agent.ben")).one().id
    assert admin.post(f"/admin/users/{ben}/active", value="off").status_code == 200
    assert b.client.get("/queue", follow_redirects=False).status_code == 303
    relog = browser(arm)
    token = relog.client.get("/login").text.split('name="login_csrf" value="')[1].split('"')[0]
    done = relog.client.post(
        "/login", data={"username": "agent.ben", "password": arm.password, "login_csrf": token}, follow_redirects=False
    )
    assert done.headers["location"] == "/login?failed=true"


def test_an_administrator_cant_lock_themselves_out(arm: ArmA) -> None:
    admin = browser(arm, "admin.ada")
    with arm.sessions() as s:
        ada = s.scalars(select(User).where(User.username == "admin.ada")).one().id
    assert admin.post(f"/admin/users/{ada}/active", value="off").status_code == 409


def test_recovery_works_once_and_signs_everyone_out(arm: ArmA) -> None:
    ben = browser(arm, "agent.ben")
    with arm.sessions() as s:
        user = s.scalars(select(User).where(User.username == "agent.ben")).one()
        token = accounts.issue_recovery(s, arm.who("admin.ada"), user.id)
        stored = repr(s.scalars(select(SystemEvent)).all())
    assert token not in stored
    fresh = browser(arm)
    page = fresh.client.get(f"/recover?token={token}")
    form = page.text.split('name="login_csrf" value="')[1].split('"')[0]
    new_password = "a-brand-new-password-1"
    assert (
        fresh.client.post("/recover", data={"token": token, "password": "short", "login_csrf": form}).status_code == 409
    )
    done = fresh.client.post(
        "/recover", data={"token": token, "password": new_password, "login_csrf": form}, follow_redirects=False
    )
    assert done.status_code == 303
    assert ben.client.get("/queue", follow_redirects=False).status_code == 303
    page = fresh.client.get(f"/recover?token={token}")
    form = page.text.split('name="login_csrf" value="')[1].split('"')[0]
    again = fresh.client.post("/recover", data={"token": token, "password": new_password, "login_csrf": form})
    assert again.status_code == 409 and "recovery link" in again.text
    browser_new = Browser(TestClient(app_for(arm)))
    browser_new.login("agent.ben", new_password)


def test_a_wrong_or_expired_recovery_token_says_the_same_thing(arm: ArmA) -> None:
    from app.persistence.models import RecoveryToken

    with arm.sessions() as s:
        user = s.scalars(select(User).where(User.username == "agent.ben")).one()
        token = accounts.issue_recovery(s, arm.who("admin.ada"), user.id)
        for row in s.scalars(select(RecoveryToken)):
            row.expires_at_utc = "2020-01-01T00:00:00Z"
        s.commit()
        for candidate in (token, "not-a-token"):
            with pytest.raises(accounts.AccountError, match="isn't valid"):
                accounts.redeem_recovery(s, candidate, "a-long-enough-password")


def test_a_shown_once_recovery_link_is_only_in_the_response(arm: ArmA) -> None:
    admin = browser(arm, "admin.ada")
    with arm.sessions() as s:
        ben = s.scalars(select(User).where(User.username == "agent.ben")).one().id
    page = admin.post(f"/admin/users/{ben}/recovery")
    assert "/recover?token=" in page.text and "won't be shown again" in page.text
    assert page.headers["cache-control"] == "no-store"


def test_a_machine_token_reads_and_cant_write(arm: ArmA) -> None:
    client = TestClient(app_for(arm))
    with arm.sessions() as s:
        issued = accounts.issue_api_token(s, arm.who("admin.ada"), "reporting")
        stored = [e.detail for e in s.scalars(select(SystemEvent))]
    assert issued.token not in repr(stored)
    headers = {"Authorization": f"Bearer {issued.token}"}
    assert client.get("/api/v1/cases", headers=headers).status_code == 200
    me = client.get("/api/v1/me", headers=headers).json()
    assert me["role"] == "auditor" and me["csrf_token"] == ""
    body = {"received_at_utc": "2026-07-01T10:00:00Z", "contact_channel": "email", "text": "x"}
    assert client.post("/api/v1/cases", json=body, headers=headers).status_code == 403
    assert client.post("/api/v1/cases", json=body, headers={**headers, "X-CSRF-Token": ""}).status_code == 403
    assert client.get("/queue", headers=headers, follow_redirects=False).status_code == 303  # no console access


def test_a_revoked_expired_or_made_up_token_is_refused(arm: ArmA) -> None:
    from app.persistence.models import ApiToken

    client = TestClient(app_for(arm))
    with arm.sessions() as s:
        admin = arm.who("admin.ada")
        revoked = accounts.issue_api_token(s, admin, "old")
        accounts.revoke_api_token(s, admin, "old")
        expired = accounts.issue_api_token(s, admin, "stale")
        s.scalars(select(ApiToken).where(ApiToken.name == "stale")).one().expires_at_utc = "2020-01-01T00:00:00Z"
        s.commit()
    for token in (revoked.token, expired.token, "lsm_made_up"):
        assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_the_access_review_lists_people_and_no_secrets(arm: ArmA) -> None:
    admin = browser(arm, "admin.ada")
    resp = admin.get("/admin/access-review.csv")
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    names = {r["username"] for r in rows}
    assert {"agent.ana", "admin.ada"} <= names and resp.headers["content-type"].startswith("text/csv")
    assert "password" not in resp.text and "$argon2" not in resp.text
    assert next(r for r in rows if r["username"] == "admin.ada")["last_sign_in_utc"] != "never"


# ---------- errors, CORS, docs ----------


def test_an_unexpected_error_shows_no_stack_trace(arm: ArmA) -> None:
    def broken(_sim: str | None) -> Any:
        raise RuntimeError("secret-looking internal detail at /srv/app/x.py line 9")

    app = create_app(AppSettings(database_url=arm.app_url, sim_clock=True), broken)
    b = Browser(TestClient(app, raise_server_exceptions=False))
    b.login("agent.ana", arm.password)
    with arm.sessions() as s:
        request = svc.IntakeRequest(received_at_utc="2026-07-01T10:00:00Z", contact_channel="email", text="x")
        cid = svc.create_case(s, arm.who("agent.ana"), request, arm="A").id
    b.get(f"/cases/{cid}")
    b.post(f"/cases/{cid}/start")
    resp = b.post(f"/cases/{cid}/request-info", message="hello")
    assert resp.status_code == 500
    for leak in ("secret-looking", "Traceback", "/srv/app", "RuntimeError"):
        assert leak not in resp.text
    assert "The reference is" in resp.text


def test_no_cross_origin_access_is_offered(arm: ArmA) -> None:
    client = TestClient(app_for(arm))
    headers = {"Origin": "https://evil.test", "Access-Control-Request-Method": "POST"}
    assert "access-control-allow-origin" not in client.options("/api/v1/cases", headers=headers).headers
    assert "access-control-allow-origin" not in client.get("/healthz", headers={"Origin": "https://evil.test"}).headers


def test_the_default_docs_pages_are_off(arm: ArmA) -> None:
    client = TestClient(app_for(arm))
    for url in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(url).status_code == 404, url
    assert client.get("/api/v1/openapi.json").status_code == 200


# ---------- outbound destinations (SEC-16) ----------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://idp.test/",
        "http://user:pass@idp.test/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://evil.test/x",
        "http:///nohost",
    ],
)
def test_only_configured_destinations_are_called(url: str) -> None:
    with pytest.raises(BlockedUrl):
        check_url(url, ("http://idp.test/realms/hotel",))


def test_a_configured_destination_passes_even_if_internal() -> None:
    assert check_url("http://keycloak:8080/x", ("http://keycloak:8080/realms/hotel",))


@pytest.mark.parametrize(
    ("url", "addresses"),
    [
        ("http://hooks.test/x", ["93.184.216.34"]),
        ("https://other.test/x", ["93.184.216.34"]),
        ("https://metadata.google.internal/x", ["169.254.169.254"]),
        ("https://hooks.test/x", ["169.254.169.254"]),
        ("https://hooks.test/x", ["10.0.0.5"]),
        ("https://hooks.test/x", ["127.0.0.1"]),
        ("https://hooks.test/x", ["::1"]),
    ],
)
def test_an_outside_url_cant_lead_inside(url: str, addresses: list[str]) -> None:
    with pytest.raises(BlockedUrl):
        check_external_url(url, ("hooks.test", "metadata.google.internal"), resolve=lambda _h: addresses)


def test_a_clean_outside_url_passes() -> None:
    assert check_external_url("https://hooks.test/x", ("hooks.test",), resolve=lambda _h: ["93.184.216.34"])


# ---------- retention, data requests, legal hold ----------


def _closed_case(arm: ArmA, case_id: str = "DV-002") -> int:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == case_id)
    with arm.sessions() as s:
        case = load_case(s, item, arm="B")[0]
        who = arm.who("agent.ana")
        conventional.start_investigation(s, who, case)
        conventional.investigate_case(s, who, case, arm.factory()(case.received_at_utc))
        svc.add_note(s, who, case, "A note that mentions the member.")
        svc.escalate(s, who, case, "Closing this for the test.")
        return case.id


def test_erasure_removes_personal_data_and_keeps_the_audit_and_the_credits(arm: ArmA) -> None:
    cid = _closed_case(arm)
    member = arm.labels["DV-002"]["claimant_member_number"]
    with arm.sessions() as s:
        before = len(list(s.scalars(select(CaseEvent).where(CaseEvent.case_id == cid))))
        exported = retention.export_member(s, arm.who("admin.ada"), member)
        assert [c["reference"] for c in exported["cases"]] and exported["cases"][0]["requests"][0][
            "text"
        ] != "(removed)"
        report = retention.erase_member(s, arm.who("admin.ada"), member)
        assert report.removed == 1
        request = s.scalars(select(CaseRequest).where(CaseRequest.case_id == cid)).one()
        assert request.text == "(removed)" and request.sender_email is None
        assert all(n.body == "(removed)" for n in s.scalars(select(CaseNote).where(CaseNote.case_id == cid)))
        case = s.get(Case, cid)
        assert case is not None and case.personal_data_removed_at_utc and case.status == "Escalated"
        assert conventional.latest_evidence(s, case) is None
        assert len(list(s.scalars(select(CaseEvent).where(CaseEvent.case_id == cid)))) == before + 1
        assert retention.export_member(s, arm.who("admin.ada"), member)["cases"] != []  # the decision stays findable


def test_a_legal_hold_stops_erasure_and_retention_and_is_audited(arm: ArmA) -> None:
    cid = _closed_case(arm)
    member = arm.labels["DV-002"]["claimant_member_number"]
    with arm.sessions() as s:
        case = s.get(Case, cid)
        assert case is not None
        retention.set_legal_hold(s, arm.who("admin.ada"), case, True, "A dispute is open.")
        assert retention.erase_member(s, arm.who("admin.ada"), member).held == 1
        case.updated_at_utc = "2000-01-01T00:00:00Z"
        s.commit()
        assert retention.apply_retention(s, jobs.SYSTEM, case.customer_id, days=1).held == 1
        assert s.scalars(select(CaseRequest).where(CaseRequest.case_id == cid)).one().text != "(removed)"
        actions = [e.action for e in s.scalars(select(CaseEvent).where(CaseEvent.case_id == cid))]
        assert "legal_hold_set" in actions
        with pytest.raises(NotPermitted):
            retention.set_legal_hold(s, arm.who("supervisor.sam"), case, False, "Trying.")


def test_an_open_case_isnt_erased(arm: ArmA) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-002")
    member = arm.labels["DV-002"]["claimant_member_number"]
    with arm.sessions() as s:
        case = load_case(s, item, arm="B")[0]
        who = arm.who("agent.ana")
        conventional.start_investigation(s, who, case)
        conventional.investigate_case(s, who, case, arm.factory()(case.received_at_utc))
        assert retention.erase_member(s, arm.who("admin.ada"), member).still_open == 1


def test_retention_only_touches_old_closed_cases_and_a_dry_run_changes_nothing(arm: ArmA) -> None:
    old, recent = _closed_case(arm, "DV-002"), _closed_case(arm, "DV-012")
    with arm.sessions() as s:
        case = s.get(Case, old)
        assert case is not None
        case.updated_at_utc = "2000-01-01T00:00:00Z"
        s.commit()
        dry = retention.apply_retention(s, jobs.SYSTEM, case.customer_id, days=30, dry_run=True)
        assert dry.removed == 1 and case.personal_data_removed_at_utc is None
        real = retention.apply_retention(s, jobs.SYSTEM, case.customer_id, days=30)
        assert real.removed == 1 and case.personal_data_removed_at_utc
        other = s.get(Case, recent)
        assert other is not None and other.personal_data_removed_at_utc is None
        assert retention.apply_retention(s, jobs.SYSTEM, case.customer_id, days=30).removed == 0


def test_the_data_request_pages_need_confirmation(arm: ArmA) -> None:
    _closed_case(arm)
    member = arm.labels["DV-002"]["claimant_member_number"]
    admin = browser(arm, "admin.ada")
    admin.get("/admin/users")
    assert admin.post("/admin/data-subject/erase", member_number=member, confirm="something else").status_code == 409
    exported = admin.post("/admin/data-subject/export", member_number=member)
    assert exported.status_code == 200 and json.loads(exported.text)["synthetic"] is True
    done = admin.post("/admin/data-subject/erase", member_number=member, confirm=member)
    assert done.status_code == 200 and "removed=1" in done.text


# ---------- rotation (ACC-08) ----------


def test_rotating_the_customer_systems_token_makes_the_old_one_fail(
    mock_template: dict[str, Any], tmp_path: Path
) -> None:
    """Exercised once with a test credential. The old value is proved to fail, not assumed to."""
    from app.adapters.mock_customer_api import MockCustomerApiAdapter
    from customer_shapes import CustomerShape
    from mock_customer_api import db as mock_db
    from mock_customer_api.api import create_app as create_mock_app
    from mock_customer_api.settings import Settings as MockSettings

    def api(token: str) -> TestClient:
        settings = MockSettings(
            database_url=f"sqlite:///{mock_template['path'].as_posix()}", token=token, sim_clock_enabled=True
        )
        return TestClient(create_mock_app(settings, mock_db.make_engine(settings.database_url)), base_url="http://mock")

    shape = CustomerShape.load("hg-demo")
    member = next(iter(mock_template["labels"].values()))["facts"]["claimant"]
    before = api("rotation-test-old-value")
    adapter_old = MockCustomerApiAdapter("http://mock", "rotation-test-old-value", shape, client=before)
    assert adapter_old.get_member(member)
    after = api("rotation-test-new-value")
    assert MockCustomerApiAdapter("http://mock", "rotation-test-new-value", shape, client=after).get_member(member)
    with pytest.raises(AuthenticationFailed):
        MockCustomerApiAdapter("http://mock", "rotation-test-old-value", shape, client=after).get_member(member)
