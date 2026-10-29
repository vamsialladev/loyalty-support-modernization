# Implementation status

**Last updated:** 2026-10-29 · **Current milestone:** 3 of 20 complete · **Next:** Milestone 4 (mock customer API,
Postgres, Alembic migrations, Compose, contract tests), after the owner confirms the plan-mode choice. **Waiting on
the owner:** the 30-label review (`evaluations/label-review/review-sheet.csv`, about 45 minutes).

## Completion scores (spec Part 0.5)
Counted from `docs/requirements-matrix.md` by `uv run python scripts/matrix_scores.py`. Only "Implemented and
verified" (or "Not applicable") counts as done.

| Score | Done (verified) | Total | % | In progress (unverified / configured / docs) |
|---|---|---|---|---|
| Core product functionality | 10 | 108 | 9% | 4 |
| Benchmarks and evaluation | 12 | 63 | 19% | 2 |
| Actual-tool exercises | 0 | 16 | 0% | 3 |
| Protocol labs | 0 | 16 | 0% | 0 |
| Security controls | 5 | 55 | 9% | 5 |
| Owner's demonstrated understanding | 0 | 3 | 0% | 1 |
| Other tracked work (not a Part 0.5 score) | 36 | 107 | 34% | 13 |

368 requirements: Tier 1: 189, Tier 2: 102, Tier 3: 27, Tier 4: 50.

The core items done are the data layer (generator, scenarios, policies, dictionary, commands) plus preflight and the
test command. There is still no application: no API, console, arm or write path.

## Milestones

| M | Status | Evidence |
|---|---|---|
| 1 | Implemented and verified | `tests/test_repo_guidance.py`, `tests/test_matrix_scores.py` |
| 2 | Implemented and verified | `tests/test_discovery_docs.py`, `tests/test_preregistration.py`; pre-registration commit `1f8b8e6` |
| 3 | **Implemented and verified** (Appendix C, M3 part: generator reproducible, same seed → same checksum) | `tests/test_generator.py` (reproducibility, integrity, catalog conformance, label independence, leakage, app cannot read labels); `scripts\data.ps1 -Action verify` identical; verification log, Milestone 3 |
| 4–20 | Planned | `docs/implementation-plan.md` |

## Milestone 3 deliverables
- **Purpose recorded first** (commit `f0b3c34`): `docs/project-purpose.md`, CLAUDE.md section, swap guide,
  onboarding, principal artifacts, executive brief, role coverage map, data sources, using-at-a-company, FDE tool map.
- **Generator** `seed_data/generator/` (seed 20261102): 3,286 members, 6,800 stay records, 3,836 ledger entries,
  12 posting-queue items; policies `policies/hg-demo/`; customer mapping `config/customers/hg-demo.yaml`.
- **Benchmark dataset v1** (committed): 280 cases (dev 100, validation 30, held-out 80, stress 30, fairness 40) with
  labels from the independent labeler, `composition.md` with re-weighting factors, `manifest.json`.
- **Legacy history** (regenerated): 3,872 cases, 36,442 events, 1,989 adjustments; 82 documents.
- **Day-one analysis:** `docs/day-one-discovery.md`, `docs/problem-statement.md`, charts, executive brief phase 2;
  `evaluations/financial_model.py`.
- **Label review:** sheet ready, 30 stratified cases.
- ADR-0028 to ADR-0034; catalog change log (fairness set, temporal split, D19 variants).

## Work attribution
All work was done by Claude Code (Opus 5.5). The owner set the project purpose, approved the plan and its four design
choices, and answered the M1 and M2 exercises. No other tool touched the repository.
