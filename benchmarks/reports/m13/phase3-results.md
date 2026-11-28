# Milestone 13, Phase 3: arm A (no cache) vs arm D (provider prompt caching)

> Real model (claude-haiku-5-5) · SYNTHETIC cases and personal data · paired A/D regression on the frozen held-out split, not a held-out claim. Written by `python -m evaluations.m13_results`; pass marks from `docs/m13-phase3-plan.md`.

| Run | Cases | Case success | False approvals | p50 / p95 / p99 s | Calls | Cache-read share | Later calls reading cache | $ per 1,000 cases | Requeued jobs |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| m13-a-r1 | 80 | 78 | 0 | 8.0 / 12.671 / 15.125 | 296 | 0.0% | 0/216 | $1.71 | 0 |
| m13-a-r2 | 80 | 78 | 0 | 8.53 / 13.766 / 17.875 | 306 | 0.0% | 0/226 | $1.75 | 0 |
| m13-a-r3 | 80 | 78 | 0 | 9.155 / 14.78 / 464.671 | 295 | 0.0% | 0/216 | $1.70 | 1 |
| m13-d-r1 | 80 | 78 | 0 | 7.968 / 11.468 / 15.469 | 293 | 65.7% | 206/213 | $1.19 | 0 |
| m13-d-r2 | 80 | 78 | 0 | 9.188 / 11.952 / 16.593 | 298 | 66.1% | 211/218 | $1.22 | 0 |
| m13-d-r3 | 80 | 78 | 0 | 8.688 / 13.155 / 61.906 | 327 | 66.0% | 233/247 | $1.41 | 0 |

| Pass mark | Result | Pass |
|---|---|---|
| wrong_reuses | `{"value": 0, "how": "none possible: tests/test_prompt_cache.py, request test"}` | yes |
| case_success | `{"value": [78, 78, 78], "floor": 78}` | yes |
| false_approvals | `{"value": [0, 0, 0]}` | yes |
| p95_draft_ready_s | `{"value": [11.468, 11.952, 13.155], "ceiling": 14.78}` | yes |
| cache_used | `{"value": 0.9587, "minimum": 0.9}` | yes |
| cost_per_case | `{"a_usd": 0.001723, "d_usd": 0.001275, "change": -0.26}` | yes |

**Verdict:** all pass marks met.

## Flagged: runs with requeued jobs (kept, as the owner decided on 2026-11-27)

A requeue is the worker recovering from a database error (likely TD-57, the SQLite lock race in the benchmark environment). The pass marks above use every case; this shows how much the requeues moved p95.

| Run | Requeued jobs | p95, all cases (s) | p95 without the requeued cases (s) | Cases left out | How |
|---|---:|---:|---:|---|---|
| m13-a-r3 | 1 | 14.78 | 14.78 | HO-032 | cases 31-40: HO-032 (more AI runs than in every no-cache run) |
