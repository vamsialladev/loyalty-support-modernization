# Unusual protocol read volume

**Alert:** `loyalty-protocol-reads`: more than 200 MCP or A2A calls in 15 minutes (`loyalty_protocol_calls`, by
`protocol`). From the Milestone 11 exercise: a client with a valid token can read a lot, slowly, inside its scopes.
**Proposed owner:** security (L3). The protocol doors are off by default and read-only (RFC-0004). Synthetic data only.

**You notice:** the alert, while `FEATURE_MCP` or `FEATURE_A2A` is on.

1. Which client? The calls are audit events `mcp_call` and `a2a_call` with the operation and outcome:
   `python -m app.services.security_events --since <today>` (or the system events table). The actor is the machine
   client (`svc-…`).
2. Is it expected (a batch the customer announced)? If so, raise the threshold in
   `observability/grafana/alerting/rules.yaml` with a reviewed commit, not in the UI.
3. If not: disable the client in the identity provider (Keycloak → Clients → the client → Enabled off). Tokens it
   already holds stay valid until they expire (TD-49), so also turn the protocol off: `FEATURE_MCP=false` or
   `FEATURE_A2A=false`, then restart.
4. Check what it read: each call's operation is in the audit row. Only tool outputs for the cases its scopes allow
   are readable; nothing can change data through these doors.

**Check it worked:** the call count falls back, the client's next token request is refused, and the alert clears.
