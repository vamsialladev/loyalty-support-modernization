# RFC-0004: Protocol interfaces (MCP, A2A, AG-UI)
Status: accepted under the owner's standing instructions (plan approved 2026-11-11)      Milestone: 11      Author: Claude Code (Opus 5.5)      Date: 2026-11-11

Everything here is a simulation with synthetic data. **No number in this RFC is a result.** Versions were read from
primary sources on 2026-11-11 (`docs/protocol-catalog.md` has the links) and are re-checked when the lock file is built.

## Context

The core app already works without any agent protocol: REST, a server-rendered console, a durable worker and one
bounded AI loop (ADR-0009, ADR-0025). Milestone 11 adds three optional edges over the same services:

- **MCP:** other AI clients read loyalty facts (ADR-0023: read-only, never executes adjustments).
- **A2A:** a loyalty coordinator asks a separate reservation specialist for stay evidence (ADR-0025: a lab, not the core).
- **AG-UI:** a frontend watches an arm C investigation as it runs.

Requirements: PROTO-01 to PROTO-05, PROTO-14 (M11 part), REUSE-06, REUSE-09, SEC-01, SEC-16, PURP-05, TOOL-CC.
**Done when (Appendix C):** MCP, A2A and AG-UI tests pass against an independent client or peer where available.
Spec Parts G.1–G.5 and G.13.

## The one rule

**A protocol is a door, not a new room.** Every request through MCP, A2A or AG-UI reaches the same services, the same
permission checks and the same audit tables as REST. No protocol can approve, execute or change a case. With every
protocol flag off, the app behaves exactly as it did at Milestone 10, and a test proves it.

## Pinned versions (checked 2026-11-11)

| Protocol | Specification | Package | Status | Independent peer |
|---|---|---|---|---|
| MCP | 2026-07-28 (current). The SDK also serves 2025-11-25 clients | `mcp` 2.3.x (MIT) | Released, current | MCP Inspector CLI (Node, pinned); Claude Code as a second client (owner step) |
| A2A | 1.0 (1.0.1 is the latest patch release) | `a2a-sdk` 1.3.x (Apache-2.0) | Released | A2A TCK (`a2aproject/a2a-tck`); a2a-inspector if it runs |
| AG-UI | 1.0 (1.1 is a draft "no SDK implements yet") | `ag-ui-protocol` 1.0.x (MIT) | Released 1.0; draft 1.1 not used | `@ag-ui/client` script (Node, pinned) |

**Fallback:** if the MCP Inspector can't speak 2026-07-28 ("modern"), the interop run uses 2025-11-25 through the
same server, and the report says which version the peer used. Same-SDK tests are never presented as interop proof.

## What could go wrong, and what stops it

| Risk | Guard |
|---|---|
| A protocol becomes a back door to writes | Tools and skills are built from an explicit read list. A test asserts no write function is reachable (adjustments, tickets, `attach_*`, approval, execution) |
| A token for one service is accepted by another (confused deputy, token passthrough) | One audience per service; the verifier refuses any other. Incoming tokens are never forwarded: the coordinator gets its own token for the specialist |
| One customer reads another's records | The customer comes from the verified token, never from the message. Same rule as REST: another customer's case is "not found" |
| A peer or Agent Card points us at an internal address (SSRF) | Discovery and callbacks only through `app/outbound.py`: configured hosts, `https` for outside URLs, no private ranges, no redirects, size and time limits |
| Chain-of-thought, prompts or secrets reach a frontend | AG-UI events are built from an allowlist: tool name, argument hash, status, allowlisted case state. No `REASONING_*` events, no arguments, no results, no prompt |
| A reconnect repeats work | AG-UI 1.0 has no stream resume: a reconnect is a new run that *watches*. Starting an investigation uses the existing job queue, which keeps one active job per case |
| A draft spec is presented as a standard | AG-UI 1.1 isn't used. Anything we add beyond 1.0 is a `CUSTOM` event, named as ours |
| A same-vendor client "passes" because it shares our assumptions | Each protocol is also run against a tool we didn't write. If it can't run, the result is **Blocked** with the reason |
| A compromised package | `pip-audit`, OSV and the GitHub malware advisories checked before locking; hashes in `uv.lock`; Node tools run with exact versions, outside the repo's code paths |

## Options considered

**1. Where protocol code lives.**
1. Inside `app/` next to REST.
2. A separate `protocols/` package with its own entry points, calling `app/services` and `app/ports`.
3. A separate repository.

**Chosen: 2.** Spec G.2 asks for per-protocol folders, a flag each and an independent start command. Domain code
keeps its rule (no FastAPI, no SDKs). A separate repo would copy the permission code we most want shared.

**2. How MCP and A2A callers prove who they are.**

| Option | Pros | Cons |
|---|---|---|
| Reuse the opaque `lsm_` machine tokens (M9) | Already built and tested | No issuer, audience, expiry claim or scope. MCP's authorization spec requires audience validation and protected-resource metadata; this can't meet it |
| Our own JWT issuer inside the app | No extra container | We'd be writing an authorization server, which neither spec asks for and which is easy to get wrong |
| **JWT access tokens from the local Keycloak (M9), verified as a resource server** | Real issuer, audience, expiry, scopes, JWKS; same IdP as console sign-in; matches MCP's OAuth model | One more Keycloak client per service; offline tests need a test signer |

