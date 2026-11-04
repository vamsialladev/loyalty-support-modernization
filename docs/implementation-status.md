# Implementation status

**Last updated:** 2026-11-04 · **Current milestone:** 5 of 20 complete · **Next:** Milestone 6 (eligibility, policy
retrieval, state machine, approval binding, execution, reconciliation, durable worker), after the owner confirms the
plan-mode choice (recommended: yes). **Waiting on the owner:** the 30-label review.

## Completion scores (spec Part 0.5)
Counted from `docs/requirements-matrix.md` by `uv run python scripts/matrix_scores.py`. Only "Implemented and
verified" (or "Not applicable") counts as done.

| Score | Done (verified) | Total | % | In progress (unverified / configured / docs) |
|---|---|---|---|---|
| Core product functionality | 25 | 108 | 23% | 4 |
| Benchmarks and evaluation | 14 | 64 | 22% | 2 |
| Actual-tool exercises | 0 | 16 | 0% | 3 |
| Protocol labs | 0 | 16 | 0% | 0 |
| Security controls | 5 | 55 | 9% | 5 |
| Owner's demonstrated understanding | 0 | 3 | 0% | 1 |
| Other tracked work (not a Part 0.5 score) | 36 | 107 | 34% | 13 |

369 requirements: Tier 1: 190, Tier 2: 102, Tier 3: 27, Tier 4: 50.

New in M5: legacy arm A in the browser (ARMA-01), its limits mapped to the catalog (ARMA-02), the scripted legacy
agent (ARMA-03, new row), instrumentation (LEG-02), no self-approval (WP-04). Started but not done (still `Planned`
with progress noted in the matrix): sign-in (SEC-07), the shared write path (WP-02, WP-05, WP-07–WP-09), app tables
(DB-01), the console (UI-01, PROF-02, SEC-17), browser tests (TEST-05), identical safeguards across arms (ARMS-01).

## Milestones

| M | Status | Evidence |
|---|---|---|
| 1 | Implemented and verified | `tests/test_repo_guidance.py`, `tests/test_matrix_scores.py` |
| 2 | Implemented and verified | `tests/test_discovery_docs.py`, `tests/test_preregistration.py`; pre-registration `1f8b8e6` |
| 3 | Implemented and verified | `tests/test_generator.py`; `scripts\data.ps1 -Action verify` identical |
| 4 | **Implemented and verified** (Appendix C, M3-4: `docker compose up`, migrate and seed succeed from scratch; contract tests pass) | `tests/test_mock_api.py` (41), `tests/test_compose.py`, `tests/test_app_shell.py`, `tests/test_mock_api_postgres.py` (6, real Postgres); `scripts\compose_check.ps1` passed; verification log, Milestone 4 |
| 5 | **Implemented and verified** (Appendix C, M5: legacy arm A completes a case end to end in the browser) | `tests/browser/test_legacy_e2e.py` (2, offline and against the stack), `tests/test_legacy_rules.py` (26), `tests/test_legacy_screens.py` (14), `tests/test_case_workflow.py` (36), `tests/test_console_web.py` (17), `tests/test_scripted_agent.py` (10), `tests/test_arm_a_boundaries.py` (6); verification log, Milestone 5 |
| 6–20 | Planned | `docs/implementation-plan.md` |

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
All work was done by Claude Code (Opus 5.5). The owner approved the Milestone 5 plan and its six design choices and
answered the M4 exercise. No other tool touched the repository.
