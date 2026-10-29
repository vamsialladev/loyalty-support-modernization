# Scaling and limits

> **Early draft** (PURP-04). All figures are **estimates** until a load test or a run measures them. Sections are
> added as components exist: data volume (M3), queue and database (M6, M12), model cost (M8, M10), team size.

## Assumed baseline
About 320 missing-points requests a month for two properties (assumption A1), 6 agents and 2 supervisors (A5).

| Dimension | 1× (baseline) | 10× | 100× | First thing that breaks (estimate) | Planned response |
|---|---|---|---|---|---|
| Requests | ~320/month | ~3,200/month | ~32,000/month | Supervisor approval capacity, before any software limit | Approval limits by amount and risk; batch review for low-value adjustments (policy decision for the sponsor) |
| Model cost | not measured yet | — | — | — | Measured in M10; routing to a cheaper model only if the benchmark shows no quality loss |
| Queue and database | — | — | — | — | Measured in M12 |
| Team size | 1 engineer | — | — | — | Onboarding doc and starter kit so new engineers can contribute in a day |

## Data volume (Milestone 3)

Measured at 1× on the owner's Windows machine (2026-10-29): about 3,300 members, 6,800 stay records, 3,800 ledger
entries, about 3,900 history cases with 37,000 events, 82 documents; full generation about 5 seconds warm (about 70 seconds on
the first, cold run); operational data about 16 MB of JSONL. The 10× and 100× columns are **estimates** (linear extrapolation), not runs.

| Dimension | 1× (measured) | 10× (estimate) | 100× (estimate) | What breaks first | Planned response |
|---|---|---|---|---|---|
| Stay IDs (`BR-####`, 4 digits) | ~3,400 per property of 9,000 | would exceed 9,000 | — | The 4-digit confirmation format | Generator switches to 5 digits above scale 1.5 (implemented); real customers keep their own formats via the mapping file |
| Generation time | ~5 s warm (~70 s cold) | ~1 min warm | ~10 min warm | Pure-Python record building and pydantic validation | Vectorise the background world; skip per-record validation for bulk rows and validate a sample (TD-08) |
| JSONL size | ~16 MB | ~160 MB | ~1.6 GB | Loading files into memory in tests and analysis | Load into Postgres (M4) and query; stream files instead of reading them whole |
| Benchmark cases | 280 | 280 | 280 | Not volume-bound: cases are fixed quotas | More cases only with more label review capacity, which is the real limit |
| Label review | 30 labels by one reviewer | — | — | Reviewer time, not compute | Second reviewer and a written labelling standard (the stage 3 lesson) |

## API and database (Milestone 4)

Nothing here is load-tested yet (the load test is Milestone 12); every figure is an **estimate** or a design limit.

| Dimension | Today | What breaks first at 10x / 100x (estimate) | Planned response |
|---|---|---|---|
| Mock API workers | One uvicorn process, sync endpoints on a thread pool | Thread pool and the SQLAlchemy connection pool (default 5 + 10 overflow) under concurrent investigations | More workers and an explicit pool size per process; the real customer API's own rate limit is the binding constraint in production |
| Adjustment writes | One transaction per adjustment, idempotency key as primary key | Contention only on the same key (by design); different keys don't block each other | Nothing until measured |
| Ledger reads | Indexed by member and posting time; cursor pages of up to 100 | Members with very long histories (a ledger page per 100 entries) | Date-window filters (the policy only needs 12 months) |
| One Postgres server for both systems | Separate databases and roles (ADR-0036) | The two databases competing for one server's memory and I/O | Separate instances in any hosted deployment |
| Seed | Bulk insert of about 14,000 rows in 1,000-row chunks | Seconds now; minutes at 100x | `COPY` instead of inserts if seed time matters |
