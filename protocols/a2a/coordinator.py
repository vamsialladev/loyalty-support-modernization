"""The loyalty investigation coordinator: asks the reservation specialist for evidence on one case (spec G.4).

    FEATURE_A2A=true uv run python -m protocols.a2a.coordinator --case 12

What it does, in order, and why each step is there:

1. Reads the case as its own read-only service identity, inside its customer. No confirmed member means nothing to
   ask, so no call is made.
2. Keeps one active A2A task per case (`a2a_tasks`, migration 0011): a second request while one is open gets the
   open one back, so a retry can't send a duplicate.
3. Fetches the Agent Card **only from the configured specialist URL**, without redirects and with size and time
   limits, and refuses a card whose JSON-RPC endpoint points at another host. A card describes; it isn't trusted.
4. Calls the specialist with **its own** token for the specialist's audience. It never forwards a token it received.
5. Times out, cancels the remote task, and records "timed out"; an unreachable peer is "peer unavailable". Either
   way the case is unchanged.
6. Checks the artifact (exact schema, content hash, the member and stay it asked about) and records it as evidence
   for a person to review. Nothing here changes the engine's inputs, the case state, or anything with money in it.

Push notifications, if configured, carry a per-task token that's stored only as a hash and checked in constant time;
they're recorded for the audit trail, duplicates are ignored, and the artifact is taken only from the authenticated
response, never from a notification.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
from a2a.client import ClientConfig, create_client
from a2a.helpers import new_data_message
from a2a.types import (
    AgentCard,
    CancelTaskRequest,
    GetTaskRequest,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    TaskPushNotificationConfig,
    TaskState,
)
from google.protobuf.json_format import MessageToDict, ParseDict, ParseError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app import correlation
from app.clock import utc_now
from app.domain.roles import Identity, NotPermitted
from app.domain.roles import Role as StaffRole
from app.outbound import BlockedUrl, check_url
from app.persistence.models import A2aTask, Case
from app.services import conventional
from app.services.cases import CaseNotFound, get_case
from app.services.instrumentation import record
from protocols.a2a.evidence import EvidenceRequest, InvalidArtifact, check_artifact
from protocols.a2a.specialist import CARD_PATH, SKILL
from protocols.common.tokens import same_secret

log = logging.getLogger("protocols.a2a.coordinator")
MAX_CARD_BYTES = 64_000
SUBMITTED = "submitted"
FINAL = {
    TaskState.TASK_STATE_COMPLETED: "completed",
    TaskState.TASK_STATE_FAILED: "failed",
    TaskState.TASK_STATE_CANCELED: "canceled",
    TaskState.TASK_STATE_REJECTED: "rejected",
}
TokenSource = Callable[[], str]
POLL_SECONDS = 0.2


def _state(task: dict[str, Any]) -> Any:
    return TaskState.Value(task.get("status", {}).get("state", "TASK_STATE_UNSPECIFIED"))


def _remember_remote_id(sessions: sessionmaker[Session], row_id: int, remote_id: str) -> None:
    with sessions() as s:
        live = s.get(A2aTask, row_id)
        if live is not None and not live.remote_task_id and remote_id:
            live.remote_task_id = remote_id[:64]
            s.commit()


@dataclass(frozen=True)
class CoordinatorConfig:
    specialist_url: str
    customer_id: str
    timeout_seconds: float = 10.0
    callback_url: str | None = None  # where the specialist may push task updates; None = no push


def coordinator_identity(customer_id: str) -> Identity:
    return Identity(0, "svc-a2a-coordinator", "A2A loyalty coordinator", StaffRole.AUDITOR, customer_id)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _snapshot(row: A2aTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "state": row.state,
        "remote_task_id": row.remote_task_id,
        "artifact_sha256": row.artifact_sha256,
        "detail": row.detail,
    }


class CardRefused(Exception):
    pass


async def fetch_card(http: httpx.AsyncClient, config: CoordinatorConfig) -> AgentCard:
    url = config.specialist_url.rstrip("/") + CARD_PATH
    try:
        check_url(url, (config.specialist_url,))
        response = await http.get(url, follow_redirects=False)
    except BlockedUrl as refused:
        raise CardRefused(f"blocked:{refused}") from refused
    if response.status_code != 200 or len(response.content) > MAX_CARD_BYTES:
        raise CardRefused(f"card_response_{response.status_code}")
    try:
        card: AgentCard = ParseDict(response.json(), AgentCard(), ignore_unknown_fields=True)
    except (ParseError, ValueError) as exc:
        raise CardRefused("card_unreadable") from exc
    if SKILL not in {skill.id for skill in card.skills}:
        raise CardRefused("card_lacks_the_skill")
    expected = (urlsplit(config.specialist_url).hostname, urlsplit(config.specialist_url).port)
    endpoints = [i for i in card.supported_interfaces if i.protocol_binding == "JSONRPC"]
    if not endpoints or any((urlsplit(i.url).hostname, urlsplit(i.url).port) != expected for i in endpoints):
        raise CardRefused("card_points_elsewhere")  # a card can't send us to another host
    return card


def _open_task(
    s: Session, who: Identity, case_id: int, config: CoordinatorConfig, token_hash: str | None
) -> tuple[A2aTask, Any, bool]:
    """The case's open task (reused) or a new one. Returns (row, request, is_new)."""
    case = get_case(s, who, case_id)
    active = s.scalars(select(A2aTask).where(A2aTask.case_id == case.id, A2aTask.state == SUBMITTED)).first()
    rec = conventional.latest_recommendation(s, case)
    request = None
    if rec is not None and rec.member_number:
        request = EvidenceRequest(case_reference=case.reference, member_number=rec.member_number, stay_id=rec.stay_id)
    if active is not None:
        return active, request, False
    row = A2aTask(
        case_id=case.id,
        requested_by=who.username,
        peer=config.specialist_url,
        state=SUBMITTED if request else "rejected",
        detail=None if request else "no_confirmed_member",
        notification_token_hash=token_hash
        if request
        else None,  # stored before sending: notifications can arrive first
        correlation_id=correlation.current(),
        created_at_utc=utc_now(),
        finished_at_utc=None if request else utc_now(),
    )
    s.add(row)
    s.flush()
    record(s, case, who, "a2a_evidence_requested", a2a_task=row.id, peer=config.specialist_url, sent=bool(request))
    s.commit()
    return row, request, True


