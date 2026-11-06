# Technical strategy

> **Early draft** (PURP-04). Short and honest; updated as evidence arrives. Nothing here is built unless the
> requirements matrix says so.

## Target architecture
A modular monolith (FastAPI) with a separate mock customer API, Postgres as the single store (business data, policy
search, job queue, audit), a deterministic domain core, and a bounded AI layer behind a provider interface
(`docs/architecture.md`). Every external system sits behind an adapter.

## Path from this simulation to a multi-customer platform
1. **One customer, synthetic data (now):** prove the write path, the benchmark and the method.
2. **Second customer by configuration (M14):** Cedarpoint Inns as a separate deployment and database, same code.
   If that needs code forks, the configuration model is wrong.
3. **Starter kit (M17):** extract the generic parts (provider interface, adapters, durable jobs, approvals,
   audit, benchmark runner) and prove them on a second domain.
4. **Platform (beyond this project):** shared services for identity, model gateway, evaluation and audit; per-customer
   deployments for data isolation until multitenancy is designed and tested.

## What to standardize (candidates for other teams)
The approval-binding hash and idempotency-from-approval pattern; pre-registered evaluation with A vs B vs C arms;
preflight that never prints secrets; the "rules decide, AI explains" boundary. From Milestone 5: one shared
`WritePath` that every arm (and every future UI) must go through, so safeguards cannot differ by front end; the
browser sends record numbers only and the server re-reads records before they become evidence; one event log for
both audit and instrumentation. From Milestone 6: an approval as an HMAC over the exact action; a re-check that uses each
arm's own view; an idempotency key from the approval; four execution steps with no lock across an external call; a database
index behind every "only one" rule; "unknown" as a real state that nothing may hide; a kill switch that reads as a lock, not a
flag. **Reading this as a standard:** `docs/rfcs/RFC-0001-write-path-integrity.md`.

## Added in Milestone 7
- **Fence every baseline.** A pinned hash plus a behaviour snapshot, written before the change, is cheap, and it's what makes a later
  comparison believable. It's a candidate for the starter kit.
- **Keep arm B a real product, not a straw man.** It's the fallback when AI is down, and it sets the bar AI has to beat.

## What not to build
A general agent framework; a vector database before a measured need; multitenancy inside one database; a workflow
automation platform; anything that lets a model move points.

## Key bets and how we'd know they were wrong
| Bet | Wrong if |
|---|---|
| Most of the value comes from non-AI fixes (catalog prediction) | Arm C beats arm B by a wide margin on held-out cases while B fixes few defects |
| Postgres is enough (search, queue, audit) | Queue latency or full-text relevance misses targets in the M12 load test or M10 retrieval comparison |
| Per-customer deployments are simpler than multitenancy | Operating cost per customer dominates TCO at 10+ customers |
| A deterministic rules engine can express every customer's policy | Cedarpoint's rules (M14) need code changes, not configuration |
| A Postgres queue is enough for durable work (Milestone 6) | The M12 load test shows claiming or heartbeats limiting the primary database at the volumes in `docs/scaling-and-limits.md` |
| A re-check plus idempotency makes a double credit vanishingly unlikely (Milestone 6) | A real vendor's lookup lag outlasts the settle window, or it forgets keys sooner than our retries end (RFC-0001, open questions) |
| Append-only by database role is enough for this stage (Milestone 6) | A real customer's auditors need evidence against an insider with database access: then a hash chain anchored outside, or a separate audit store |
| A legacy baseline modelled from a defect catalog is fair (Milestone 5) | A reviewer finds an arm A limit that isn't in the catalog, or a catalog defect that arm A can't actually exhibit; either is logged as a new experiment (F9) |
