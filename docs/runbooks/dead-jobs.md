# Jobs giving up

**Alert:** `loyalty-dead-jobs`: one or more jobs went dead (`loyalty_jobs_dead > 0`). **Proposed owner:** application
team (L2). Synthetic data only.

**You notice:** the alert; a case shows a system error; `/metrics` shows "jobs that gave up".

1. List them: `docker compose exec worker python -m app.worker --list-dead`. It prints IDs, kinds, cases and error
   codes only, never data.
2. Read the code:
   - `unknown_kind`: a job type this version doesn't know. Usually a rollback left a newer job behind; roll forward,
     or let it stay dead.
   - `lease_lost_attempts_used`: workers kept dying mid-job. Check memory limits and the worker's log.
   - An upstream code (`UpstreamTimeout`, `CustomerSystemError`): the customer system failed every retry.
3. **Before requeueing an execution job,** open the case. An execution may already have reached the loyalty
   platform; reconciliation decides that, never a retry (ADR-0061). If the case says "execution unknown", leave it
   to reconciliation.
4. Requeue only when the cause is fixed: `docker compose exec worker python -m app.worker --requeue <id>`. It's
   recorded as `job_requeued`, a security event.

**Check it worked:** `--list-dead` no longer lists it, the case moved on, and the alert clears.
