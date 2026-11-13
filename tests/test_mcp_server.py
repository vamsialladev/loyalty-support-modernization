"""The MCP server (spec G.3, G.13; PROTO-03; ADR-0023; threats T20-T22).

Two layers. `McpReader` is tested directly on real synthetic cases: what each tool returns, scope, customer, limits,
audit. Then the HTTP app is driven through the official SDK's own client, in process, so authentication, the tool
list, and transport checks run as an MCP client meets them. **Same-SDK tests show our code works; they aren't interop
proof.** The independent client run is in `docs/protocol-test-results.md`.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import select

from app.ai.tools import run_tool
from app.domain.roles import Identity, Role
from app.persistence.models import Case, SystemEvent
from app.services import conventional
from app.services.assisted import tool_context_for
from app.services.cases import read_time
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath
from app.worker import Worker
from benchmarks.intake import load_case, read_split
from protocols.common.tokens import ResourceServer, StaticKeys, TokenVerifier
from protocols.mcp import tools as mcp_tools
from protocols.mcp.server import McpConfig, build_app, build_server
from protocols.mcp.tools import CASE_TOOL, McpReader, ToolFailed
from tests.arm_a import ArmA, make_arm_a
from tests.protocol_tokens import ISSUER, MCP_AUDIENCE, TestIssuer

BOTH = frozenset({"loyalty.read", "loyalty.case.read"})
READ_ONLY = frozenset({"loyalty.read"})
CONFIG = McpConfig(MCP_AUDIENCE, ISSUER)


def caller(customer: str = "hg-demo") -> Identity:
    return Identity(0, "svc-mcp-test-client", "mcp client test-client", Role.AUDITOR, customer)


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


@pytest.fixture
def case_id(arm: ArmA) -> int:
    """A K01 case (eligible stay, points missing), investigated by arm B so its member is confirmed."""
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == arm.scenario("K01"))
    with arm.sessions() as s:
        cid = load_case(s, item, arm="B")[0].id
        conventional.start_investigation(s, arm.who("agent.ana"), s.get(Case, cid))  # type: ignore[arg-type]
    Worker(arm.sessions, build_handlers(SharedWritePath("hg-demo"), arm.factory(), None)).drain()
    return cid


@pytest.fixture
def reader(arm: ArmA) -> McpReader:
    return McpReader(arm.sessions, arm.factory())


def stay_of(reader: McpReader, case_id: int) -> str:
    return str(reader.call(caller(), BOTH, "get_stay", {"case_id": case_id})["stays"][0]["stay_id"])


# ---------- the tools, directly ----------


def test_each_tool_returns_exactly_what_arm_cs_model_gets(arm: ArmA, reader: McpReader, case_id: int) -> None:
    stay = stay_of(reader, case_id)
    calls = [
        ("get_member", {}),
        ("get_stay", {"stay_id": stay}),
        ("get_points_ledger", {"stay_id": stay}),
        ("evaluate_eligibility", {"stay_id": stay}),
        ("search_policy", {"stay_id": stay, "query": "missing points"}),
    ]
    with arm.sessions() as s:  # closed before the reader runs: SQLite allows one writer at a time
        case = s.get(Case, case_id)
        assert case is not None
        ctx = tool_context_for(s, caller(), case, arm.factory()(read_time(case)))
        expected = {tool: json.loads(run_tool(tool, args, ctx).content) for tool, args in calls}
    for tool, args in calls:
        assert reader.call(caller(), BOTH, tool, {"case_id": case_id, **args}) == expected[tool], tool
    member = reader.call(caller(), BOTH, "get_member", {"case_id": case_id})
    assert member["confirmed"] is True and set(member) == {
        "confirmed",
        "member_number",
        "first_name",
        "last_name",
        "tier",
        "status",
    }  # no email, phone, address or card: the minimum arm C's model gets


def test_another_customers_case_is_not_found(reader: McpReader, case_id: int) -> None:
    with pytest.raises(ToolFailed) as failed:
        reader.call(caller("cedarpoint"), BOTH, "get_member", {"case_id": case_id})
    assert failed.value.code == "not_found"
    with pytest.raises(ToolFailed) as missing:
        reader.call(caller(), BOTH, "get_member", {"case_id": 999_999})
    assert missing.value.code == "not_found"  # the same answer: a caller can't tell "not yours" from "doesn't exist"


def test_a_stay_that_isnt_this_members_is_not_found(reader: McpReader, case_id: int) -> None:
    with pytest.raises(ToolFailed) as failed:
        reader.call(caller(), BOTH, "get_points_ledger", {"case_id": case_id, "stay_id": "ML-0000"})
    assert failed.value.code == "not_found"


def test_the_case_tool_needs_its_own_scope(reader: McpReader, case_id: int) -> None:
    with pytest.raises(ToolFailed) as failed:
        reader.call(caller(), READ_ONLY, CASE_TOOL, {"case_id": case_id})
    assert failed.value.code == "insufficient_scope"
    with pytest.raises(ToolFailed):
        reader.call(caller(), frozenset({"loyalty.case.read"}), "get_member", {"case_id": case_id})


@pytest.mark.parametrize("bad", [None, "1", 0, -3, True, 1.5])
def test_a_bad_case_id_is_refused(reader: McpReader, bad: Any) -> None:
    with pytest.raises(ToolFailed) as failed:
        reader.call(caller(), BOTH, "get_member", {"case_id": bad})
    assert failed.value.code == "invalid_arguments"


def test_unknown_tools_and_extra_arguments_are_refused(reader: McpReader, case_id: int) -> None:
    for tool in ("submit_recommendation", "submit_adjustment", "execute"):
        with pytest.raises(ToolFailed) as failed:
            reader.call(caller(), BOTH, tool, {"case_id": case_id})
        assert failed.value.code == "unknown_tool"
    with pytest.raises(ToolFailed) as extra:
        reader.call(caller(), BOTH, "get_member", {"case_id": case_id, "member_number": "GR-1"})
    assert extra.value.code == "invalid_arguments"
    with pytest.raises(ToolFailed):
        reader.call(caller(), BOTH, CASE_TOOL, {"case_id": case_id, "include": "snapshots"})


def test_case_evidence_gives_references_and_the_engines_result_only(reader: McpReader, case_id: int) -> None:
    result = reader.call(caller(), BOTH, CASE_TOOL, {"case_id": case_id})
    assert set(result) == {"case_id", "reference", "status", "arm", "received_at_utc", "engine_result", "evidence"}
    assert result["engine_result"]["action"]
    for row in result["evidence"]:
        assert set(row) == {"kind", "source_ref", "attached_at_utc"}  # no snapshot, so no member details
    text = json.dumps(result)
    member = reader.call(caller(), BOTH, "get_member", {"case_id": case_id})
    assert member["last_name"] not in text


def test_every_call_is_audited_with_a_hash_not_the_arguments(arm: ArmA, reader: McpReader, case_id: int) -> None:
    stay = stay_of(reader, case_id)
    reader.call(caller(), BOTH, "get_points_ledger", {"case_id": case_id, "stay_id": stay})
    with pytest.raises(ToolFailed):
        reader.call(caller("cedarpoint"), BOTH, "get_member", {"case_id": case_id})
    with arm.sessions() as s:
        events = list(s.scalars(select(SystemEvent).where(SystemEvent.action == "mcp_call")))
    assert [e.detail["outcome"] for e in events] == ["ok", "ok", "not_found"]
    assert {e.actor_kind for e in events} == {"service"}
    for event in events:
        assert len(event.detail["arguments_hash"]) == 64 and event.detail["correlation_id"]
        assert stay not in json.dumps(event.detail)  # the stay ID is in the arguments, so only its hash is logged


def test_calls_are_rate_limited_per_caller_and_the_refusal_is_audited(arm: ArmA, case_id: int) -> None:
    tight = McpReader(arm.sessions, arm.factory(), per_minute=2)
    for _ in range(2):
        tight.call(caller(), BOTH, CASE_TOOL, {"case_id": case_id})
    with pytest.raises(ToolFailed) as limited:
        tight.call(caller(), BOTH, CASE_TOOL, {"case_id": case_id})
    assert limited.value.code == "rate_limited"
    other = Identity(0, "svc-mcp-other-client", "other", Role.AUDITOR, "hg-demo")
    tight.call(other, BOTH, CASE_TOOL, {"case_id": case_id})  # a different caller has its own allowance
    with arm.sessions() as s:
        outcomes = [e.detail["outcome"] for e in s.scalars(select(SystemEvent).where(SystemEvent.action == "mcp_call"))]
    assert outcomes.count("rate_limited") == 1


def test_no_write_function_is_reachable_from_the_mcp_code() -> None:
    """ADR-0023: MCP never executes adjustments. Nothing that writes is even imported."""
    import protocols.mcp.server as server_module

    source = inspect.getsource(mcp_tools) + inspect.getsource(server_module)
    for name in (
        "submit_adjustment",
        "create_ticket",
        "attach_",
        "approve",
        "execute",
        "enqueue",
        "start_investigation",
        "request_adjustment",
        "kill_switch",
        "text(",
        "open(",
    ):
        assert name not in source, name
    assert set(mcp_tools.TOOL_SCOPES) == {
        "get_member",
        "get_stay",
        "get_points_ledger",
        "search_policy",
        "evaluate_eligibility",
        CASE_TOOL,
    }


# ---------- through the SDK's own client, over HTTP ----------


@pytest.fixture(scope="module")
def idp() -> TestIssuer:
    return TestIssuer()


def run_app(reader: McpReader, idp: TestIssuer, body: Callable[[Any], Awaitable[Any]], token: str | None = None) -> Any:
    verifier = TokenVerifier(
        ResourceServer("mcp", ISSUER, MCP_AUDIENCE, BOTH), StaticKeys(idp.jwks()), require_any_scope=False
    )
    server = build_server(reader, verifier, CONFIG)
    app = build_app(server, CONFIG)

    async def go() -> Any:
        async with server.session_manager.run():
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            http = httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://127.0.0.1:8030", headers=headers
            )
            return await body(http)

    return asyncio.run(go())


def with_client(fn: Callable[[Client], Awaitable[Any]]) -> Callable[[Any], Awaitable[Any]]:
    async def body(http: Any) -> Any:
        async with Client(streamable_http_client(MCP_AUDIENCE, http_client=http)) as client:
            return await fn(client)

    return body


def test_an_mcp_client_lists_only_its_tools_and_reads_a_case(reader: McpReader, idp: TestIssuer, case_id: int) -> None:
    async def flow(client: Client) -> tuple[list[str], Any, Any]:
        listed = await client.list_tools()
        member = await client.call_tool("get_member", {"case_id": case_id})
        refused = await client.call_tool("get_member", {"case_id": case_id + 1000})
        return [t.name for t in listed.tools], member, refused

    names, member, refused = run_app(reader, idp, with_client(flow), idp.token(scope="loyalty.read"))
    assert names == ["get_member", "get_stay", "get_points_ledger", "search_policy", "evaluate_eligibility"]
    assert not member.is_error and member.structured_content["confirmed"] is True
    assert refused.is_error and "not_found" in refused.content[0].text
    with_case = run_app(
        reader,
        idp,
        with_client(lambda c: c.list_tools()),
        idp.token(scope="loyalty.read loyalty.case.read"),
    )
    assert CASE_TOOL in [t.name for t in with_case.tools]


def test_every_tool_is_marked_read_only(reader: McpReader, idp: TestIssuer) -> None:
    listed = run_app(
        reader, idp, with_client(lambda c: c.list_tools()), idp.token(scope="loyalty.read loyalty.case.read")
    )
    for tool in listed.tools:
        assert tool.annotations.read_only_hint is True and tool.annotations.destructive_hint is False
        assert tool.input_schema["required"][0] == "case_id"


def raw(reader: McpReader, idp: TestIssuer, token: str | None, **request: Any) -> Any:
    async def body(http: Any) -> Any:
        return await http.request(
            request.pop("method", "POST"), request.pop("path", "/mcp"), headers=request.pop("headers", {}), **request
        )

    return run_app(reader, idp, body, token)


LIST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}


@pytest.mark.parametrize(
    "token",
    [
        None,
        "not-a-jwt",
        "expired",
        "wrong-audience",
        "wrong-issuer",
    ],
)
def test_requests_without_a_good_token_get_401_with_the_metadata_url(
    reader: McpReader, idp: TestIssuer, token: str | None
) -> None:
    value = {
        "expired": idp.token(expires_in=-120),
        "wrong-audience": idp.token(audience="http://127.0.0.1:8041"),
        "wrong-issuer": idp.token(issuer="http://evil.example/realms/hotel"),
    }.get(token or "", token)
    response = raw(reader, idp, value, json=LIST)
    assert response.status_code == 401
    assert (
        'resource_metadata="http://127.0.0.1:8030/.well-known/oauth-protected-resource/mcp"'
        in (response.headers["www-authenticate"])
    )


def test_a_good_token_without_the_read_scope_gets_403(reader: McpReader, idp: TestIssuer) -> None:
    response = raw(reader, idp, idp.token(scope="openid profile"), json=LIST)
    assert response.status_code == 403
    assert 'error="insufficient_scope"' in response.headers["www-authenticate"]


def test_the_protected_resource_metadata_names_the_issuer(reader: McpReader, idp: TestIssuer) -> None:
    response = raw(reader, idp, None, method="GET", path="/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == MCP_AUDIENCE and body["authorization_servers"] == [ISSUER]


def test_a_foreign_origin_or_host_is_refused(reader: McpReader, idp: TestIssuer) -> None:
    """DNS rebinding: a web page elsewhere can't use a browser to reach this local server."""
    token = idp.token()
    origin = raw(reader, idp, token, json=LIST, headers={"Origin": "http://evil.example"})
    host = raw(reader, idp, token, json=LIST, headers={"Host": "evil.example"})
    assert origin.status_code == 403
    assert host.status_code in (400, 421)


