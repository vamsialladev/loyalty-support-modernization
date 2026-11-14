# Declared load profile

Spec F.1; OPS-01; ADR-0083. **Synthetic, from assumptions, not a customer's measurement.** The load test
(`scripts\load_test.ps1`) runs these stages; its report is in `performance/reports/`.

## Where the numbers come from
- **Requests:** about 320 missing-points requests a month across two properties, with peaks in January and July
  (assumption A1, `docs/customer-discovery.md`). That's about 15 per business day, or about 45 a day at a three-times
  peak. Every request becomes a case, and most cases get one investigation.
- **People:** 6 agents and 2 supervisors (assumption A5). An agent works a case at a time; a supervisor reviews the
  approvals queue and the metrics.
- **Not in this profile:** protocol traffic (MCP and A2A are off by default, and read-only), AG-UI viewers, and the
  model provider (mock AI). They're listed under "not covered" in the report.

## Stages
A virtual **agent** repeats, as fast as the stack answers: create a case from a synthetic dataset request, start its
investigation, open the queue, and read the case until the worker has finished. That is much faster than a person,
so one virtual agent stands for many people. A virtual **supervisor** reads the approvals queue and the metrics page
every 2 seconds.

| Stage | Virtual agents | Virtual supervisors | Seconds | What it stands for |
|---|---|---|---|---|
| `baseline` | 2 | 1 | 120 | Today's team working flat out: more than the 45-a-day peak in two minutes |
| `x4` | 8 | 2 | 120 | Four times that: a bad holiday peak, or a second brand on the same stack |
| `x10` | 20 | 4 | 120 | Ten times: where the single worker and the single app process should show their limits |

## What the stack is during the test
The default Compose stack: one app process, **one worker** (one job at a time, ADR-0060), the mock customer API,
Postgres 16, all on one laptop under Docker Desktop. The per-user rate limit is lifted for the run, because the
virtual users share four demo accounts. Nothing else changes.

## What "good" looks like here (proposed, not an SLO)
- API reads (`GET`) under 500 ms at p95 at `baseline` and `x4`.
- No 5xx at any stage.
- Investigations finish (the worker keeps up) at `baseline`. At `x10`, the queue is expected to grow: one worker is
  the planned first limit, and the fix is more workers (`docker compose up --scale worker=N`), not a faster one.

Proposed SLOs for a real deployment are in `docs/slos.md` (Milestone 12, PR 6), apart from these local results.
