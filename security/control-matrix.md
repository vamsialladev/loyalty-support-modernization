# Control matrix (SEC-02)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

| Requirement | Threat | Owner (role) | Where | Evidence | Result | Limitation |
|---|---|---|---|---|---|---|
| Deny by default, every route | Unauthenticated access | Security | `app/web/console.py`, `app/api/router.py` | `tests/test_security_authz.py::test_every_console_route_needs_a_session_unless_its_listed_public` | Pass | New public routes must be added on purpose |
| Roles on the server | Role escalation | Security | `app/domain/roles.py` | `tests/test_security_authz.py` | Pass | |
| Customer scope | Cross-customer access | Security | `cases.get_case`, `list_cases`, `pending_approvals`, `metrics.collect`, API | `tests/test_security_authz.py` | Pass; **found one real bug** | Tested on a second customer's rows in one database |
| Sessions | Hijack, fixation | Security | `app/services/sessions.py` | `tests/test_console_web.py` | Pass | `Secure` cookies only in hosted profiles |
| CSRF | Cross-site changes | Security | Every POST; API header | `tests/test_security_authz.py`, `tests/test_api.py` | Pass | |
| Rate limits | Guessing, exhaustion | Platform | `app/services/rate_limit.py` | `tests/test_security_authz.py` | Pass | The address is the socket's; a proxy needs a trusted header |
| Recovery, deactivation | Lost or stale accounts | Security | `app/services/accounts.py` | `tests/test_security_authz.py` | Pass | Links are handed over by an administrator, out of band |
| OIDC | Forged sign-in | Security | `app/adapters/oidc_identity.py` | `tests/test_oidc.py`, `scripts/oidc_check.ps1` | Pass, 7 of 7 on real Keycloak | MFA is the provider's: see `docs/identity.md` |
| Machine tokens | Overprivileged integrations | Security | `accounts.py` | `tests/test_security_authz.py` | Pass | Read-only, no per-token scopes yet |
| Approval binding | Tampering | Ops lead | `app/domain/approval_binding.py` | `tests/test_red_team.py::test_a_tampered_amount_voids_the_approval` | Pass | The key must stay secret |
| Audit | Repudiation | Audit | `case_events`, `system_events`, DB role | `tests/test_audit_postgres.py` | Pass | Append-only for the app role, **not tamper-proof**: a DB owner can still change it |
| Output encoding | XSS | Security | Jinja autoescape, CSP | `tests/test_red_team.py` | Pass | |
| Error handling | Information leak | Security | Console's error handler | `tests/test_security_authz.py::test_an_unexpected_error_shows_no_stack_trace` | Pass | |
| Outbound allowlist | SSRF | Security | `app/outbound.py` | `tests/test_security_authz.py` | Pass | The SDK's host isn't checked by us. Nothing takes a URL from outside yet |
| File ingestion | Malicious files | Security | `conventional/extraction.py` | `tests/test_extraction.py`, `tests/test_red_team.py` | Pass | No malware scan, and no quarantine beyond "evidence only" |
| Retention, erasure, hold | Over-retention | Privacy | `app/services/retention.py` | `tests/test_security_authz.py` | Pass | Backups aren't touched. Free text in some event details stays |

## OWASP Top 10 for LLM and GenAI apps, 2025

| Item | Here |
|---|---|
| LLM01 Prompt Injection | **Contained, not prevented.** Data blocks; nothing a model says decides anything; tests on business effects |
| LLM02 Sensitive Information Disclosure | Redaction, minimal fields, tools scoped to the member, no secrets in prompts |
| LLM03 Supply Chain | Locked versions, `pip-audit`, Dependabot, pinned model IDs |
| LLM04 Data and Model Poisoning | Policies publish through checks; no training on case data; a poisoned document is evidence only |
| LLM05 Improper Output Handling | Schema validation, then Jinja escaping and CSP |
| LLM06 Excessive Agency | Five read-only tools; no write tool; a person approves |
| LLM07 System Prompt Leakage | The prompt holds no secret; assume it can leak |
| LLM08 Vector and Embedding Weaknesses | No vectors or embeddings are used |
| LLM09 Misinformation | Engine's result first; validation on actions, amounts and citations; a person decides. Free text can still mislead |
| LLM10 Unbounded Consumption | Turn, call, deadline and spend limits; rate limits |

## OWASP Top 10 for Agentic Applications, 2026 edition (read 2026-11-11; Milestone 11 protocols)

Status words follow spec 0.4. "Planned (M11)" rows become "Pass" only when their test exists and passes.

| Item | Here | Status |
|---|---|---|
| ASI01 Agent Goal Hijack | Same as LLM01: request text and tool results are data; rules decide; a person approves. Through MCP, A2A or AG-UI nothing can approve or execute | Arm C: pass (M8–9 red team). Protocols: pass, none can approve or execute (`tests/test_mcp_server.py`, `tests/test_a2a.py`, `tests/test_ag_ui.py`) |
| ASI02 Tool Misuse and Exploitation | MCP exposes six read-only tools from an explicit list, per role, each call re-checked and audited; no write tool exists to misuse | MCP: pass (`tests/test_mcp_server.py`). A2A and AG-UI expose no tools to call |
| ASI03 Identity and Privilege Abuse | Tokens verified for issuer, audience, expiry and scope; one audience per service; no token passthrough; the customer comes from the token, never the message | Pass for the verifier and MCP (`tests/test_protocol_auth.py`, `tests/test_mcp_server.py`, a real Keycloak in `security/evidence/protocol-token-check-2026-11-11.txt`). A2A: pass (`tests/test_a2a.py`) |
| ASI04 Agentic Supply Chain Vulnerabilities | Locked SDK versions with hashes, `pip-audit`, OSV and malware-advisory checks before adding a protocol package; peer Agent Cards read only from configured URLs | Pass: `pip-audit` (two versions) and OSV/GitHub malware checks before locking, hashes in `uv.lock`, CI audits every group (verification log, Milestone 11, rows 3 and 5); cards from configured URLs only (`tests/test_a2a.py`) |
| ASI05 Unexpected Code Execution (RCE) | No tool runs code, SQL or shell; no model-generated HTML or JavaScript is rendered | Pass for arm C (M8–9); protocols add no such tool |
| ASI06 Memory and Context Poisoning | No long-term agent memory. A specialist's artifact is evidence for a person to review, with provenance, not an instruction | A2A: pass, the artifact is schema-checked and hashed and changes nothing (`tests/test_a2a.py`) |
| ASI07 Insecure Inter-Agent Communication | A2A: authenticated per request, per-task authorization, callbacks only to allowlisted destinations with a per-task token, duplicates handled idempotently | Pass (`tests/test_a2a.py`); same SDK on both sides, independent peer not run yet |
| ASI08 Cascading Failures | Peer timeout, cancellation and "peer unavailable" leave the case unchanged; one bounded loop, no agent chains | A2A: pass (`tests/test_a2a.py`) |
| ASI09 Human-Agent Trust Exploitation | AG-UI shows tool names and status, not persuasive model reasoning; approval stays on the console's own form with its separation of duties | AG-UI: pass, tool names and status only, no reasoning events, approval only on the case page (`tests/test_ag_ui.py`, `tests/browser/test_ag_ui_panel.py`) |
| ASI10 Rogue Agents | A remote agent can only return evidence; it holds no write permission and its card isn't trusted as proof of identity | Pass (`tests/test_a2a.py`: card checks, no write function reachable) |