**Chosen: Keycloak.** Client-credentials clients for machine callers, one audience per protocol service, scopes
`loyalty.read` (MCP) and `reservation.evidence` (A2A). Verified with PyJWT and a JWKS fetched through `check_url`,
reusing `app/adapters/oidc_identity.py`'s algorithm allowlist and discovery check. Claims map to the existing
`Identity` (role + `customer_id`), then the REST checks do the rest. Offline tests sign tokens with an in-process RSA
key; one evidence run uses the real Keycloak. REST keeps its `lsm_` tokens.

**3. What MCP exposes.** Tools only, for now: `get_member`, `get_stay`, `get_points_ledger`, `search_policy`,
`evaluate_eligibility` (the same functions arm C uses, `app/ai/tools.py`) plus `get_case_evidence`. Resources and
prompts aren't needed by any client we have. Stage 7's convention carries over: the role decides which tools exist
for the caller, and every call is checked again and audited (`hotel-tools-mcp/src/hotel_tools/rbac.py`).

**4. Where A2A task state lives.**
1. The SDK's in-memory task store: lost on restart; two replicas disagree.
2. **A new table, `a2a_tasks`, in the app database** (migration `0011`): task ID, case, peer, state, artifact hash,
   correlation ID, times. Upgrade-checked from a volume built by the previous code (ADR-0058).
3. The SDK's SQL store: adds a second schema owner to our database.

**Chosen: 2.** It survives restarts and is audited with the case.

**5. How AG-UI gets its events.**
1. Push events from inside the loop as it runs: live, but lost on disconnect, and the worker and the web process are
   different processes.
2. **Read persisted rows (`ai_runs`, `ai_steps`, `case_events`) and turn them into AG-UI events.** A new viewer
   gets the same events as the first, and nothing in memory is the source of truth.

**Chosen: 2.** It polls the database at a short, bounded interval while the run is active, then ends the stream.

**6. Can AG-UI start an investigation?** Yes, but only through the existing job queue (`jobs.enqueue`, one active job
per case), only for a case worker in the same customer, and only while the case is `INVESTIGATING`. Otherwise the
run only watches. Approving, executing and closing stay on the console's own forms.

## Decision

- `protocols/mcp/`: an MCP server on the official SDK's `MCPServer`, Streamable HTTP, Origin and Host checks,
  `TokenVerifier` backed by the shared verifier, protected-resource metadata, the six read tools above. Start:
  `python -m protocols.mcp.server`.
- `protocols/a2a/`: two services. The **reservation evidence specialist** reads stays and pending postings through
  `CustomerSystems` and returns one data artifact with provenance (source system, record IDs, read time, correlation
  ID, content hash). The **loyalty investigation coordinator** reads the specialist's Agent Card from a configured URL,
  sends the task with its own token, handles timeout, cancellation and an unavailable peer, and records the artifact
  for a person to review. Push-notification callbacks go only to allowlisted destinations and carry a per-task token.
- `protocols/ag_ui/`: `POST` with `RunAgentInput` (`threadId` = case reference, `runId` from the client), SSE response.
  Events: `RUN_STARTED`, `STEP_STARTED`/`STEP_FINISHED`, `TOOL_CALL_START`/`TOOL_CALL_END` (name and argument hash
  only), `STATE_SNAPSHOT` (allowlisted), `TEXT_MESSAGE_*` (the stored summary a person already sees), `RUN_FINISHED`
  or `RUN_ERROR` with a safe message.
- Shared: flags `FEATURE_MCP`, `FEATURE_A2A`, `FEATURE_AG_UI` (off by default, named like the existing `FEATURE_*` flags); a `protocols` Compose profile; a
  `protocols` dependency group, so the core install doesn't change; every handler inside `correlated()`, audited with
  `record` / `record_system`, rate-limited with `rate_limit.hit`.
- A developer-only **Protocol Lab** page (admin role, flag): version, transport, capabilities, peer, scenarios,
  sanitized traces, results, limits.

**Reuse, cited rather than repeated (REUSE-06, REUSE-09):** stage 7's role-decides-tools pattern, "other tenant =
not found", argument hashes instead of arguments, and its OAuth plan (`hotel-tools-mcp/docs/AUTH.md`, built here for the
first time); `agent-protocols-lab`'s A2A kit (`src/protolab/a2a_kit.py`) and AG-UI event order
(`demos/ag_ui/demo.py`). New here: issuer, audience and scope checks; A2A callbacks; AG-UI from a real stored run.

## Rollout

Five pull requests, each green on CI before the next: research and this RFC; foundation (flags, verifier, Keycloak
clients, dependency group); MCP; A2A (with migration `0011` and its upgrade check); AG-UI and the Protocol Lab page.
Rollback is turning a flag off; the migration only adds a table.

## Open questions

- Does the MCP Inspector's "modern" mode speak 2026-07-28 against a Python server? (Found out in the MCP step.)
- Does the A2A TCK cover spec 1.0 at the level we implement? (A2A step.)
- At a real hotel group, who owns the Keycloak clients and their secrets, and how often are they rotated? (Owner, at
  handover; `docs/real-system-swap-guide.md`.)
- When would a partner agent be worth A2A rather than a REST call? `docs/a2a-vs-rest.md` answers for this case; a real
  partner would decide it.
