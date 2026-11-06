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
