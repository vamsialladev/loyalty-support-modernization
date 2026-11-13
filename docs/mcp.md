# The MCP server (PROTO-03)

> Simulated engagement, synthetic data. Design: `docs/rfcs/RFC-0004-protocols.md`, ADR-0023, ADR-0071. Results:
> `docs/protocol-test-results.md`.

## What it is

A read-only MCP server, so an AI assistant (Claude Code, an IDE, the client's own agent) can look up the same facts a
support agent sees for a case: the member, their stays, the ledger, the policy in force and the engine's result. It
runs the same functions arm C's model uses (`app/ai/tools.py`), as a read-only service account of one customer.

| | |
|---|---|
| Specification | MCP **2026-07-28** (the SDK also serves 2025-11-25 clients through their handshake) |
| SDK | `mcp` 2.3.0, `MCPServer` |
| Transport | Streamable HTTP, stateless, JSON responses, `127.0.0.1:8030/mcp` |
| Auth | OAuth resource server: bearer token from the configured issuer; audience = the endpoint URL; scope `loyalty.read`, plus `loyalty.case.read` for `get_case_evidence` |
| Tools | `get_member`, `get_stay`, `get_points_ledger`, `search_policy`, `evaluate_eligibility`, `get_case_evidence`. Every one takes a `case_id` and is marked read-only |
| Never | A write tool, SQL, files, model sampling, or forwarding the caller's token |

## Why it's optional, and when REST is enough

**REST is enough** when you control the one client calling in: the console does, and a script with an `lsm_` machine
token can read the JSON API today. MCP adds nothing for them.

**MCP earns its place** when several AI clients the client already uses (an IDE assistant, a desktop assistant, their
own agent framework) would each need a custom integration. One MCP server replaces those, with tool descriptions the
model can read and a standard way to authenticate.

**It is never the core.** Turn `FEATURE_MCP` off and nothing else changes (`tests/test_protocols_off.py`).

## How access works

1. The caller gets a token from the issuer (the local Keycloak in Compose) with the client-credentials grant.
2. The token must be issued **for this server**: its audience is the MCP endpoint URL. A token for the A2A specialist
   is refused here, and the reverse is also true (RFC 8707; MCP's "no token passthrough").
3. The customer comes from the token's `customer_id` claim, never from a tool argument. Another customer's case is
   "not found", the same answer as a case that doesn't exist.
4. The caller is a read-only auditor. It sees only the tools its scopes allow, and each call checks again.
5. Every call is rate-limited per caller and audited (`system_events`, action `mcp_call`) with a hash of the arguments.

Without a token, the server answers 401 with `WWW-Authenticate: Bearer resource_metadata="…"`, and serves its
protected-resource metadata at `/.well-known/oauth-protected-resource/mcp` (RFC 9728), naming the issuer.

## Run it locally

```powershell
$env:FEATURE_MCP = "true"; uv run python -m protocols.mcp.server
```

It needs `PROTOCOL_TOKEN_ISSUER` (or `OIDC_ISSUER_URL`) and the app database. Check with
`uv run python -m app.preflight --profile protocols`. Machine clients are created in the local Keycloak by
`scripts/protocol_clients.py` (see `scripts/protocol_token_check.py` for an example).

## Connect a client (no secrets in files)

Claude Code (syntax from its MCP documentation, read 2026-11-11). Put the token in an environment variable, and use
this project `.mcp.json` entry, so the file never holds it:

```json
{
  "mcpServers": {
    "loyalty-support": {
      "type": "http",
      "url": "http://127.0.0.1:8030/mcp",
      "headers": { "Authorization": "Bearer ${LOYALTY_MCP_TOKEN}" }
    }
  }
}
```

Claude Code's documentation says it uses MCP 2026-07-28 with servers that support it. **Connecting it here is an
owner step** (it changes your Claude Code configuration), and its result is recorded only once it's run.

MCP Inspector (CLI, an independent client): `tests/interop/test_mcp_inspector.py`, opt in with `RUN_INTEROP=1`.

## Limits, said plainly

- Tokens are checked locally, so a disabled client's last token works until it expires (TD-49).
- Insufficient scope for one tool comes back as a tool error, not an HTTP 403: only the transport-wide scope
  (`loyalty.read`) is enforced at the HTTP layer. The tool is also hidden from the caller's list.
- No resources or prompts are offered; `resources/list` answers with an empty list.
- No Compose service yet: the server starts with its own command. Containers and the host see Keycloak under different
  hostnames, which breaks the issuer check; that belongs with Milestone 12's container work (TD-52).
