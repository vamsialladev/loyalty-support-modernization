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
| A2A | `protocols/a2a/specialist.py`, `a2a-sdk` 1.3.0, A2A 1.0 | A2A TCK (`a2aproject/a2a-tck`) | JSON-RPC over HTTP | Agent Card, SendMessage, GetTask, CancelTask | **NOT RUN:** it means cloning and installing the TCK, which needs the owner's OK (asked 2026-11-11) | — |
| AG-UI | `protocols/ag_ui/`, `ag-ui-protocol` 1.0.0, AG-UI 1.0 | `@ag-ui/client` (TypeScript) | HTTP POST + SSE | RunAgentInput, 11 event types | **NOT RUN:** it means installing an npm package, which needs the owner's OK (asked 2026-11-11). Our own browser panel reads the stream in Chromium (`tests/browser/test_ag_ui_panel.py`), but that's our client, not an independent one | — |

## G.13 checks, per protocol

| Check | MCP | A2A | AG-UI |
|---|---|---|---|
| Schema validation | Pass: closed input schemas; extra or bad arguments refused (`tests/test_mcp_server.py`) | Pass: the artifact's exact schema; extra fields refused (`tests/test_a2a.py`) | Pass: every streamed event is an AG-UI 1.0 `EventType`; the inbound body must be a `RunAgentInput` with no extra fields (`tests/test_ag_ui.py`) |
| Version compatibility | Pass: 2026-07-28 and a 2025-11-25 client through its handshake (same SDK; `tests/test_mcp_server.py`) | Pass: A2A 1.0 via `A2A-Version`; a request without it is read as 0.3 and refused (found building; `tests/test_a2a.py`) | AG-UI 1.0 only; the 1.1 draft isn't used. No `protocolVersion` is sent, which 1.0 peers expect (`tests/test_ag_ui.py`) |
| Initialization and negotiation | Pass: `server/discover` for 2026-07-28, `initialize` for 2025-11-25 (same SDK; `tests/test_mcp_server.py`) | Pass: Agent Card discovery from the configured URL only; a card pointing elsewhere is refused (`tests/test_a2a.py`) | Not applicable: AG-UI starts with the POST; `threadId` must be the case reference (`tests/test_ag_ui.py`) |
| Authentication failures | Pass: no token, malformed, expired, wrong audience, wrong issuer → 401 with metadata URL (`tests/test_mcp_server.py`) | Pass: no token, malformed, expired, wrong issuer, an MCP token → 401 (`tests/test_a2a.py`) | Pass: no console session → 401 (`tests/test_ag_ui.py`) |
| Insufficient permissions | Pass: no `loyalty.read` → 403 `insufficient_scope`; case tool hidden and refused without `loyalty.case.read` (`tests/test_mcp_server.py`) | Pass: wrong scope → 403; another customer's token → task rejected (`tests/test_a2a.py`) | Pass: starting needs the CSRF token and a case worker; an auditor can watch but not start (`tests/test_ag_ui.py`) |
| Malformed input | Pass: bad JSON → -32700; bad `case_id` → `invalid_arguments` (`tests/test_mcp_server.py`) | Pass: a request with an unknown field (`customer_id`) is rejected by the real specialist, not guessed (`tests/test_a2a.py`) | Pass: wrong `threadId`, missing fields, extra fields, a non-object → 422 (`tests/test_ag_ui.py`) |
| Unsupported features | Pass: unknown version → 400, -32022 with the supported list; unknown and write tools → `unknown_tool` (`tests/test_mcp_server.py`) | Not run: streaming, gRPC and `ListTasks` aren't offered, and the card says so | By design: client tools, messages, state and interrupts aren't used; the server is the source of truth (`protocols/ag_ui/routes.py`) |
| Stream interruption | Not applicable: stateless JSON responses, no stream | Not applicable: no streaming offered | Pass: the window closes with `RUN_ERROR`, never a made-up `RUN_FINISHED` (`tests/test_ag_ui.py`) |
| Cancellation | Not applicable: every tool is a short read with no stream | Pass: on timeout the coordinator sends `CancelTask` and it reaches the specialist (real socket; `tests/test_a2a.py`) | Cancelling the investigation stays on the console's form; closing the stream only stops watching |
| Duplicates | By design, no test: every tool is a read, marked idempotent | Pass: one open task per case, enforced by a partial unique index (`tests/test_a2a.py`, `tests/test_a2a_postgres.py` on CI); duplicate notifications recorded once | Pass: no step sent twice in a stream; resending a `runId` or reconnecting never starts a second investigation (`tests/test_ag_ui.py`, `tests/browser/test_ag_ui_panel.py`) |
| Timeouts and unavailable peers | Upstream errors come back as `unavailable` or `system_error` (arm C's tool tests, `tests/test_ai_tools.py`) | Pass: `timed_out` and `peer_unavailable`, case unchanged (`tests/test_a2a.py`) | Pass: a bounded watch window (`tests/test_ag_ui.py`) |
| Replay | A replayed token works until it expires (TD-49); calls are reads | Pass for notifications: a guessed token 401, another task's ID 404 (`tests/test_a2a.py`). Tokens: TD-49 | A reconnect is a new run that replays stored steps from the start: AG-UI 1.0 has no resume (`tests/test_ag_ui.py`) |
| Expired credentials | Pass: 401 (`tests/test_mcp_server.py`, `tests/test_protocol_auth.py`) | Pass: 401 (`tests/test_a2a.py`) | The console session's own expiry applies (Milestone 9 tests) |
| State recovery | Not applicable: stateless, no sessions | Task state is in `a2a_tasks`, so a restart keeps it (`tests/test_a2a_postgres.py`, on CI) | Pass: events come from stored rows, so a new viewer sees the whole run (`tests/test_ag_ui.py`) |
| Cross-record access | Pass: another customer's case and another member's stay are `not_found` (`tests/test_mcp_server.py`) | Pass: another customer's case isn't found; the artifact must be about the member asked for (`tests/test_a2a.py`) | Pass: another customer's case is 404 (`tests/test_ag_ui.py`) |
