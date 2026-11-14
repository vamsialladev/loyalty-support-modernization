# Scaling and limits

> **Early draft** (PURP-04). All figures are **estimates** until a load test or a run measures them. Sections are
> added as components exist: data volume (M3), queue and database (M6, M12), model cost (M8, M10), team size.

## Assumed baseline
About 320 missing-points requests a month for two properties (assumption A1), 6 agents and 2 supervisors (A5).

| Dimension | 1× (baseline) | 10× | 100× | First thing that breaks (estimate) | Planned response |
|---|---|---|---|---|---|
| Requests | ~320/month | ~3,200/month | ~32,000/month | Supervisor approval capacity, before any software limit | Approval limits by amount and risk; batch review for low-value adjustments (policy decision for the sponsor) |
| Model cost | not measured yet | — | — | — | Measured in M10; routing to a cheaper model only if the benchmark shows no quality loss |
| Queue and database | 155 investigations in 2 min at the load test's baseline stage (measured, M12) | throughput fell past 8 virtual agents (measured) | — | The single app process, likely its 1-CPU limit (inferred) | More app processes first, then more workers (Milestone 12 section below) |
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

## Console and write path (Milestone 5)

Not load-tested (Milestone 12). **Estimates** and design limits only.

| Dimension | Today | What breaks first at 10x / 100x (estimate) | Planned response |
|---|---|---|---|
| Customer-system calls per case | Arm A makes about 6–10 calls per case (four screens, attach re-reads, the duplicate check's ledger read) | The customer platform's rate limit, long before the app | Arm B consolidates reads (Milestone 7); cache only where authorization allows (B.12) |
| Execution | **Milestone 6: moved to the worker;** see the next section. One upstream write per approval | — | Done |
| Case event log | One row per step, unique (case, step) | **Milestone 6:** step numbers are now taken under the case lock, tested with 12 concurrent writers | Done |
| Sessions | One row per sign-in, never cleaned up | Table growth over months | A retention job with the other retention rules (spec C.3) |
| Scripted agent | Not measured in Milestone 5 (mechanics only) | Not a production path | Benchmark runs in Milestone 10 report their own timings, labelled "scripted, not human timing" |

## Queue and database (Milestone 6)

**Nothing here is measured under load; every figure is an estimate.** The Milestone 12 load test replaces them. What is measured:
8 workers claimed 50 jobs each exactly once (`tests/test_worker_postgres.py`). That proves correctness, not throughput.

| Dimension | Today | What breaks first at 10x / 100x (estimate) | Planned response |
|---|---|---|---|
| Job volume | About 320 requests a month (A1); only a fraction reach execution. One worker handles one job at a time | Not the queue. At 100x (about 32,000 a month, about 1,100 a day) a single worker still has room if each job takes seconds; **the customer platform's rate limit comes first** | More worker processes. `SKIP LOCKED` lets them share without waiting. Honour `Retry-After` (built) |
| Calls per execution | About 4 reads to re-check, 1 write, plus lookups if uncertain | Upstream rate limits, as above. Approve and execute each add a re-check | Arm B consolidates reads (M7); a per-customer limiter if a vendor's limits need one |
| Jobs table growth | One row per job, never deleted | Claim query slows once finished rows dominate. The claim index includes status, so this is slow rot, not a cliff | The retention job (spec C.3) deletes finished jobs |
| Polling | Each idle worker runs one claim query a second | Trivial at a few workers; visible at hundreds | Back off when idle, or `LISTEN/NOTIFY` |
| Row locks | One short lock per case, none across a network call | Contention only on one case, which real traffic rarely hits | None needed unless a case gets very busy |
| Case event log | Step numbers are taken under the case lock, one writer at a time per case | Fine: the serialization is per case, not global. Table growth is the limit | Partition by month if a customer keeps years online |
| Audit retention | `case_events` and `system_events` can't be deleted by the app role | Unbounded growth by design | A retention job run as the owner role, with its own audit (M12, spec C.3) |
| Primary database | One Postgres holds business data, search, queue and audit | **The first real limit is write capacity shared by all four.** Estimate: far above this volume; unknown until measured | Measure in M12. Move the queue out only if the measurement says so |

**First thing that breaks, overall (estimate):** supervisor approval capacity, then the customer platform's rate limits, then
the primary database. The queue itself is unlikely to be first.

**Team size:** the write path takes care to change. A second engineer can add an arm without touching it, because arms plug in
through `arm_review.review_for`.

## Arm B and the console (Milestone 7)
- **Reads per investigation:** several customer-system calls, more when a member has linked profiles. Not measured under load: Milestone 12.
- **What breaks first:** the family-name search on a real platform, then the metrics page, which scans whole tables (TD-33).
- **Row locks:** the group limit locks one group's cases for one short transaction, with no customer call inside it, so unrelated cases
  don't wait on each other.
- **Not measured yet:** throughput, and page times under load. No number here is a result.

## The AI loop (Milestone 8)
- **Cost per case:** measured in Milestone 10, about $0.0017 at list price (`benchmarks/reports/heldout/variability.md`).
- **What breaks first:** the provider's rate limit, then per-run tokens as documents grow. `context_chars` caps the second; the worker's job queue absorbs bursts for the first.
- **Concurrency:** one worker runs one job at a time, so more cases means more workers. Each run holds no lock and no open transaction during a model call.

## Rate limits and security (Milestone 9)
- **Every signed-in request writes one row** to `rate_limits`, under a row lock, so each person's requests run one at a time at that point. Cost not measured. Milestone 12's load test measures it. What would change it: a shared cache, at the price of another system to run.
- **`rate_limits` grows** with people and addresses. Old windows are overwritten per key rather than deleted, so growth follows the number of distinct keys.
- **Retention** scans resolved cases daily. Fine at this size; an index on status and update time is the next step.

## The benchmark (Milestone 10)
- **Measured per case on the live model, one at a time:** about $0.0017 at list price, worst investigation p50 7.8 s, p95 11.6 s. One worker does about 5 to 6 cases a minute, so the assumed 320 a month is well within one worker.
- **What breaks first:** nothing here measures load. Milestone 12 does. Live held-out takes about 14 minutes a run at concurrency 1.

## Protocols (Milestone 11)
- **MCP is stateless** (2026-07-28: no sessions), so it scales out behind a load balancer like the API. Each call is
  one rate-limit write plus one audit row, the same per-request cost as REST (estimate; not load-tested).
- **AG-UI holds a connection per viewer** and polls the database every half second while a run is active, for at most
  two minutes. At 100 concurrent viewers that's about 200 small queries a second (estimate). What breaks first: the
  connection pool, then the database. The response: Postgres `LISTEN`/`NOTIFY` or a shared cache in front of the
  stored rows, so viewers don't each poll.
- **A2A** adds one table row per request and keeps at most one open task per case. The specialist's own task store is
  in memory (a lab): two replicas wouldn't share tasks. A real partner agent would run its own durable store.
- **Token checks are local** (no call to the issuer per request), so the issuer isn't a bottleneck; the price is
  TD-49 (a disabled client's last token works until it expires).

## Load test (Milestone 12)

**Measured** on the owner's laptop, 2026-11-14, with `scripts\load_test.ps1`: the default Compose stack, mock customer
API, mock AI, synthetic data. **Not production capacity.** Report: `performance/reports/2026-11-14-local.md`;
profile: `docs/load-profile.md`.

| Stage (virtual agents + supervisors) | Requests/s | API p95 | Investigation p50 | Max queue depth / oldest | Failures |
|---|---|---|---|---|---|
| baseline (2 + 1) | 9.1 | 78–160 ms | 1.7 s | 2 / 3 s | 0 |
| x4 (8 + 2) | 16.5 | 340–918 ms | 3.5 s | 8 / 4 s | 0 |
| x10 (20 + 4) | 12.8 | 1.4–2.6 s | 8.9 s | 16 / 9 s | 0 |

- **Measured:** no failures; throughput peaks at x4 and falls at x10 while latency climbs, with the queue short
  throughout. Postgres stays at 7–8 connections with a cache hit over 99.7% and no deadlocks.
- **Inferred, not measured:** the limit is the single app process (one uvicorn process, 1 CPU in Compose). CPU
  wasn't sampled during the run.
- **Estimates, unchanged:** 100× the declared volume (32,000 requests a month) is about 1,500 a business day,
  what the baseline stage's rate (about 77 a minute) clears in about 20 minutes. So volume alone isn't the first limit; supervisor approvals
  are (top of this file). A hosted deployment's limits (network, the customer API's own rate limit, the model
  provider's limits) aren't measured here.
- **Next measurements (Milestone 13 or a pilot):** CPU per container during the run, the same stages with
  `--workers 2` and two worker containers, and `pg_stat_statements` turned on.
