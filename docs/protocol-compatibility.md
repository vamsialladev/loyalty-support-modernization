# Protocol compatibility (PROTO-01)

> Simulated engagement, synthetic data. "Supported" below means implemented here **and** tested; results with the
> independent peer are in `docs/protocol-test-results.md`. Anything not listed isn't supported.

## Versions

| Protocol | We implement | Also accepted | Refused with |
|---|---|---|---|
| MCP | 2026-07-28 | 2025-11-25 clients (the SDK serves both; `initialize` handshake for them) | `UnsupportedProtocolVersionError` (-32022, HTTP 400) listing the supported versions |
| A2A | 1.0 | 0.3 only if the SDK's compatibility mode is turned on (off here) | `VersionNotSupportedError` (-32009) |
| AG-UI | 1.0 | Peers that send no `protocolVersion` (the spec treats them as pre-versioning) | Input failing `RunAgentInput` validation: HTTP 422, no stream |

## Capability subset

| Protocol | Supported | Not supported, on purpose |
|---|---|---|
| MCP | `server/discover`, `tools/list`, `tools/call` (six read-only tools), protected-resource metadata, Streamable HTTP | Resources, prompts, sampling, roots, logging (three of them deprecated in 2026-07-28), the Tasks extension, `subscriptions/listen`, stdio, any write tool |
| A2A | Agent Card, `SendMessage`, `GetTask`, `CancelTask`, push-notification config create/get/delete, one data artifact per task | Signed Agent Cards (cards are read from a configured URL instead), gRPC, HTTP+JSON binding, `ListTasks`, `SubscribeToTask` streaming, `GetExtendedAgentCard`, multi-turn `INPUT_REQUIRED` |
| AG-UI | `RunAgentInput` over HTTP POST, SSE response, the 11 event types in `docs/protocol-catalog.md` | `REASONING_*`, `TOOL_CALL_ARGS`, `TOOL_CALL_RESULT`, `STATE_DELTA`, `MESSAGES_SNAPSHOT`, frontend-defined tools, interrupts, 1.1 draft features |

## Between protocols

- The three aren't wire-compatible and don't pretend to be: there is no gateway translating one into another.
- They share **services and checks**, not messages: the same permission code, customer scope, rate limits and audit.
- An MCP token isn't accepted by the A2A specialist and the reverse is also true (different audiences).

## Clients and peers

Support in a client is recorded only after running it, with the client's exact version. We don't assume Cursor,
Codex, Claude Code or any other tool supports a given version: the MCP Inspector's and Claude Code's results are in
`docs/protocol-test-results.md`, or say NOT RUN.
