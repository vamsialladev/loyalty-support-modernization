# Protocol test results (PROTO-01, PROTO-14)

> Simulated engagement, synthetic data. Every row comes from a test or a recorded run in this repo, with the exact
> version, transport, capability subset and peer. Same-SDK tests show our code works; only a peer we didn't write
> counts as interoperability. Rows are filled in as each protocol's step lands. A row without a result says
> **NOT RUN**.

## Independent client and peer runs

| Protocol | Our side | Peer (exact version) | Transport | Capability subset | Result | Evidence |
|---|---|---|---|---|---|---|
| MCP | — | MCP Inspector CLI | Streamable HTTP | discover, tools/list, tools/call | NOT RUN | — |
| MCP | — | Claude Code (owner step) | Streamable HTTP | tools/list, tools/call | NOT RUN | — |
| A2A | — | A2A TCK | JSON-RPC over HTTP | Agent Card, SendMessage, GetTask, CancelTask | NOT RUN | — |
| AG-UI | — | `@ag-ui/client` | HTTP POST + SSE | RunAgentInput, 11 event types | NOT RUN | — |

## G.13 checks, per protocol

| Check | MCP | A2A | AG-UI |
|---|---|---|---|
| Schema validation | NOT RUN | NOT RUN | NOT RUN |
| Version compatibility | NOT RUN | NOT RUN | NOT RUN |
| Initialization and negotiation | NOT RUN | NOT RUN | NOT RUN |
| Authentication failures | NOT RUN | NOT RUN | NOT RUN |
| Insufficient permissions | NOT RUN | NOT RUN | NOT RUN |
| Malformed input | NOT RUN | NOT RUN | NOT RUN |
| Unsupported features | NOT RUN | NOT RUN | NOT RUN |
| Stream interruption | NOT RUN | NOT RUN | NOT RUN |
| Cancellation | NOT RUN | NOT RUN | NOT RUN |
| Duplicates | NOT RUN | NOT RUN | NOT RUN |
| Timeouts and unavailable peers | NOT RUN | NOT RUN | NOT RUN |
| Replay | NOT RUN | NOT RUN | NOT RUN |
| Expired credentials | NOT RUN | NOT RUN | NOT RUN |
| State recovery | NOT RUN | NOT RUN | NOT RUN |
| Cross-record access | NOT RUN | NOT RUN | NOT RUN |
