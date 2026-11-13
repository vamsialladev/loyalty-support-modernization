"""The MCP server against an independent client: the official MCP Inspector's CLI (spec G.3, G.13; Appendix C, M11).

Opt in, because it downloads a pinned Node package and needs Node:

    $env:RUN_INTEROP = "1"; uv run pytest tests/interop/test_mcp_inspector.py -s

The server runs as a real HTTP server on a free local port, with real synthetic cases. The Inspector is not our code
and doesn't share our SDK: it's the TypeScript client the MCP project publishes. The test records the protocol
version the Inspector sent, so the report can say exactly what was checked. Tokens are signed by a test key made for
this run; the real-Keycloak token check is `security/evidence/protocol-token-check-2026-11-11.txt`.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from protocols.common.tokens import ResourceServer, StaticKeys, TokenVerifier
from protocols.mcp.server import McpConfig, build_app, build_server
from protocols.mcp.tools import McpReader
from tests.arm_a import ArmA, make_arm_a
from tests.conftest import ROOT
from tests.protocol_tokens import ISSUER, TestIssuer
from tests.test_mcp_server import case_id  # noqa: F401  (fixture reuse: pytest finds it by this name)

INSPECTOR = "@modelcontextprotocol/inspector@2.14.0"
EVIDENCE = ROOT / "security" / "evidence" / "mcp-inspector-run.txt"

pytestmark = [
    pytest.mark.interop,
    pytest.mark.skipif(os.environ.get("RUN_INTEROP") != "1", reason="opt-in: set RUN_INTEROP=1 (needs Node and npx)"),
    pytest.mark.skipif(shutil.which("npx") is None, reason="npx isn't installed"),
]


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Recorder:
    """Wraps the app to note each request's MCP version header and method, and nothing else (no tokens)."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.seen: list[tuple[str, str, str]] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            self.seen.append((headers.get("mcp-protocol-version", "-"), headers.get("mcp-method", "-"), scope["path"]))
        await self.app(scope, receive, send)


def inspector(url: str, token: str, *args: str) -> subprocess.CompletedProcess[str]:
    command = ["npx", "-y", INSPECTOR, "--cli", url, "--transport", "http"]
    command += ["--header", f"Authorization: Bearer {token}", *args]
    return subprocess.run(  # a fixed command: the pinned package and a local URL
        command, capture_output=True, text=True, timeout=300, shell=os.name == "nt", check=False
    )


def test_the_mcp_inspector_lists_and_calls_tools(arm: ArmA, case_id: int) -> None:  # noqa: F811  (the fixture)
    port = free_port()
    url = f"http://127.0.0.1:{port}/mcp"
    idp = TestIssuer()
    config = McpConfig(url, ISSUER, port=port)
    verifier = TokenVerifier(
        ResourceServer("mcp", ISSUER, url, frozenset({"loyalty.read", "loyalty.case.read"})),
        StaticKeys(idp.jwks()),
        require_any_scope=False,
    )
    recorder = Recorder(build_app(build_server(McpReader(arm.sessions, arm.factory()), verifier, config), config))
    server = uvicorn.Server(uvicorn.Config(recorder, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    try:
        read_only = idp.token(audience=url, scope="loyalty.read", expires_in=600)
        listed = inspector(url, read_only, "--method", "tools/list")
        called = inspector(
            url, read_only, "--method", "tools/call", "--tool-name", "get_member", "--tool-arg", f"case_id={case_id}"
        )
        other = idp.token(audience=url, scope="loyalty.read", customer_id="cedarpoint", expires_in=600)
        foreign = inspector(
            url, other, "--method", "tools/call", "--tool-name", "get_member", "--tool-arg", f"case_id={case_id}"
        )
        expired = inspector(url, idp.token(audience=url, expires_in=-120), "--method", "tools/list")
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    names = [t["name"] for t in json.loads(listed.stdout)["tools"]]
    member = json.loads(called.stdout)
    node = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False).stdout.strip()
    versions = sorted({v for v, _, path in recorder.seen if path == "/mcp" and v != "-"})
    lines = [
        "MCP server against the MCP Inspector CLI (an independent client; spec G.3, Appendix C M11)",
        f"Date: {datetime.now(UTC).date().isoformat()}",
        "Command: $env:RUN_INTEROP='1'; uv run pytest tests/interop/test_mcp_inspector.py -s",
        f"Client: {INSPECTOR} (npx, Node {node})",
        "Server: protocols/mcp/server.py on mcp 2.3.0, Streamable HTTP, stateless, JSON responses, 127.0.0.1",
        f"Protocol versions the Inspector sent (MCP-Protocol-Version header): {', '.join(versions) or 'none sent'}",
        f"Methods the Inspector sent: {', '.join(sorted({m for _, m, _ in recorder.seen if m != '-'})) or 'none'}",
        "Tokens: signed by a key made for this run (scope loyalty.read); not Keycloak",
        "",
        f"tools/list, scope loyalty.read: exit {listed.returncode}; tools = {names}",
        f"tools/call get_member, own customer: exit {called.returncode}; isError = {member.get('isError', False)}; "
        f"confirmed = {member.get('structuredContent', {}).get('confirmed')}",
        f"tools/call get_member, another customer's token: exit {foreign.returncode}; "
        f"says not_found = {'not_found' in foreign.stdout + foreign.stderr}",
        f"tools/list, expired token: exit {expired.returncode} (non-zero expected: the server answered 401)",
    ]
    EVIDENCE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    assert listed.returncode == 0, listed.stderr[-2000:]
    assert names == ["get_member", "get_stay", "get_points_ledger", "search_policy", "evaluate_eligibility"]
    assert called.returncode == 0 and not member.get("isError") and member["structuredContent"]["confirmed"] is True
    assert "not_found" in foreign.stdout + foreign.stderr
    assert expired.returncode != 0
