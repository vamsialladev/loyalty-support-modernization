# Protocol catalog (PROTO-01)

> Simulated engagement, synthetic data. Read from primary sources on **2026-11-11**: specifications, maintainer
> repositories, SDK pages and release notes. Anything not on a page we read says "not found". Status words are the
> maintainers' own; we don't upgrade a draft to a standard.

Milestone 11 builds the three **core** protocols. The labs (Milestone 16) get a row here with their official source
and status, and their full record when they're built. **"ACP" is always spelled out:** there are three.

## Core protocols (built in Milestone 11)

### MCP: Model Context Protocol
| Field | Record |
|---|---|
| Purpose and layer | An AI application (host/client) gets tools, resources and prompts from a server. Application layer, model-to-tool |
| Official source | modelcontextprotocol.io/specification/2026-07-28; github.com/modelcontextprotocol |
| Governance | The MCP project's maintainers, with changes through SEPs (Specification Enhancement Proposals) |
| Pinned specification | **2026-07-28** (the versioning page calls it the current version). 2025-11-25 is the previous stable one |
| What changed in 2026-07-28 | `initialize` and protocol sessions removed: each request carries `io.modelcontextprotocol/protocolVersion` and `.../clientCapabilities` in `_meta`, and on HTTP an `MCP-Protocol-Version` header that must match (else 400, `HeaderMismatch`, -32020). `server/discover` is mandatory for servers. `Mcp-Session-Id` removed. Tasks moved to an extension. Roots, Sampling and Logging deprecated (12-month window) |
| SDK and license | `mcp` **2.3.0** (PyPI, 2026-10-02), MIT. Server class `MCPServer` (was `FastMCP`). Serves 2026-07-28 and older clients from the same server |
| Status | Released, current |
| Transports | stdio; Streamable HTTP (one endpoint, POST; JSON or SSE per response; `Mcp-Method` header always, `Mcp-Name` on `tools/call`; `Origin` MUST be validated, else 403) |
| Authentication | OAuth 2.1 resource server: RFC 9728 protected-resource metadata (MUST), audience via RFC 8707 resource indicators (MUST validate), 401 for invalid or expired tokens, 403 `insufficient_scope` with `WWW-Authenticate`. **MUST NOT accept tokens not issued for this server** (token passthrough). New since 2025-11-25: RFC 9207 `iss` validation; Client ID Metadata Documents preferred over dynamic registration |
| Limitations | Unsupported version → `UnsupportedProtocolVersionError` (-32022, 400) with `data.supported`. Standalone GET stream and `Last-Event-ID` resume removed. Whether the MCP Inspector speaks 2026-07-28 isn't documented on the pages we read |
| Verification date | 2026-11-11 |
| Adoption evidence | `docs/protocol-adoption-evidence.md` |

### A2A: Agent2Agent Protocol
| Field | Record |
|---|---|
| Purpose and layer | One agent discovers another and delegates a task to it, with messages, task states and artifacts. Agent-to-agent |
| Official source | a2a-protocol.org/latest/specification; github.com/a2aproject/A2A |
| Governance | The `a2aproject` GitHub organisation. Its foundation hosting wasn't on the pages read today: to verify |
| Pinned specification | **1.0** ("Latest Released Version 1.0.0" on the spec page; GitHub release v1.0.1 marked latest, changelog 2026-05-26) |
| SDK and license | `a2a-sdk` **1.3.0** (PyPI, 2026-10-27), Apache-2.0. Implements spec 1.0 with a 0.3 compatibility mode. Extras include `http-server`, `fastapi`, `sql`. Routes are functions (`create_jsonrpc_routes`, `create_agent_card_routes`, `add_a2a_routes_to_fastapi`); executors implement `AgentExecutor.execute` / `.cancel` |
| Status | Released |
| Transports | JSON-RPC over HTTP, HTTP+JSON (REST), gRPC. Streaming over SSE (`SendStreamingMessage`, `SubscribeToTask`) |
| Methods (JSON-RPC) | `SendMessage`, `SendStreamingMessage`, `GetTask`, `ListTasks`, `CancelTask`, `SubscribeToTask`, `Create/Get/List/DeleteTaskPushNotificationConfig`, `GetExtendedAgentCard` |
| Task states | `TASK_STATE_SUBMITTED`, `_WORKING`, `_COMPLETED`, `_FAILED`, `_CANCELED`, `_INPUT_REQUIRED`, `_REJECTED`, `_AUTH_REQUIRED` (and `_UNSPECIFIED`) |
| Discovery | Agent Card at `/.well-known/agent-card.json`. Signed cards (JWS, RFC 7515, with JCS canonicalisation) are defined in 1.0. **A card describes capabilities; it isn't proof of trust** |
| Authentication | At the transport layer: HTTPS required, the server MUST authenticate every request, schemes declared in the card. Push notifications: the agent MUST send the credentials in `PushNotificationConfig.authentication`; the client MUST validate them and SHOULD check the task ID |
| Limitations | Webhook URL validation is a SHOULD (reject private ranges, localhost, link-local; allowlists). No replay protection is specified for notifications, only "process idempotently, duplicates may occur". The SDK's URL check is off by default |
| Verification date | 2026-11-11 |

