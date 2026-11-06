# Risk register (SEC-02)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

Likelihood and impact are judgments, not measurements. A pilot's owner must accept each high risk. Nobody has, because this is a simulation.

| ID | Risk | Likelihood | Impact | Controls | Evidence | Residual | Owner (role) |
|---|---|---|---|---|---|---|---|
| R1 | A wrong or duplicate credit | Medium | High | Engine only, different supervisor, binding, re-check, idempotency, one live credit per stay | `tests/test_execution_postgres.py`, `tests/test_red_team.py` | A platform that applies a timed-out write very late (RFC-0001) | Loyalty ops lead |
| R2 | Prompt injection through a message or a document | High | Medium | Nothing a model says decides anything; data blocks; validation; drafts aren't sent | `tests/test_red_team.py`, `tests/test_red_team_shared_corpus.py` | A misleading explanation can sway a reviewer. **Not solved** | AI lead |
| R3 | Another member's data disclosed | Low | High | Two identifiers, tools scoped to the member, `not_found` for the rest | `tests/test_arm_c.py`, `tests/test_arm_b_console.py` | Staff can search members | Security |
| R4 | Another customer's data disclosed | Low | High | Customer scope in every read | `tests/test_security_authz.py` | One database per deployment is still safer | Security |
| R5 | Personal data sent to a provider | Medium | High | Redaction, minimal fields, live off by default | `tests/test_ai_tools.py` | Pattern matching misses things. **Provider terms unverified** | Privacy |
| R6 | A leaked key or credential | Low | High | Secrets in `.env` only, gitleaks, masked diagnostics, rotation | `tests/test_security_authz.py::test_rotating_the_customer_systems_token_makes_the_old_one_fail` | Rotation of the model key isn't exercised | Security |
| R7 | Runaway model spend | Medium | Medium | Caps in the database, per run, day and month; loop limits | `tests/test_ai_provider.py` | A provider-side limit should back this up | Platform |
| R8 | Reviewers rubber-stamp | Medium | High | Evidence first, labelled AI text, reasons required | `tests/test_arm_c.py` | Measured at Milestone 10 | Ops lead |
| R9 | A compromised dependency | Low | High | Locked versions, `pip-audit`, Dependabot | CI | No signature verification | Platform |
| R10 | Local demo auth used in a real deployment | Low | High | Preflight rules per profile; OIDC profile | `tests/test_preflight.py`, `scripts/oidc_check.ps1` | Depends on the operator | Platform |
