# Implementation status

**Last updated:** 2026-11-12 · **Current milestone:** 11 of 20, merged (PRs #32 to #36, in order) · **Next:** Milestone 12
(performance, observability, CI/CD, hardening). **Waiting on the owner:** a look at PROTO-04's status (the A2A TCK is
partial); the Milestone 7 to 9 exercises; the Codex exercise, when convenient.

## Completion scores (spec Part 0.5)
Counted from `docs/requirements-matrix.md` by `uv run python scripts/matrix_scores.py`. Only "Implemented and
verified" (or "Not applicable") counts as done.

| Score | Done (verified) | Total | % | In progress (unverified / configured / docs) |
|---|---|---|---|---|
| Core product functionality | 76 | 108 | 70% | 5 |
| Benchmarks and evaluation | 46 | 64 | 72% | 3 |
| Actual-tool exercises | 0 | 16 | 0% | 3 |
| Protocol labs | 6 | 16 | 38% | 2 |
| Security controls | 30 | 55 | 55% | 6 |
| Owner's demonstrated understanding | 0 | 3 | 0% | 1 |
| Other tracked work (not a Part 0.5 score) | 40 | 107 | 37% | 13 |

369 requirements: Tier 1: 190, Tier 2: 102, Tier 3: 27, Tier 4: 50