### AG-UI: Agent-User Interaction Protocol
| Field | Record |
|---|---|
| Purpose and layer | An agent backend streams events to a user-facing frontend: run lifecycle, messages, tool activity, state. Agent-to-UI |
| Official source | docs.ag-ui.com/spec/1.0; github.com/ag-ui-protocol/ag-ui |
| Governance | The `ag-ui-protocol` project; the Python package's maintainer is CopilotKit |
| Pinned specification | **1.0** (the current release). **1.1 is a draft** that "no SDK implements yet": not used |
| SDK and license | `ag-ui-protocol` **1.0.0** (PyPI, 2026-09-17), MIT. Modules `ag_ui.core`, `ag_ui.encoder` (`EventEncoder`). JS: `@ag-ui/client` (1.0.4 in release `release/2026-11-05`; npm page unreadable to our fetcher) |
| Status | Released 1.0 |
| Transport | HTTP POST of `RunAgentInput` (`threadId`, `runId`, `messages` required; `state`, `tools`, `context`, `forwardedProps` optional); response `text/event-stream`, one JSON event per `data:` line. Consumers MUST ignore `event:`, `id:` and `retry:` |
| Events used here | `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`, `STEP_STARTED`, `STEP_FINISHED`, `TOOL_CALL_START`, `TOOL_CALL_END`, `STATE_SNAPSHOT`, `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END`. Not used: `REASONING_*` (no chain-of-thought), `TOOL_CALL_ARGS` and `TOOL_CALL_RESULT` (no arguments or results), `THINKING_*` (deprecated) |
| Authentication | Not defined by AG-UI: it's the application's job. Here, the console's session (with CSRF) or a bearer token, then case-reader checks |
| Limitations | **No stream resumption:** "a broken stream cannot be re-entered. Re-running is a new run with a new `runId`". A dropped stream is a truncated run, and the consumer must not invent a `RUN_FINISHED`. No event IDs or deduplication are defined |
| Verification date | 2026-11-11 |
| Security notes | GitHub's malware advisories and OSV list nothing for the PyPI package (2026-11-11). GitHub lists unreviewed CVE entries titled "ag-ui-protocol ag-ui" whose ecosystem we couldn't confirm; `pip-audit` runs on the locked version before it's used |

## Supporting standards (not agent protocols)

| Standard | Where it's used here |
|---|---|
| HTTPS/TLS | Required by MCP's and A2A's remote guidance. Local demo runs on loopback HTTP; hosted TLS is in `docs/encryption.md` (the protocol services are not part of the public demo) |
| HTTP, JSON-RPC 2.0 | MCP's and A2A's message framing |
| OpenAPI, JSON Schema | REST contract (`openapi-v1.json`); MCP tool input schemas; A2A artifact schema |
| SSE | AG-UI's transport; MCP and A2A streaming responses |
| OAuth 2.1, RFC 9728, RFC 8707, RFC 9207 | MCP authorization; reused for A2A peer tokens |
| OIDC, JWT, JWKS | Keycloak issues the access tokens; PyJWT verifies them against its JWKS |
| OpenTelemetry, trace context | Correlation IDs today; OpenTelemetry in Milestone 12 |
| Webhook verification | A2A push notifications: per-task token, checked in constant time |
| CloudEvents | Not used: no event bus (ADR-0022) |
| DID, verifiable credentials | Not used in Milestone 11; ANP lab (Milestone 16) |

## Labs (Milestone 16): source and status only

Sources and statuses for these are **not read today**. `agent-protocols-lab` recorded pins for some on 2026-10-27
(A2UI v0.9.1, UCP v2026-08-25); Milestone 16 re-reads every one from its maintainers before building.

| Protocol | Kind | Record |
|---|---|---|
| A2UI | Agent-generated UI descriptions | Milestone 16 |
| MCP Apps | MCP extension for embedded UI | Milestone 16 |
| **Agent Client Protocol** | Editor ↔ coding agent | Milestone 16 |
| **Agent Communication Protocol** (IBM / BeeAI) | Historical agent messaging; its relationship to A2A to be verified from maintainer sources | Milestone 16 |
| **Agentic Commerce Protocol** | Agent checkout with a merchant | Milestone 16 |
| ANP: Agent Network Protocol | Decentralised agent identity and discovery | Milestone 16 |
| UCP: Universal Commerce Protocol | Agent commerce | Milestone 16 |
| AP2: Agent Payments Protocol | Payment mandates | Milestone 16 |
| x402 | HTTP 402 payments | Milestone 16 |
| MPP: Machine Payments Protocol | Machine payments | Milestone 16 |

`agent-protocols-lab` (stage-level demo of ten protocols, checked 2026-10-27) is the place to see each one alone;
this repo connects the core three to the loyalty domain instead of repeating those demos (REUSE-09).
