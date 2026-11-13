"""The reservation evidence specialist: an A2A agent the reservations team would run (spec G.4; RFC-0004).

    FEATURE_A2A=true uv run python -m protocols.a2a.specialist

- **Discovery:** an Agent Card at `/.well-known/agent-card.json`, public, because it only says what the agent does and
  how to authenticate. A card describes capabilities; it isn't proof of who runs the agent.
- **Authentication, per request:** an OAuth access token from the configured issuer, with this agent's URL as its
  audience and scope `reservation.evidence`, checked by `protocols.common.tokens`. A2A puts identity in the transport,
  never in the message.
- **Per-task authorization:** the specialist serves one customer's reservation system. A caller from another customer
  gets the task rejected, whatever its message says. It reads only stays on the member's own profile.
- **Lifecycle:** submitted → working → completed with one data artifact, or failed / rejected with a safe message;
  `CancelTask` works while the read is in progress. Push notifications go only to configured callback hosts.
- **Never:** writes, tickets, or another customer's records. It holds no loyalty permission at all.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from a2a.helpers import get_data_parts, new_task_from_user_message, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import DefaultServerCallContextBuilder, create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
    TaskUpdater,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    ClientCredentialsOAuthFlow,
    OAuth2SecurityScheme,
    OAuthFlows,
    Part,
    SecurityRequirement,
    SecurityScheme,
    StringList,
    TaskState,
)
from google.protobuf import struct_pb2
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app import correlation
from app.outbound import BlockedUrl, check_url
from app.ports.customer_systems import CustomerSystemError, CustomerSystems
from protocols.a2a.evidence import EvidenceRequest, gather
from protocols.common.tokens import Caller, TokenRejected, TokenVerifier, bearer, www_authenticate

log = logging.getLogger("protocols.a2a.specialist")
CARD_PATH = "/.well-known/agent-card.json"
SKILL = "reservation_evidence"
SCOPE = "reservation.evidence"
CALLER_KEY = "loyalty_caller"


@dataclass(frozen=True)
class SpecialistConfig:
    url: str  # this agent's base URL: the JSON-RPC endpoint and the token audience
    issuer: str
    customer_id: str  # the one customer whose reservation system this agent reads
    callback_bases: tuple[str, ...] = ()  # push notifications may go only to these hosts
    read_delay_seconds: float = 0.0  # tests only: makes a read slow enough to cancel or time out


def agent_card(config: SpecialistConfig) -> AgentCard:
    token_url = config.issuer.rstrip("/") + "/protocol/openid-connect/token"
    return AgentCard(
        name="Reservation evidence specialist (SYNTHETIC)",
        description=(
            "Reads one loyalty member's stays and queued point postings from the reservation system, with provenance. "
            "Read-only. Simulated hotel group, synthetic data."
        ),
        version="0.1.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False, push_notifications=True),
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=config.url, protocol_version="1.0")],
        skills=[
            AgentSkill(
                id=SKILL,
                name="Reservation evidence",
                description="Stays and queued postings for one member, as a data artifact with provenance.",
                tags=["loyalty", "reservations", "read-only"],
                input_modes=["application/json"],
                output_modes=["application/json"],
            )
        ],
        security_schemes={
            "oauth": SecurityScheme(
                oauth2_security_scheme=OAuth2SecurityScheme(
                    description="Client-credentials access token whose audience is this agent's URL.",
                    flows=OAuthFlows(
                        client_credentials=ClientCredentialsOAuthFlow(
                            token_url=token_url, scopes={SCOPE: "Read reservation evidence"}
                        )
                    ),
                )
            )
        },
        security_requirements=[SecurityRequirement(schemes={"oauth": StringList(list=[SCOPE])})],
    )


class RequireToken:
    """Every request but the card needs a valid token for this agent. The verified caller rides on the ASGI scope;
    the A2A context builder below hands it to the executor."""

    def __init__(self, app: ASGIApp, verifier: TokenVerifier) -> None:
        self.app = app
        self.verifier = verifier

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == CARD_PATH:
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        try:
            caller = await asyncio.to_thread(self.verifier.verify, bearer(headers.get("authorization")))
        except TokenRejected as refused:
            log.info("a2a token refused: %s", refused.reason)
            response = JSONResponse(
                {"error": "invalid_token" if refused.status == 401 else "insufficient_scope"},
                status_code=refused.status,
                headers={"WWW-Authenticate": www_authenticate(refused)},
            )
            await response(scope, receive, send)
            return
        scope[CALLER_KEY] = caller
        await self.app(scope, receive, send)


CARD_CACHE_CONTROL = "public, max-age=300"


class CardCacheControl:
    """A2A 1.0 §8.6.1: the Agent Card response SHOULD carry Cache-Control with max-age. Found by the A2A TCK
    (CARD-CACHE-001). Five minutes, so a changed card reaches clients quickly."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != CARD_PATH:
            await self.app(scope, receive, send)
            return

        async def with_header(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                message = {**message, "headers": [*headers, (b"cache-control", CARD_CACHE_CONTROL.encode())]}
            await send(message)

        await self.app(scope, receive, with_header)


class CallerContextBuilder(DefaultServerCallContextBuilder):
    def build(self, request: Request) -> Any:
        context = super().build(request)
        context.state[CALLER_KEY] = request.scope.get(CALLER_KEY)
        headers = context.state.get("headers", {})
        # The token doesn't travel further; the rest stays (the SDK reads A2A-Version from it).
        context.state["headers"] = {k: v for k, v in headers.items() if k.lower() != "authorization"}
        return context


@dataclass
class EvidenceExecutor(AgentExecutor):
    config: SpecialistConfig
    systems: Callable[[], CustomerSystems]
    reads: dict[str, asyncio.Task[Any]] = field(default_factory=dict)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.message is None and context.current_task is None:
            return  # nothing to answer
        task = context.current_task or new_task_from_user_message(context.message)  # type: ignore[arg-type]
        if not context.current_task:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        caller: Caller | None = context.call_context.state.get(CALLER_KEY) if context.call_context else None
        if caller is None or caller.customer_id != self.config.customer_id:
            # Per-task authorization: the token says who is asking; nothing in the message can change that.
            await updater.update_status(TaskState.TASK_STATE_REJECTED, message=new_text_message("Not permitted."))
            return
        data = next(iter(get_data_parts(context.message.parts)), None) if context.message else None
        try:
            request = EvidenceRequest.model_validate(data if isinstance(data, dict) else {})
        except ValidationError:
            await updater.update_status(TaskState.TASK_STATE_REJECTED, message=new_text_message("Invalid request."))
            return
        await updater.update_status(TaskState.TASK_STATE_WORKING, message=new_text_message("Reading reservations."))
        read = asyncio.create_task(self._read(request, task.context_id))
        self.reads[task.id] = read
        try:
            body = await read
        except asyncio.CancelledError:
            await updater.update_status(TaskState.TASK_STATE_CANCELED, message=new_text_message("Canceled."))
            return
        except CustomerSystemError:
            await updater.update_status(
                TaskState.TASK_STATE_FAILED, message=new_text_message("The reservation system didn't answer.")
            )
            return
        finally:
            self.reads.pop(task.id, None)
        payload = struct_pb2.Struct()
        payload.update(json.loads(json.dumps(body)))
        await updater.add_artifact(
            parts=[Part(data=struct_pb2.Value(struct_value=payload))], name="reservation-evidence"
        )
        await updater.update_status(TaskState.TASK_STATE_COMPLETED, message=new_text_message("Done."))

    async def _read(self, request: EvidenceRequest, context_id: str) -> dict[str, Any]:
        if self.config.read_delay_seconds:
            await asyncio.sleep(self.config.read_delay_seconds)
        with correlation.correlated(context_id[:32]):
            return await asyncio.to_thread(gather, self.systems(), request, context_id[:32])

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        read = self.reads.get(context.task_id or "")
        if read is not None:
            read.cancel()
            return
        task_id = context.task_id or ""
        updater = TaskUpdater(event_queue=event_queue, task_id=task_id, context_id=context.context_id or "")
        await updater.update_status(TaskState.TASK_STATE_CANCELED, message=new_text_message("Canceled."))


def callback_validator(config: SpecialistConfig) -> Callable[[str], Any]:
    """SSRF guard for push notifications: only configured callback hosts, no credentials in the URL (A2A §13.2)."""

    async def allowed(url: str) -> bool:
        try:
            check_url(url, config.callback_bases)
        except BlockedUrl as refused:
            log.info("push notification URL refused: %s", refused)
            return False
        return True

    return allowed


def build_app(
    config: SpecialistConfig,
    verifier: TokenVerifier,
    systems: Callable[[], CustomerSystems],
    push_http: httpx.AsyncClient | None = None,
) -> Starlette:
    card = agent_card(config)
    validator = callback_validator(config)
    configs = InMemoryPushNotificationConfigStore()
    sender = BasePushNotificationSender(
        push_http or httpx.AsyncClient(timeout=5.0, follow_redirects=False), configs, push_url_validator=validator
    )
    handler = DefaultRequestHandler(
        agent_executor=EvidenceExecutor(config, systems),
        task_store=InMemoryTaskStore(),
        agent_card=card,
        push_config_store=configs,
        push_sender=sender,
        push_url_validator=validator,
    )
    routes = [*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/", CallerContextBuilder())]
    app = Starlette(routes=routes)
    app.add_middleware(RequireToken, verifier=verifier)
    app.add_middleware(CardCacheControl)
    return app


def main() -> int:  # pragma: no cover - the start command; tests build the app directly
    import uvicorn

    from app.services.systems import mock_systems_factory
    from app.settings import AppSettings
    from protocols.common.tokens import IssuerKeys, ResourceServer

    settings = AppSettings.from_env()
    if not settings.feature_a2a:
        print("FEATURE_A2A is off: the specialist doesn't start. The core app doesn't need it.")
        return 2
    if not settings.protocol_token_issuer:
        print("PROTOCOL_TOKEN_ISSUER (or OIDC_ISSUER_URL) isn't set: there is no issuer to check tokens against.")
        return 2
    port = int(os.environ.get("A2A_SPECIALIST_PORT", "8041"))
    url = os.environ.get("A2A_SPECIALIST_URL", "").strip() or f"http://127.0.0.1:{port}"
    callbacks = tuple(u for u in os.environ.get("A2A_CALLBACK_BASES", "").split(",") if u.strip())
    config = SpecialistConfig(url, settings.protocol_token_issuer, settings.customer_id, callbacks)
    server = ResourceServer("a2a-specialist", config.issuer, url, frozenset({SCOPE}))
    factory = mock_systems_factory(settings)
    app = build_app(config, TokenVerifier(server, IssuerKeys(config.issuer)), lambda: factory(None))
    uvicorn.run(app, host="127.0.0.1", port=port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
