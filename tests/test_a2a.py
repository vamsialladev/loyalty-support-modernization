"""A2A: the loyalty coordinator and the reservation evidence specialist (spec G.4, G.13; PROTO-04; T20-T24).

Both run as real ASGI apps on the official `a2a-sdk`; the coordinator reaches the specialist through httpx's ASGI
transport, so every request is real JSON-RPC over HTTP, in process. **Same SDK on both sides, so this isn't interop
proof;** the independent peer is in `docs/protocol-test-results.md`. Business effects are checked too: whatever the
peer does, the case's state, evidence and engine result don't change.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from app.domain.roles import Identity, Role
from app.persistence.models import A2aTask, Case, CaseEvent, CaseEvidence, Recommendation
from app.services import conventional
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath
from app.worker import Worker
from benchmarks.intake import load_case, read_split
from protocols.a2a.coordinator import CoordinatorConfig, handle_notification, notification_app, request_evidence
from protocols.a2a.evidence import EvidenceRequest, InvalidArtifact, check_artifact, content_hash
from protocols.a2a.specialist import CARD_PATH, SCOPE, SpecialistConfig, build_app
from protocols.common.tokens import ResourceServer, StaticKeys, TokenVerifier
from tests.arm_a import ArmA, make_arm_a
from tests.protocol_tokens import ISSUER, MCP_AUDIENCE, TestIssuer

SPECIALIST = "http://127.0.0.1:8041"
CALLBACKS = "http://127.0.0.1:8050"


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def _load(arm: ArmA, investigate: bool = True) -> int:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == arm.scenario("K01"))
    with arm.sessions() as s:
        cid = load_case(s, item, arm="B")[0].id
        if investigate:
            conventional.start_investigation(s, arm.who("agent.ana"), s.get(Case, cid))  # type: ignore[arg-type]
    if investigate:
        Worker(arm.sessions, build_handlers(SharedWritePath("hg-demo"), arm.factory(), None)).drain()
    return cid


@pytest.fixture
def case_id(arm: ArmA) -> int:
    return _load(arm)


@pytest.fixture(scope="module")
def idp() -> TestIssuer:
    return TestIssuer()


def specialist(arm: ArmA, idp: TestIssuer, push: httpx.AsyncClient | None = None, **over: Any) -> Any:
    config = SpecialistConfig(SPECIALIST, ISSUER, "hg-demo", (CALLBACKS,), **over)
    verifier = TokenVerifier(
        ResourceServer("a2a-specialist", ISSUER, SPECIALIST, frozenset({SCOPE})), StaticKeys(idp.jwks())
    )
    return build_app(config, verifier, lambda: arm.systems(), push_http=push)


def token(idp: TestIssuer, **over: Any) -> str:
    return idp.token(**{"audience": SPECIALIST, "scope": SCOPE, "client_id": "a2a-coordinator", **over})


def ask(arm: ArmA, app: Any, idp: TestIssuer, case_id: int, **over: Any) -> dict[str, Any]:
    tok = over.pop("tok", None) or token(idp)
    config = CoordinatorConfig(
        **{"specialist_url": SPECIALIST, "customer_id": "hg-demo", "timeout_seconds": 10.0, **over}
    )
    transport = over.pop("transport", None) if "transport" in over else httpx.ASGITransport(app=app)
    return asyncio.run(request_evidence(arm.sessions, case_id, config, lambda: tok, transport))


def ask_with(
    arm: ArmA, transport: httpx.AsyncBaseTransport, idp: TestIssuer, case_id: int, **config: Any
) -> dict[str, Any]:
    full = CoordinatorConfig(
        **{"specialist_url": SPECIALIST, "customer_id": "hg-demo", "timeout_seconds": 10.0, **config}
    )
    tok = token(idp)
    return asyncio.run(request_evidence(arm.sessions, case_id, full, lambda: tok, transport))


def case_state(arm: ArmA, case_id: int) -> tuple[str, int, int]:
    with arm.sessions() as s:
        case = s.get(Case, case_id)
        assert case is not None
        evidence = s.scalar(select(func.count()).select_from(CaseEvidence).where(CaseEvidence.case_id == case_id))
        recs = s.scalar(select(func.count()).select_from(Recommendation).where(Recommendation.case_id == case_id))
        return case.status, int(evidence or 0), int(recs or 0)


def actions(arm: ArmA, case_id: int) -> list[str]:
    with arm.sessions() as s:
        return [
            e.action for e in s.scalars(select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.step))
        ]


class Unreachable(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        raise httpx.ConnectError("connection refused", request=request)


# ---------- the whole path ----------


def test_the_coordinator_gets_evidence_with_provenance_and_the_case_doesnt_change(
    arm: ArmA, idp: TestIssuer, case_id: int
) -> None:
    before = case_state(arm, case_id)
    result = ask(arm, specialist(arm, idp), idp, case_id)
    assert result["state"] == "completed" and result["remote_task_id"] and len(result["artifact_sha256"]) == 64
    with arm.sessions() as s:
        row = s.get(A2aTask, result["id"])
        assert row is not None and row.artifact is not None
        artifact = row.artifact
        rec = conventional.latest_recommendation(s, s.get(Case, case_id))  # type: ignore[arg-type]
        assert rec is not None
    assert artifact["member_number"] == rec.member_number and artifact["stays"]
    assert artifact["provenance"]["agent"] == "reservation-evidence-specialist"
    assert set(artifact["provenance"]["record_ids"]) >= {s["record_id"] for s in artifact["stays"]}
    for stay in artifact["stays"]:
        assert not {"guest_name", "room_revenue_cents", "rate_code"} & set(stay)  # minimum needed, no more
    assert case_state(arm, case_id) == before  # status, evidence and engine result are untouched
    assert actions(arm, case_id)[-2:] == ["a2a_evidence_requested", "a2a_evidence_received"]


def test_a_second_request_while_one_is_open_gets_the_open_one_and_sends_nothing(
    arm: ArmA, idp: TestIssuer, case_id: int
) -> None:
    with arm.sessions() as s:
        s.add(
            A2aTask(
                case_id=case_id,
                requested_by="svc-a2a-coordinator",
                peer=SPECIALIST,
                state="submitted",
                created_at_utc="2026-11-11T00:00:00Z",
            )
        )
        s.commit()
    transport = Unreachable()
    result = ask_with(arm, transport, idp, case_id)
    assert result["state"] == "submitted" and transport.calls == 0


def test_no_confirmed_member_means_no_call(arm: ArmA, idp: TestIssuer) -> None:
    cid = _load(arm, investigate=False)
    transport = Unreachable()
    result = ask_with(arm, transport, idp, cid)
    assert result["state"] == "rejected" and result["detail"] == "no_confirmed_member" and transport.calls == 0


def test_the_coordinator_only_reads_its_own_customers_cases(arm: ArmA, idp: TestIssuer, case_id: int) -> None:
    transport = Unreachable()
    result = ask_with(arm, transport, idp, case_id, customer_id="cedarpoint")
    assert result["state"] == "not_found" and transport.calls == 0


# ---------- the specialist's checks ----------


def test_the_specialist_rejects_a_task_from_another_customers_token(arm: ArmA, idp: TestIssuer, case_id: int) -> None:
    """Per-task authorization from the token, not the message: the message names a hg-demo member, the token says
    cedarpoint, so the task is rejected."""
    result = ask(arm, specialist(arm, idp), idp, case_id, tok=token(idp, customer_id="cedarpoint"))
    assert result["state"] == "rejected"
    assert case_state(arm, case_id)[0] == "investigating" or case_state(arm, case_id)[0]


def call_specialist(
    app: Any, headers: dict[str, str], body: dict[str, Any] | None = None, path: str = "/"
) -> httpx.Response:
    async def go() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=SPECIALIST) as http:
            if body is None:
                return await http.get(path, headers=headers)
            return await http.post(path, json=body, headers=headers)

    return asyncio.run(go())


SEND = {"jsonrpc": "2.0", "id": 1, "method": "SendMessage", "params": {}}


@pytest.mark.parametrize(
    "make",
    [
        lambda i: "",
        lambda i: "Bearer not-a-jwt",
        lambda i: f"Bearer {token(i, expires_in=-120)}",
        lambda i: f"Bearer {i.token(audience=MCP_AUDIENCE, scope=SCOPE)}",  # a token for the MCP server
        lambda i: f"Bearer {token(i, issuer='http://evil.example/realms/hotel')}",
    ],
)
def test_the_specialist_needs_a_token_for_itself(arm: ArmA, idp: TestIssuer, make: Any) -> None:
    response = call_specialist(specialist(arm, idp), {"Authorization": make(idp)} if make(idp) else {}, SEND)
    assert response.status_code == 401 and response.headers["www-authenticate"].startswith("Bearer")


def test_a_token_without_the_specialists_scope_is_403(arm: ArmA, idp: TestIssuer) -> None:
    response = call_specialist(
        specialist(arm, idp), {"Authorization": f"Bearer {token(idp, scope='loyalty.read')}"}, SEND
    )
    assert response.status_code == 403 and 'error="insufficient_scope"' in response.headers["www-authenticate"]


def test_the_agent_card_is_public_and_describes_oauth_not_a_secret(arm: ArmA, idp: TestIssuer) -> None:
    response = call_specialist(specialist(arm, idp), {}, path=CARD_PATH)
    card = response.json()
    assert response.status_code == 200
    assert card["skills"][0]["id"] == "reservation_evidence"
    assert card["supportedInterfaces"][0] == {"url": SPECIALIST, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}
    flow = card["securitySchemes"]["oauth"]["oauth2SecurityScheme"]["flows"]["clientCredentials"]
    assert flow["tokenUrl"] == f"{ISSUER}/protocol/openid-connect/token" and SCOPE in flow["scopes"]
    assert "secret" not in json.dumps(card).lower() and "SYNTHETIC" in card["name"]


def test_the_agent_card_can_be_cached_for_five_minutes_and_nothing_else_is(arm: ArmA, idp: TestIssuer) -> None:
    """A2A 1.0 §8.6.1 (SHOULD), found by the A2A TCK as CARD-CACHE-001: only the card gets the header."""
    app = specialist(arm, idp)
    assert call_specialist(app, {}, path=CARD_PATH).headers["cache-control"] == "public, max-age=300"
    assert "cache-control" not in call_specialist(app, {}, SEND).headers


def _post_raw(app: Any, headers: dict[str, str]) -> httpx.Response:
    async def go() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=SPECIALIST) as http:
            return await http.post("/", content=json.dumps(SEND).encode(), headers=headers)

    return asyncio.run(go())


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", ""])
def test_a_request_that_isnt_json_is_refused_after_the_token_check(
    arm: ArmA, idp: TestIssuer, content_type: str
) -> None:
    """TD-53, found by the A2A TCK: a wrong Content-Type used to reach the JSON-RPC handler."""
    app = specialist(arm, idp)
    headers = {"Content-Type": content_type} if content_type else {}
    assert _post_raw(app, headers).status_code == 401  # no token: still 401 first
    refused = _post_raw(app, {**headers, "Authorization": f"Bearer {token(idp)}", "A2A-Version": "1.0"})
    assert refused.status_code == 415 and refused.json()["error"]["code"] == -32600


def test_json_with_a_charset_still_reaches_the_handler(arm: ArmA, idp: TestIssuer) -> None:
    headers = {"Content-Type": "application/json; charset=utf-8", "Authorization": f"Bearer {token(idp)}"}
    assert _post_raw(specialist(arm, idp), headers | {"A2A-Version": "1.0"}).status_code == 200


def test_a_malformed_request_is_rejected_not_guessed(arm: ArmA, idp: TestIssuer) -> None:
    from protocols.a2a.specialist import EvidenceExecutor  # noqa: F401  (the executor validates with EvidenceRequest)

    with pytest.raises(ValueError):
        EvidenceRequest.model_validate({"case_reference": "C-1", "member_number": "GR-1", "customer_id": "cedarpoint"})


# ---------- the coordinator's checks ----------


def test_an_unreachable_specialist_is_recorded_and_the_case_is_unchanged(
    arm: ArmA, idp: TestIssuer, case_id: int
) -> None:
    before = case_state(arm, case_id)
    result = ask_with(arm, Unreachable(), idp, case_id)
    assert result["state"] == "peer_unavailable"
    assert case_state(arm, case_id) == before
    assert actions(arm, case_id)[-1] == "a2a_evidence_not_received"


def test_a_slow_specialist_times_out_and_the_task_is_canceled(arm: ArmA, idp: TestIssuer, case_id: int) -> None:
    """Over a real socket: in-process ASGI calls swallow the cancellation, so the deadline needs a real server."""
    import socket
    import threading
    import time

    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    url = f"http://127.0.0.1:{port}"
    config = SpecialistConfig(url, ISSUER, "hg-demo", (), read_delay_seconds=5.0)
    verifier = TokenVerifier(ResourceServer("a2a-specialist", ISSUER, url, frozenset({SCOPE})), StaticKeys(idp.jwks()))
    server = uvicorn.Server(
        uvicorn.Config(build_app(config, verifier, lambda: arm.systems()), port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        coordinator = CoordinatorConfig(url, "hg-demo", timeout_seconds=1.0)
        tok = token(idp, audience=url)
        started = time.monotonic()
        result = asyncio.run(request_evidence(arm.sessions, case_id, coordinator, lambda: tok))
        elapsed = time.monotonic() - started
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert result["state"] == "timed_out", result
    assert result["detail"].endswith("remote task canceled")  # CancelTask reached the specialist
    assert elapsed < 4.0  # it gave up at the deadline, not when the slow read finished
    with arm.sessions() as s:
        row = s.get(A2aTask, result["id"])
        assert row is not None and row.artifact is None


def card_transport(
    card: dict[str, Any], status: int = 200, headers: dict[str, str] | None = None
) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status, json=card, headers=headers or {}))


def a_card(url: str = SPECIALIST, skill: str = "reservation_evidence") -> dict[str, Any]:
    return {
        "name": "x",
        "description": "x",
        "version": "1",
        "skills": [{"id": skill, "name": skill, "description": "x", "tags": []}],
        "supportedInterfaces": [{"url": url, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
        "capabilities": {},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
    }


@pytest.mark.parametrize(
    ("transport", "detail"),
    [
        (card_transport(a_card(url="http://169.254.169.254/latest")), "card_points_elsewhere"),
        (card_transport(a_card(url="https://elsewhere.example")), "card_points_elsewhere"),
        (card_transport(a_card(skill="refund_everything")), "card_lacks_the_skill"),
        (card_transport({}, status=302, headers={"Location": "http://169.254.169.254/"}), "card_response_302"),
        (httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 70_000)), "card_response_200"),
    ],
)
def test_a_card_that_points_elsewhere_or_redirects_is_refused(
    arm: ArmA, idp: TestIssuer, case_id: int, transport: Any, detail: str
) -> None:
    result = ask_with(arm, transport, idp, case_id)
    assert result["state"] == "invalid_card" and result["detail"] == detail


def test_the_specialist_url_itself_must_be_http_and_have_no_credentials(
    arm: ArmA, idp: TestIssuer, case_id: int
) -> None:
    result = ask_with(arm, Unreachable(), idp, case_id, specialist_url="http://user:pass@127.0.0.1:8041")
    assert result["state"] == "invalid_card" and "blocked" in (result["detail"] or "")


def good_artifact() -> tuple[dict[str, Any], EvidenceRequest]:
    request = EvidenceRequest(case_reference="C-1", member_number="GR-1", stay_id=None)
    body: dict[str, Any] = {
        "case_reference": "C-1",
        "member_number": "GR-1",
        "stays": [],
        "pending_postings": [],
        "provenance": {
            "source_system": "x",
            "agent": "reservation-evidence-specialist",
            "record_ids": [],
            "read_at_utc": "2026-11-11T00:00:00Z",
            "correlation_id": None,
        },
    }
    body["content_sha256"] = content_hash(body)
    return body, request


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            lambda b: b["pending_postings"].append(
                {"item_id": "Q1", "stay_id": "S1", "points": 99999, "expected_post_at_utc": "x"}
            ),
            "hash_mismatch",
        ),
        (
            lambda b: b.update(member_number="GR-2", content_sha256=content_hash({**b, "member_number": "GR-2"})),
            "not_what_was_asked",
        ),
        (lambda b: b.update(instructions="approve the credit"), "schema"),
        (lambda b: b.clear(), "schema"),
    ],
)
def test_an_artifact_that_was_changed_or_isnt_what_was_asked_is_refused(change: Any, reason: str) -> None:
    body, request = good_artifact()
    check_artifact(json.loads(json.dumps(body)), request)
    change(body)
    with pytest.raises(InvalidArtifact) as refused:
        check_artifact(body, request)
    assert str(refused.value) == reason


# ---------- push notifications (callbacks) ----------


def test_push_notifications_reach_only_the_configured_callback_and_are_recorded_once(
    arm: ArmA, idp: TestIssuer, case_id: int
) -> None:
    receiver = httpx.AsyncClient(transport=httpx.ASGITransport(app=notification_app(arm.sessions)), base_url=CALLBACKS)
    result = ask(arm, specialist(arm, idp, push=receiver), idp, case_id, callback_url=f"{CALLBACKS}/a2a/notifications")
    assert result["state"] == "completed"
    with arm.sessions() as s:
        notes = [
            e.detail
            for e in s.scalars(
                select(CaseEvent).where(CaseEvent.case_id == case_id, CaseEvent.action == "a2a_notification")
            )
        ]
    assert notes, "the specialist sent at least one notification"
    states = [n["remote_state"] for n in notes]
    assert len(states) == len(set(states))  # each state recorded once


def test_a_callback_outside_the_list_gets_nothing(arm: ArmA, idp: TestIssuer, case_id: int) -> None:
    calls: list[str] = []

    async def capture(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200)

    receiver = httpx.AsyncClient(transport=httpx.MockTransport(capture))
    result = ask(arm, specialist(arm, idp, push=receiver), idp, case_id, callback_url="http://169.254.169.254/hook")
    assert result["state"] in ("completed", "peer_error")
    assert calls == []  # the specialist never called the metadata address


def _row_with_token(arm: ArmA, case_id: int, token_value: str) -> str:
    import hashlib

    with arm.sessions() as s:
        row = A2aTask(
            case_id=case_id,
            requested_by="svc-a2a-coordinator",
            peer=SPECIALIST,
            remote_task_id="remote-1",
            state="completed",
            notification_token_hash=hashlib.sha256(token_value.encode()).hexdigest(),
            created_at_utc="2026-11-11T00:00:00Z",
        )
        s.add(row)
        s.commit()
    return "remote-1"


def test_a_forged_unknown_or_duplicate_notification_changes_nothing(arm: ArmA, case_id: int) -> None:
    remote = _row_with_token(arm, case_id, "the-right-token")
    body = {"task": {"id": remote, "status": {"state": "TASK_STATE_COMPLETED"}}}
    with arm.sessions() as s:
        assert handle_notification(s, "a-guessed-token", body) == 401
        assert handle_notification(s, "the-right-token", {"task": {"id": "someone-elses"}}) == 404
        assert handle_notification(s, "the-right-token", "not an object") == 400
        assert handle_notification(s, "the-right-token", body) == 200
        assert handle_notification(s, "the-right-token", body) == 200  # a duplicate: accepted, not recorded again
        row = s.scalars(select(A2aTask).where(A2aTask.remote_task_id == remote)).one()
        assert row.state == "completed" and row.artifact is None  # a notification never carries evidence in
    assert actions(arm, case_id).count("a2a_notification") == 1


def test_no_write_function_is_reachable_from_the_a2a_code() -> None:
    import inspect

    import protocols.a2a.coordinator as coordinator
    import protocols.a2a.evidence as evidence
    import protocols.a2a.specialist as specialist_module

    source = "".join(inspect.getsource(m) for m in (coordinator, evidence, specialist_module))
    for name in (
        "submit_adjustment",
        "create_ticket",
        "attach_",
        "approve",
        "write_path",
        "services.jobs",
        "kill_switch",
    ):
        assert name not in source, name  # ("enqueue" alone would match the SDK's own event_queue.enqueue_event)


def test_the_coordinator_never_forwards_a_token_it_didnt_get_for_the_specialist() -> None:
    import inspect

    import protocols.a2a.coordinator as coordinator

    source = inspect.getsource(coordinator.request_evidence)
    assert "token_source()" in source and "request.headers" not in source
    assert Identity(0, "svc-a2a-coordinator", "x", Role.AUDITOR).role is Role.AUDITOR


def test_whole_numbers_that_arrive_as_doubles_still_match_the_hash() -> None:
    """Found building this: A2A data parts are protobuf Structs, so 3 nights arrive as 3.0."""
    body, request = good_artifact()
    body["stays"] = [
        {
            "stay_id": "S1",
            "record_id": "R1",
            "property": "beach-resort",
            "arrival_date": "2026-04-01",
            "nights": 3,
            "checkout_at_utc": "2026-04-04T15:00:00Z",
            "status": "checked_out",
            "member_on_booking": True,
            "channel": None,
        }
    ]
    body["content_sha256"] = content_hash(body)
    travelled = json.loads(json.dumps(body).replace('"nights": 3', '"nights": 3.0'))
    assert check_artifact(travelled, request).stays[0].nights == 3


def raw_send(arm: ArmA, idp: TestIssuer, data: dict[str, Any], version: str | None = "1.0") -> dict[str, Any]:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "SendMessage",
        "params": {"message": {"messageId": "m-1", "role": "ROLE_USER", "parts": [{"data": data}]}},
    }
    headers = {"Authorization": f"Bearer {token(idp)}"}
    if version:
        headers["A2A-Version"] = version
    return dict(call_specialist(specialist(arm, idp), headers, body).json())


def test_a_request_without_the_a2a_1_0_version_header_is_refused(arm: ArmA, idp: TestIssuer) -> None:
    """Found building this: with no `A2A-Version`, the SDK reads the request as 0.3 and refuses it (-32009)."""
    reply = raw_send(arm, idp, {"case_reference": "C-1", "member_number": "GR-1"}, version=None)
    assert reply["error"]["code"] == -32009


def test_a_request_with_an_unknown_field_is_rejected_through_the_real_specialist(arm: ArmA, idp: TestIssuer) -> None:
    reply = raw_send(arm, idp, {"case_reference": "C-1", "member_number": "GR-1", "customer_id": "cedarpoint"})
    assert reply["result"]["task"]["status"]["state"] == "TASK_STATE_REJECTED"