def test_in_a_container_the_public_host_is_allowed_and_the_bind_address_is_not(
    reader: McpReader, idp: TestIssuer
) -> None:
    """Found by the Milestone 12 labs check: bound to 0.0.0.0:8030 in Compose and reached at 127.0.0.1:28030, every
    call got 421 because the allowed host came from the bind address. It now comes from the resource URL."""
    public = "http://127.0.0.1:28030/mcp"
    config = McpConfig(public, ISSUER, host="0.0.0.0", port=8030)  # noqa: S104 - the container's bind address
    verifier = TokenVerifier(
        ResourceServer("mcp", ISSUER, public, BOTH), StaticKeys(idp.jwks()), require_any_scope=False
    )
    server = build_server(reader, verifier, config)
    app = build_app(server, config)
    token = idp.token(audience=public)

    async def go() -> list[int]:
        codes = []
        async with server.session_manager.run():  # one run per server: the SDK refuses a second
            for host in ("127.0.0.1:28030", "0.0.0.0:8030"):
                http = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=f"http://{host}")
                response = await http.post("/mcp", json=LIST, headers={"Authorization": f"Bearer {token}"})
                codes.append(int(response.status_code))
        return codes

    public_host, bind_address = asyncio.run(go())
    assert public_host == 200
    assert bind_address in (400, 421)


