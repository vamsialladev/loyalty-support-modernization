# Protocol test results (PROTO-01, PROTO-14)

> Simulated engagement, synthetic data. Every row comes from a test or a recorded run in this repo, with the exact
> version, transport, capability subset and peer. Same-SDK tests show our code works; only a peer we didn't write
> counts as interoperability. Rows are filled in as each protocol's step lands. A row without a result says
> **NOT RUN**.

## Independent client and peer runs

| Protocol | Our side | Peer (exact version) | Transport | Capability subset | Result | Evidence |
|---|---|---|---|---|---|---|
| MCP | `protocols/mcp/server.py`, `mcp` 2.3.0, MCP 2026-07-28 | MCP Inspector CLI 2.14.0 (TypeScript; pinned) | Streamable HTTP | tools/list, tools/call | **NOT RUN:** the run downloads a Node package, which needs the owner's OK (asked 2026-11-11). The test is ready: `tests/interop/test_mcp_inspector.py` | — |
| MCP | `protocols/mcp/server.py` | Claude Code (owner step) | Streamable HTTP | tools/list, tools/call | NOT RUN | — |
| A2A | — | A2A TCK | JSON-RPC over HTTP | Agent Card, SendMessage, GetTask, CancelTask | NOT RUN | — |
| AG-UI | — | `@ag-ui/client` | HTTP POST + SSE | RunAgentInput, 11 event types | NOT RUN | — |

## G.13 checks, per protocol

| Check | MCP | A2A | AG-UI |
|---|---|---|---|
| Schema validation | Pass: closed input schemas; extra or bad arguments refused (`tests/test_mcp_server.py`) | NOT RUN | NOT RUN |
| Version compatibility | Pass: 2026-07-28 and a 2025-11-25 client through its handshake (same SDK; `tests/test_mcp_server.py`) | NOT RUN | NOT RUN |
| Initialization and negotiation | Pass: `server/discover` for 2026-07-28, `initialize` for 2025-11-25 (same SDK; `tests/test_mcp_server.py`) | NOT RUN | NOT RUN |
| Authentication failures | Pass: no token, malformed, expired, wrong audience, wrong issuer → 401 with metadata URL (`tests/test_mcp_server.py`) | NOT RUN | NOT RUN |
| Insufficient permissions | Pass: no `loyalty.read` → 403 `insufficient_scope`; case tool hidden and refused without `loyalty.case.read` (`tests/test_mcp_server.py`) | NOT RUN | NOT RUN |
| Malformed input | Pass: bad JSON → -32700; bad `case_id` → `invalid_arguments` (`tests/test_mcp_server.py`) | NOT RUN | NOT RUN |
| Unsupported features | Pass: unknown version → 400, -32022 with the supported list; unknown and write tools → `unknown_tool` (`tests/test_mcp_server.py`) | NOT RUN | NOT RUN |
| Stream interruption | Not applicable: stateless JSON responses, no stream | NOT RUN | NOT RUN |
| Cancellation | Not applicable: every tool is a short read with no stream | NOT RUN | NOT RUN |
| Duplicates | By design, no test: every tool is a read, marked idempotent | NOT RUN | NOT RUN |
| Timeouts and unavailable peers | Upstream errors come back as `unavailable` or `system_error` (arm C's tool tests, `tests/test_ai_tools.py`) | NOT RUN | NOT RUN |
| Replay | A replayed token works until it expires (TD-49); calls are reads | NOT RUN | NOT RUN |
| Expired credentials | Pass: 401 (`tests/test_mcp_server.py`, `tests/test_protocol_auth.py`) | NOT RUN | NOT RUN |
| State recovery | Not applicable: stateless, no sessions | NOT RUN | NOT RUN |
| Cross-record access | Pass: another customer's case and another member's stay are `not_found` (`tests/test_mcp_server.py`) | NOT RUN | NOT RUN |
