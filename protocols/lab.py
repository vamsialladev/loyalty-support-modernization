"""What the developer-only Protocol Lab page shows (spec G.13; PROTO-14, Milestone 11 part). Plain data: no SDK import.

Every claim here points at a test or a document in this repo, and an independent run that hasn't happened says NOT RUN.
Each peer result names its evidence file in `security/evidence/`.
Sanitized traces and the lab protocols come with Milestone 16.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.settings import AppSettings


@dataclass(frozen=True)
class LabEntry:
    name: str
    group: str  # spec G.13 status group
    spec: str
    package: str
    transport: str
    capabilities: str
    start: str
    flag: str
    enabled: bool
    peer: str
    peer_result: str
    tests: str
    limits: str


def entries(settings: AppSettings) -> list[LabEntry]:
    return [
        LabEntry(
            "MCP: Model Context Protocol",
            "Core integration",
            "2026-07-28 (2025-11-25 clients served too)",
            "mcp 2.3.0",
            "Streamable HTTP, stateless JSON, 127.0.0.1:8030/mcp",
            "server/discover, tools/list, tools/call: six read-only tools, each for one case",
            "FEATURE_MCP=true uv run python -m protocols.mcp.server",
            "FEATURE_MCP",
            settings.feature_mcp,
            "MCP Inspector CLI 2.14.0",
            "Pass, 2026-11-12: tools/list and tools/call; another customer's token not_found; expired token refused. "
            "The Inspector negotiated 2025-11-25, so the 2026-07-28 path has same-SDK tests only "
            "(security/evidence/mcp-inspector-run.txt)",
            "tests/test_mcp_server.py, tests/test_protocol_auth.py",
            "Per-tool scope errors are tool errors, not HTTP 403; a disabled client's last token lasts until expiry",
        ),
        LabEntry(
            "A2A: Agent2Agent Protocol",
            "Core integration",
            "1.0",
            "a2a-sdk 1.3.0",
            "JSON-RPC over HTTP, 127.0.0.1:8041",
            "Agent Card, SendMessage, GetTask, CancelTask, push notifications to configured hosts",
            "FEATURE_A2A=true uv run python -m protocols.a2a.specialist; ... -m protocols.a2a.coordinator --case <id>",
            "FEATURE_A2A",
            settings.feature_a2a,
            "A2A TCK, commit 70f6f73",
            "Partial, 2026-11-12, JSON-RPC: 57 passed, 5 failed, 201 skipped. Agent card 9 of 9 after a fix. The 5 "
            "failures are TCK scenarios the specialist doesn't act out, by design. The TCK can't send tokens, so the "
            "harness added one (security/evidence/a2a-tck-run.txt)",
            "tests/test_a2a.py, tests/test_a2a_postgres.py",
            "No streaming or gRPC; a lab: REST is enough for this workflow (docs/a2a-vs-rest.md)",
        ),
        LabEntry(
            "AG-UI: Agent-User Interaction Protocol",
            "Core integration",
            "1.0 (1.1 draft not used)",
            "ag-ui-protocol 1.0.0",
            "HTTP POST + SSE, inside the console",
            "RunAgentInput; 11 event types; watch-only panel on arm C cases",
            "FEATURE_AG_UI=true uv run python -m protocols.ag_ui.server",
            "FEATURE_AG_UI",
            settings.feature_ag_ui,
            "@ag-ui/client 1.0.4",
            "Pass, 2026-11-12: watch a finished run, start one, a closed watch window (RUN_ERROR), no session (401) "
            "(security/evidence/ag-ui-client-run.txt)",
            "tests/test_ag_ui.py, tests/browser/test_ag_ui_panel.py",
            "No resume in 1.0: a reconnect replays from the start; the stream polls the database",
        ),
    ]


def any_enabled(settings: AppSettings) -> bool:
    return settings.feature_mcp or settings.feature_a2a or settings.feature_ag_ui