def test_the_token_is_never_kept_for_reuse(reader: McpReader, idp: TestIssuer) -> None:
    """No passthrough: what reaches the tools has no copy of the caller's token."""
    from protocols.mcp.server import LoyaltyTokenVerifier

    verifier = TokenVerifier(ResourceServer("mcp", ISSUER, MCP_AUDIENCE, BOTH), StaticKeys(idp.jwks()))
    token = idp.token()
    access = asyncio.run(LoyaltyTokenVerifier(verifier).verify_token(token))
    assert access is not None and access.token != token and token not in json.dumps(access.model_dump())


MODERN = {"MCP-Protocol-Version": "2026-07-28", "Accept": "application/json, text/event-stream"}


def meta(version: str = "2026-07-28") -> dict[str, Any]:
    return {"io.modelcontextprotocol/protocolVersion": version, "io.modelcontextprotocol/clientCapabilities": {}}


def test_an_unsupported_protocol_version_is_refused_as_the_spec_says(reader: McpReader, idp: TestIssuer) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": meta("2099-01-01")}}
    headers = {**MODERN, "MCP-Protocol-Version": "2099-01-01", "Mcp-Method": "tools/list"}
    response = raw(reader, idp, idp.token(), json=body, headers=headers)
    error = response.json()["error"]
    assert response.status_code == 400 and error["code"] == -32022  # UnsupportedProtocolVersionError
    assert error["data"] == {"supported": ["2026-07-28"], "requested": "2099-01-01"}


def test_malformed_json_is_a_parse_error(reader: McpReader, idp: TestIssuer) -> None:
    headers = {**MODERN, "Mcp-Method": "tools/list", "Content-Type": "application/json"}
    response = raw(reader, idp, idp.token(), content=b"{not json", headers=headers)
    assert response.status_code == 400 and response.json()["error"]["code"] == -32700


def test_a_2025_11_25_client_is_served_with_the_same_checks(reader: McpReader, idp: TestIssuer) -> None:
    async def body(http: Any) -> list[str]:
        async with Client(streamable_http_client(MCP_AUDIENCE, http_client=http), mode="legacy") as client:
            return [t.name for t in (await client.list_tools()).tools]

    names = run_app(reader, idp, body, idp.token(scope="loyalty.read"))
    assert CASE_TOOL not in names and "get_member" in names