def _finish(s: Session, who: Identity, row_id: int, state: str, detail: str | None, **values: Any) -> dict[str, Any]:
    row = s.get(A2aTask, row_id)
    assert row is not None
    row.state, row.detail, row.finished_at_utc = state, (detail or "")[:120] or None, utc_now()
    for key, value in values.items():
        setattr(row, key, value)
    case = s.get(Case, row.case_id)
    assert case is not None
    record(
        s,
        case,
        who,
        "a2a_evidence_received" if state == "completed" else "a2a_evidence_not_received",
        a2a_task=row.id,
        state=state,
        detail=row.detail,
        remote_task_id=row.remote_task_id,
        artifact_sha256=row.artifact_sha256,
    )
    s.commit()
    return _snapshot(row)


async def request_evidence(
    sessions: sessionmaker[Session],
    case_id: int,
    config: CoordinatorConfig,
    token_source: TokenSource,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """`transport` is for tests (an in-process specialist); by default it's a real HTTP connection."""
    who = coordinator_identity(config.customer_id)
    notification_token = secrets.token_urlsafe(24) if config.callback_url else None
    token_hash = _hash(notification_token) if notification_token else None
    with correlation.correlated(correlation.new_id()):
        with sessions() as s:
            try:
                row, request, is_new = _open_task(s, who, case_id, config, token_hash)
            except (CaseNotFound, NotPermitted):
                return {"state": "not_found", "case_id": case_id}
            if not is_new or request is None:
                return _snapshot(row)
            row_id = row.id
        try:
            async with httpx.AsyncClient(transport=transport, timeout=config.timeout_seconds) as http:
                card = await fetch_card(http, config)
        except CardRefused as refused:
            with sessions() as s:
                return _finish(s, who, row_id, "invalid_card", str(refused))
        except httpx.HTTPError as exc:
            with sessions() as s:
                return _finish(s, who, row_id, "peer_unavailable", type(exc).__name__)
        authed = httpx.AsyncClient(
            transport=transport,
            headers={"Authorization": f"Bearer {token_source()}"},  # our own token: nothing received is forwarded
            timeout=config.timeout_seconds,
            follow_redirects=False,
        )
        client = await create_client(agent=card, client_config=ClientConfig(streaming=False, httpx_client=authed))
        message = new_data_message(request.model_dump(), role=Role.ROLE_USER)
        # Return at once with the task, then poll: we always know the remote task ID, so a timeout can cancel it.
        configuration = SendMessageConfiguration(accepted_output_modes=["application/json"], return_immediately=True)
        if config.callback_url and notification_token:
            configuration.task_push_notification_config.CopyFrom(
                TaskPushNotificationConfig(url=config.callback_url, token=notification_token)
            )
        remote: dict[str, Any] = {}
        try:
            async with asyncio.timeout(config.timeout_seconds):
                async for event in client.send_message(
                    SendMessageRequest(message=message, configuration=configuration)
                ):
                    body = MessageToDict(event[0] if isinstance(event, tuple) else event)
                    if "task" in body:
                        remote = body["task"]
                        _remember_remote_id(sessions, row_id, str(remote.get("id", "")))
                # A send can return while the task is still working: poll GetTask until it's final or time runs out.
                while remote.get("id") and _state(remote) not in FINAL:
                    await asyncio.sleep(POLL_SECONDS)
                    remote = MessageToDict(await client.get_task(GetTaskRequest(id=remote["id"])))
        except TimeoutError:
            canceled = False
            if remote.get("id"):
                try:
                    await client.cancel_task(CancelTaskRequest(id=remote["id"]))
                    canceled = True
                except Exception:
                    log.info("cancel after timeout failed for remote task %s", remote["id"])
            note = "remote task canceled" if canceled else "remote task not canceled"
            with sessions() as s:
                return _finish(s, who, row_id, "timed_out", f"no answer in {config.timeout_seconds:g}s; {note}")
        except (httpx.HTTPError, OSError) as exc:
            with sessions() as s:
                return _finish(s, who, row_id, "peer_unavailable", type(exc).__name__)
        except Exception as exc:
            with sessions() as s:
                return _finish(s, who, row_id, "peer_error", type(exc).__name__)
        finally:
            await client.close()
            await authed.aclose()
        state = FINAL.get(_state(remote), "failed")
        if state != "completed":
            with sessions() as s:
                return _finish(s, who, row_id, state, "the specialist didn't complete the task")
        data = next((p["data"] for a in remote.get("artifacts", []) for p in a.get("parts", []) if "data" in p), None)
        try:
            artifact = check_artifact(data, request)
        except InvalidArtifact as invalid:
            with sessions() as s:
                return _finish(s, who, row_id, "invalid_artifact", str(invalid))
        with sessions() as s:
            return _finish(
                s,
                who,
                row_id,
                "completed",
                f"{len(artifact.stays)} stays, {len(artifact.pending_postings)} queued postings",
                artifact=json.loads(artifact.model_dump_json()),
                artifact_sha256=artifact.content_sha256,
            )


def handle_notification(s: Session, token: str, body: Any) -> int:
    """A push notification from the specialist. Returns the HTTP status. Authenticated by the per-task token, matched
    to a task we created, recorded once; the state and artifact on our side don't change because of it."""
    if not isinstance(body, dict):
        return 400
    task = body.get("task") or {}
    update = body.get("statusUpdate") or {}
    remote_id = str(task.get("id") or update.get("taskId") or "")[:64]
    if not remote_id:
        return 400
    if not token:
        return 401
    row = s.scalars(select(A2aTask).where(A2aTask.notification_token_hash == _hash(token))).first()
    if row is None or not same_secret(_hash(token), row.notification_token_hash or ""):
        return 401  # not a token we issued
    if row.remote_task_id is None:
        row.remote_task_id = remote_id  # the first notification can arrive before the reply naming the task
    elif row.remote_task_id != remote_id:
        return 404  # A2A §13.2: the task ID must be one we created with this token
    remote_state = str((task.get("status") or update.get("status") or {}).get("state", ""))[:40]
    case = s.get(Case, row.case_id)
    assert case is not None
    seen = {(e.detail or {}).get("remote_state") for e in _notifications(s, row)}
    if remote_state not in seen:  # A2A: duplicates may arrive; handle them idempotently
        record(
            s,
            case,
            coordinator_identity(case.customer_id),
            "a2a_notification",
            a2a_task=row.id,
            remote_state=remote_state,
        )
        s.commit()
    return 200


def _notifications(s: Session, row: A2aTask) -> list[Any]:
    from app.services.instrumentation import events

    case = s.get(Case, row.case_id)
    assert case is not None
    return [e for e in events(s, case) if e.action == "a2a_notification" and (e.detail or {}).get("a2a_task") == row.id]


def notification_app(sessions: sessionmaker[Session]) -> Starlette:
    async def receive(request: Request) -> JSONResponse:
        if int(request.headers.get("content-length", "0") or 0) > 64_000:
            return JSONResponse({"error": "too_large"}, status_code=413)
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({"error": "invalid_json"}, status_code=400)
        token = request.headers.get("x-a2a-notification-token", "")
        with sessions() as s:
            status = await asyncio.to_thread(handle_notification, s, token, body)
        return JSONResponse({"status": status}, status_code=status)

    return Starlette(routes=[Route("/a2a/notifications", receive, methods=["POST"])])


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - the start command
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    from app.persistence.database import make_engine, make_sessions
    from app.settings import AppSettings

    parser = argparse.ArgumentParser(description="Ask the reservation specialist for one case's stay evidence.")
    parser.add_argument("--case", type=int, required=True)
    args = parser.parse_args(argv)
    settings = AppSettings.from_env()
    if not settings.feature_a2a:
        print("FEATURE_A2A is off: the coordinator doesn't run. The core app doesn't need it.")
        return 2
    specialist = os.environ.get("A2A_SPECIALIST_URL", "").strip() or "http://127.0.0.1:8041"
    client_id = os.environ.get("A2A_COORDINATOR_CLIENT_ID", "").strip()
    secret = os.environ.get("A2A_COORDINATOR_CLIENT_SECRET", "")
    if not (client_id and secret and settings.protocol_token_issuer):
        print("A2A_COORDINATOR_CLIENT_ID, A2A_COORDINATOR_CLIENT_SECRET and PROTOCOL_TOKEN_ISSUER must be set.")
        return 2

    def token() -> str:
        response = httpx.post(
            settings.protocol_token_issuer.rstrip("/") + "/protocol/openid-connect/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret},
            timeout=10,
        )
        response.raise_for_status()
        return str(response.json()["access_token"])

    config = CoordinatorConfig(
        specialist, settings.customer_id, callback_url=os.environ.get("A2A_CALLBACK_URL") or None
    )
    sessions = make_sessions(make_engine(settings.database_url))

    result = asyncio.run(request_evidence(sessions, args.case, config, token))
    print(json.dumps(result, indent=2))
    return 0 if result.get("state") == "completed" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
