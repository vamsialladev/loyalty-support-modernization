# Implementation status

**Last updated:** 2026-11-05 · **Current milestone:** 6 of 20 complete · **Next:** Milestone 7 (arm B and the complete
server-rendered UI). **Waiting on the owner:** the 30-label review; the `.env` and volume upgrade (`docs/onboarding.md` §4d);
the Codex exercise, when convenient (`docs/exercises/codex-reconciliation-review.md`).

## Completion scores (spec Part 0.5)
Counted from `docs/requirements-matrix.md` by `uv run python scripts/matrix_scores.py`. Only "Implemented and
verified" (or "Not applicable") counts as done.

| Score | Done (verified) | Total | % | In progress (unverified / configured / docs) |
|---|---|---|---|---|
| Core product functionality | 42 | 108 | 39% | 5 |
| Benchmarks and evaluation | 14 | 64 | 22% | 2 |
| Actual-tool exercises | 0 | 16 | 0% | 3 |
| Protocol labs | 0 | 16 | 0% | 0 |
| Security controls | 6 | 55 | 11% | 5 |
| Owner's demonstrated understanding | 0 | 3 | 0% | 1 |
| Other tracked work (not a Part 0.5 score) | 36 | 107 | 34% | 13 |

369 requirements: Tier 1: 190, Tier 2: 102, Tier 3: 27, Tier 4: 50.

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
| 7–20 | Planned | `docs/implementation-plan.md` |

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
All work was done by Claude Code (Opus 5.5). The owner approved the Milestone 5 plan and its six design choices, approved the
Milestone 6 plan and its ten choices (ADR-0055), and answered the M4 and M5 exercises. No other tool touched the repository.
