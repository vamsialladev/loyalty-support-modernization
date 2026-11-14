# Queue backing up

**Alert:** `loyalty-queue-backlog`: the oldest waiting or running job is more than 5 minutes old, for 5 minutes
(`loyalty_jobs_oldest_age_seconds`). **Proposed owner:** application team (L2). Synthetic data only.

**You notice:** the alert; investigations stay "requested" in the console; `/metrics` shows "oldest waiting" climbing.

1. Is a worker running? `docker compose ps worker`. If it isn't healthy: `docker compose logs --tail 100 worker`
   (JSON lines; look for `claim failed` or a `job …` line with a `code`).
2. Is the database answering? `docker compose ps db`, and the app's `/readyz`.
3. Is the customer system slow or failing? Search the worker's log for `job retry` lines with `UpstreamTimeout` or
   `CustomerSystemError`. If so, the jobs are backing off as designed; see [error-rate.md](error-rate.md).
4. Too much work for one worker: run another (`docker compose up -d --scale worker=2`). Claims use `SKIP LOCKED`, so
   two workers never take the same job (ADR-0060).
5. Leave dead jobs to [dead-jobs.md](dead-jobs.md); don't requeue them here.

**Check it worked:** "oldest waiting" on `/metrics` falls below a minute, and the alert clears.
