# Implementation status

**Last updated:** 2026-10-29 · **Current milestone:** 4 of 20 complete · **Next:** Milestone 5 (legacy arm A, runnable
end to end in the browser), after the owner confirms the plan-mode choice. **Waiting on the owner:** the 30-label
review, and two local values in `.env` (`APP_DB_PASSWORD`, `MOCK_API_DB_PASSWORD`) before the stack runs on it.

## Completion scores (spec Part 0.5)
Counted from `docs/requirements-matrix.md` by `uv run python scripts/matrix_scores.py`. Only "Implemented and
verified" (or "Not applicable") counts as done.

| Score | Done (verified) | Total | % | In progress (unverified / configured / docs) |
|---|---|---|---|---|
| Core product functionality | 22 | 108 | 20% | 4 |
| Benchmarks and evaluation | 12 | 63 | 19% | 2 |
| Actual-tool exercises | 0 | 16 | 0% | 3 |
| Protocol labs | 0 | 16 | 0% | 0 |
| Security controls | 5 | 55 | 9% | 5 |
| Owner's demonstrated understanding | 0 | 3 | 0% | 1 |
| Other tracked work (not a Part 0.5 score) | 36 | 107 | 34% | 13 |

368 requirements: Tier 1: 189, Tier 2: 102, Tier 3: 27, Tier 4: 50.

New in M4: the mock customer systems, their contract, persistence and fault injection, the app's port and adapter, and
the container stack. Still no case workflow, console, arm or app write path.

## Milestones

| M | Status | Evidence |
|---|---|---|
| 1 | Implemented and verified | `tests/test_repo_guidance.py`, `tests/test_matrix_scores.py` |
| 2 | Implemented and verified | `tests/test_discovery_docs.py`, `tests/test_preregistration.py`; pre-registration `1f8b8e6` |
| 3 | Implemented and verified | `tests/test_generator.py`; `scripts\data.ps1 -Action verify` identical |
| 4 | **Implemented and verified** (Appendix C, M3-4: `docker compose up`, migrate and seed succeed from scratch; contract tests pass) | `tests/test_mock_api.py` (41), `tests/test_compose.py`, `tests/test_app_shell.py`, `tests/test_mock_api_postgres.py` (6, real Postgres); `scripts\compose_check.ps1` passed; verification log, Milestone 4 |
| 5–20 | Planned | `docs/implementation-plan.md` |

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
All work was done by Claude Code (Opus 5.5). The owner approved the plan and its four design choices and answered the
M3 exercise. No other tool touched the repository.