New in M11: MCP, A2A and AG-UI over the same services (PROTO-01 to PROTO-05, PROTO-14's M11 part), the protocol specs and the OWASP agentic list (SEC-01), callbacks and card fetching (SEC-16), RFC-0004 (PURP-05), reuse cited (REUSE-06, REUSE-09). Verified on the same SDK on both sides, and tokens against a real Keycloak. **Independent peers run 2026-11-12 with the owner's OK:** the MCP Inspector and `@ag-ui/client` passed; the A2A TCK passed partially (scenario tests the specialist doesn't act out; one SHOULD gap found and fixed). So PROTO-03 to PROTO-05 are verified (`docs/protocol-test-results.md`).

New in M10: the benchmark, with held-out verdicts, on live arm C. Open: REUSE-03 needs the owner's OK; BIZ-02 and ENT-07/08 need real participants; ENT-17's caching and BENCH-13's release gate are Milestone 12.

New in M9: `security/` documents, customer scope, OIDC, rate limits, machine tokens, retention, erasure, legal hold and access review. SEC-19 stays unverified until the repeated tests run on a real model; SEC-10 is a guide only.

New in M8: arm C (ARMC-01, ARMS-01), AI engineering (AI-01, AI-03 to AI-17), ELIG-02, POL-06, POL-07, TEST-03, TEST-04, the system card (ENT-01, ENT-02), labels and review order (ENT-05, ENT-06), documents (DOC-02 to DOC-04), the routing baseline (ML-01, ML-03). **All of it is verified on mock and scripted models; the live smoke test is NOT RUN.** Blocked: ML-05, and image OCR. Started, still `Planned`: AI-02 and ML-02 (need a live model, M10), SEC-05, ENT-12, ENT-23, DOC-06 (M9), ENT-15, LIVE-05, OPS-05 (M12), BENCH-10 (M10).

New in M7: arm B (ARMB-01), the JSON API (API-01, API-02), the complete console (UI-01, UI-03), the browser suite (TEST-05), the
day-one page (LGF-11), stage 2's approval wording (REUSE-04). Started but not done (still `Planned`, with progress noted in the
matrix): ARMS-01 and PROF-02 (arm C, M8), DB-01 (evaluation tables, M8), SEC-17 (rest in M9). Arm A is fenced (ADR-0063).

New in M6: eligibility (ELIG-01), policies (POL-01, POL-03 to POL-05, POL-08 as documentation), the state machine and roles
(WP-01, WP-02), binding and invalidation (WP-03, WP-06), re-check (WP-07), concurrency (WP-08), reconciliation (WP-09, MOCK-09),
kill switch (WP-10), audit role (WP-11), durable jobs (JOB-01 to JOB-03). Started but not done (still `Planned` with progress
noted in the matrix): POL-06 and WP-05 (model parts, M8), DB-01 (later tables), TEST-01 (redaction, M9), TEST-02 (object-level
authorization, M9), API-01 and API-02 (moved to M7, as the owner approved). Codex exercise prepared, not run (TOOL-CODEX).

## Milestones

| M | Status | Evidence |
|---|---|---|
| 1 | Implemented and verified | `tests/test_repo_guidance.py`, `tests/test_matrix_scores.py` |
| 2 | Implemented and verified | `tests/test_discovery_docs.py`, `tests/test_preregistration.py`; pre-registration `1f8b8e6` |
| 3 | Implemented and verified | `tests/test_generator.py`; `scripts\data.ps1 -Action verify` identical |
| 4 | **Implemented and verified** (Appendix C, M3-4: `docker compose up`, migrate and seed succeed from scratch; contract tests pass) | `tests/test_mock_api.py` (41), `tests/test_compose.py`, `tests/test_app_shell.py`, `tests/test_mock_api_postgres.py` (6, real Postgres); `scripts\compose_check.ps1` passed; verification log, Milestone 4 |
| 5 | **Implemented and verified** (Appendix C, M5: legacy arm A completes a case end to end in the browser) | `tests/browser/test_legacy_e2e.py` (2, offline and against the stack), `tests/test_legacy_rules.py` (26), `tests/test_legacy_screens.py` (14), `tests/test_case_workflow.py` (36), `tests/test_console_web.py` (17), `tests/test_scripted_agent.py` (10), `tests/test_arm_a_boundaries.py` (6); verification log, Milestone 5 |
| 6 | **Implemented and verified** (Appendix C, M6: real-Postgres tests pass for idempotency atomicity, concurrent execute, duplicate prevention, timeout-after-commit reconciliation, lease recovery, approval invalidation) | `tests/test_execution_postgres.py`, `tests/test_write_path_postgres.py`, `tests/test_worker_postgres.py`, `tests/test_audit_postgres.py`, `tests/test_mock_api_postgres.py`; `scripts\compose_check.ps1 -Browser`; verification log, Milestone 6 |
| 7 | **Implemented and verified** (Appendix C, M7: arm B works; Playwright happy path and self-approval block pass) | `tests/browser/test_arm_b_e2e.py` (offline and against the stack), `tests/test_arm_b_defects.py`, `tests/test_arm_b_console.py`, `tests/test_arm_b_rules.py`, `tests/test_arm_b_postgres.py`, `tests/test_arm_a_fence.py`, `tests/test_api.py`, `tests/test_metrics_and_day_one.py`; verification log, Milestone 7 |
| 8 | **Implemented and verified** (Appendix C, M8: every loop stop condition and injection test passes on the mock provider; the Claude provider is implemented; its live smoke test **passed on 2026-11-07**, one call with a made-up message, no quality claim) | `tests/test_ai_loop.py`, `tests/test_ai_tools.py`, `tests/test_ai_provider.py`, `tests/test_arm_c.py`, `tests/test_extraction.py`, `tests/test_routing_baseline.py`; verification log, Milestone 8 |
| 9 | **Implemented and verified** (Appendix C, M9: authorization, CSRF, rate-limit, redaction and red-team tests pass on mock and scripted models; OIDC login works locally against a real Keycloak). SEC-19's repeated tests on a real model: **NOT RUN** | `tests/test_security_authz.py`, `tests/test_security_postgres.py`, `tests/test_oidc.py`, `tests/test_red_team.py`, `tests/test_red_team_shared_corpus.py`, `tests/test_security_docs.py`; `security/evidence/oidc-check-2026-11-06.txt`; verification log, Milestone 9 |
| 10 | **Implemented and verified** (Appendix C, M10: thresholds committed before runs; A/B/C reports generated from actual runs; error analysis written). H7 **not tested**: no participants | `benchmarks/benchmark-thresholds.yaml`, `benchmarks/results/`, `benchmarks/reports/heldout/`, `docs/error-analysis.md`, `tests/test_scoring.py`, `tests/test_runner.py`, `tests/test_compare.py`, `tests/test_benchmark_docs.py`, `tests/test_benchmark_postgres.py`; verification log, Milestone 10 |
| 11 | **Built, tests pass; independent peers run 2026-11-12** (Appendix C, M11): MCP Inspector pass, `@ag-ui/client` pass, A2A TCK partial (5 scenario tests fail by design; card 9 of 9 after a fix) | `tests/interop/` (opt-in), `security/evidence/mcp-inspector-run.txt`, `a2a-tck-run.txt`, `ag-ui-client-run.txt`, `tests/test_protocol_auth.py`, `tests/test_mcp_server.py`, `tests/test_a2a.py`, `tests/test_a2a_postgres.py`, `tests/test_ag_ui.py`, `tests/browser/test_ag_ui_panel.py`, `tests/test_protocols_off.py`, `tests/test_protocol_docs.py`; `security/evidence/protocol-token-check-2026-11-11.txt`; verification log, Milestone 11 |
| 12–20 | Planned | `docs/implementation-plan.md` |

## Milestone 11 deliverables
- **Research first:** six protocol documents from primary sources (2026-11-11), RFC-0004, ADR-0071. MCP 2026-07-28, A2A 1.0, AG-UI 1.0 (the 1.1 draft isn't used).
- **Shared:** a resource-server token verifier (PyJWT), one audience per service, 9 of 9 checks against a real Keycloak. A disabled client's last token works until it expires (TD-49).
- **MCP:** six read-only case tools, the same reach as arm C's model; scopes decide which tools a caller sees.
- **A2A:** a reservation specialist and a loyalty coordinator; one open task per case (migration 0011); a real cancel on timeout; SSRF-safe cards and callbacks.
- **AG-UI:** a live view built from stored rows, with no reasoning, arguments or results; a watch-only panel in the console.
- **What building found:** each finding, with the test that now covers it, is in the verification log, Milestone 11, rows 8, 9, 12, 14 and 15.

## Milestone 10 deliverables
- **Held-out verdicts, by code from the pre-registered rules:** H1, H2, H3, H5, H6 supported; H4 not supported; H7 not tested. Case success A 41, B 71, C 78 of 80. False approvals 8, 0, 0.
- **What H3 rests on:** nobody works an escalation in the simulation. If a person did, C and B would be 78 and 77.
- **Conclusion by the evidence:** non-AI fixes deliver most of the value, and AI helps only in certain categories. $1.83 of the $5 cap spent.
- **`evaluations/`:** runner, scoring, verdicts, spending guard, freeze, comparison, sensitivity, final reports, business value, RCA, automation bias, ablations, dashboard.

## Milestone 9 deliverables
- **Authorization:** customer scope on every record, tested by walking the real routes. It found a real bug: the approvals list wasn't scoped.
- **Identity:** OIDC through PyJWT against a real local Keycloak, group-to-role mapping, rate limits in the database, deactivation, one-use recovery links, read-only machine tokens.
- **Governance:** retention, member export and erasure, legal hold, access review.
- **Red team:** on business effects, with models scripted to obey the attacker. Injection isn't solved, and none of these tests has run on a real model.
- **`security/`:** standards with versions, inventory, data flow, threat model, risks, controls, plan, results, runbooks, readiness. No certification or compliance claimed.

## Milestone 8 deliverables
- **The loop** (`app/ai/`): an explicit state machine, with a test per stop condition, five read-only tools, validation against the engine, one repair, then arm B's result.
- **Providers:** a mock, scripted models, and the Claude adapter, behind one port. Live needs a flag, a listed model and a key.
- **Caps and records:** `ai_runs`, `ai_steps`, `ai_spend`. No evidence and no hidden reasoning in records.
- **Documents:** text-layer PDFs and emails by rules, for arms B and C; vision for arm C.
- **Fairness:** ADR-0067 moved D18's married names to arm B. Routing stayed on rules under a rule committed first.

## Milestone 7 deliverables
- **Arm B** (`app/arms/conventional/`, `app/services/conventional.py`): one durable investigation, two identifiers, one evidence view,
  the engine's result with citations, the missing-information loop, overrides with reasons, linked cases under one supervisor limit.
  Each fix maps to a pre-registered defect (`docs/arm-differences.md`). No aggregate score computed (ADR-0048).
- **The fence around arm A** (`tests/test_arm_a_fence.py`): source hashes and scripted paths, recorded first.
- **JSON API** (`app/api/`): the same services and permissions, problem documents, cursor paging, a published contract.
- **Console:** `/metrics`, `/day-one`, the audit timeline with details, axe-core on every page type at two widths.

## Milestone 6 deliverables
- **Eligibility** (`app/domain/eligibility.py`): typed, pure, two clocks, checked against the labeler on the dev split only.
- **Policies** (`app/services/policies.py`, `policy_publishing.py`): versions by checkout date, Postgres full-text search, exact
  excerpts, publishing through checks, approvals ended in the same transaction.
- **State machine** (`app/domain/case_states.py`): every pair tested; reopening with its audit trail.
- **Approval binding** (`app/domain/approval_binding.py`): HMAC over 11 fields, 24-hour expiry, re-checked at approve and
  execute through each arm's own evaluator. Arm A's defects stay, and a test proves it.
- **Execution** (`app/services/write_path.py`): the console queues; the worker runs four steps with no lock across an external
  call. One live credit per stay in the database. Outcome classes and a settle window.
- **Durable worker** (`app/services/jobs.py`, `app/worker.py`): leases on the database clock, heartbeats, recovery, bounded
  retries, dead jobs, duplicate prevention, graceful stop, correlation IDs.
- **Kill switch** (`app/services/kill_switch.py`), tested under concurrency, with its limit stated.
- **Audit:** split database roles (`infrastructure/postgres/sql/app-owner.sql`), a one-shot `migrate` service; guarantees and
  limits in ADR-0058.
- **Principal and purpose documents:** RFC-0001, ADR-0055 to ADR-0061, strategy, scaling (queue and database), debt (TD-12 and
  TD-13 closed, TD-18 to TD-27 added), TCO, onboarding, swap guide, role coverage, tool map, `docs/retrieval.md`.
- **Codex exercise** prepared, not run: `docs/exercises/`.

## After Milestone 6 (2026-11-05)
The owner's real upgrade failed: the role split removed `loyalty_app`'s `CONNECT` on a Milestone 5 volume, which the compose
check's faked old state had hidden. Fixed, with a check that upgrades a volume built by the real Milestone 5 code, in the compose
check and CI (ADR-0058, updated). `/readyz` logs the reason; the worker's health is honest and its failed claims back off.
The owner's stack is upgraded and ready, with their data kept (verification log, Milestone 6, row 57).

## After Milestone 5 (2026-11-03 to 2026-11-04)
- Upgrade path from an existing volume: `/readyz` compares the database with this code's schema head, `stack.ps1 -Action
  up` names the cause, `app.seed` is repeatable, and the compose check runs this path (ADR-0052).
- Private GitHub repository with `main` pushed and a first CI workflow green on it (ADR-0053). Work now goes on branches
  with pull requests.
- The gap the owner found, closing with no evidence (TD-17), is fixed (ADR-0054). A-000010 stays as the audit record.

## Milestone 5 deliverables
- **Arm A, legacy** (`app/arms/legacy/`, `config/legacy/`): rules configuration out of date only where the catalog
  says, a deterministic rules checklist, four evidence screens, a keyword index frozen on 2026-03-15, refund routing.
  Every limit has a defect ID and a test (`docs/legacy-discovery.md` §2a).
- **Shared services** (`app/services/`): case workflow, the thin shared write path (separation of duties,
  idempotency key from the approval, cross-case duplicate refusal, reconciliation by key), the case event log.
- **Console** (`app/web/`): Jinja2 + HTMX (vendored 2.0.11), banner, strict CSP, sessions and CSRF; local demo
  sign-in behind the `IdentityProvider` port; app tables in Alembic revision 0002.
- **Benchmark tooling** (`benchmarks/`): the scripted legacy agent and simulated supervisor; the request loader.
- **Checks:** Playwright end to end (offline and `compose_check.ps1 -Browser`); compose check now uses its own host
  ports so it runs next to the owner's stack.
- ADR-0043 to ADR-0051; legacy discovery, onboarding, swap guide, role coverage, tech debt (TD-12 to TD-16), tool map,
  strategy and scaling updated. Owner's M4 exercise recorded.

## Milestone 4 deliverables
- **Mock customer API** (`mock_customer_api/`): members, stays, ledger (cursor pages), posting queue, tickets,
  adjustments with required idempotency key, status lookup; customer field names; problem+json errors; simulated
  clock; deterministic faults; seed, reset, cleanup; own Alembic migrations; contract `openapi-v1.json` (v1.0.0).
- **App side:** canonical records (`app/domain/customer_records.py`), port (`app/ports/customer_systems.py`), adapter
  (`app/adapters/mock_customer_api.py`), shared mapper (`customer_shapes/`), app placeholder with `/healthz` and
  `/readyz`, app Alembic baseline, `python -m app.seed`.
- **Stack:** `docker-compose.yml` (Postgres 16.15 with per-system roles, mock API, app), two Dockerfiles (non-root,
  read-only, service code only), `.dockerignore`, `scripts/stack.ps1`, `scripts/compose_check.ps1`,
  `scripts/update-local-env.ps1`, make targets.
- ADR-0035 to ADR-0042; swap guide, onboarding, scaling, tech debt, tool map and role coverage updated.

## Work attribution
All work was done by Claude Code (Opus 5.5). The owner approved the Milestone 11 plan on 2026-11-11. The owner approved the Milestone 5 plan and its six design choices, approved the
Milestone 6 plan and its ten choices (ADR-0055), and answered the M4 and M5 exercises. No other tool touched the repository.
