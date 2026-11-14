# Rollback

Spec F.2; DEL-08; ADR-0085. Covers the app image, the database migrations, and cases that are in progress while
versions change. Every value here is synthetic, and none of this has run against a hosted environment (none exists).

## The rule: roll the image back, not the schema
Each release is one image (built, scanned and attested by CI, ADR-0084). Rolling back means running the previous
image against the **current** schema. Migrations are written **expand/contract**: a release only adds tables,
nullable columns or indexes ("expand"). Removing or renaming something ("contract") waits for a later release, once
no running version uses it. So the previous image works on the newer schema, and the schema never has to go back
during an incident.

| Where | How to roll back |
|---|---|
| Compose (local, demo) | `git checkout <previous tag>`, then `docker compose up --build -d`. The migrate service runs `upgrade head`, which does nothing when the schema is already newer. |
| AWS (reference path) | ECS's deployment circuit breaker rolls back by itself when a new task never becomes healthy (`infrastructure/terraform/aws/ecs.tf`). By hand: update each service to the previous task definition revision. |
| Render (the demo) | Render's dashboard: the service → Events → the previous deploy → "Rollback". |
| An AI change (prompt, model, limits) | Return those files to the commit named in `benchmarks/results/mock/c-mock-dev/manifest.json` and confirm the release gate passes (`docs/release-gate.md`). |

## Migrations: what reverses safely
All 13 migrations have a downgrade. On a fresh Postgres, CI runs them up to head, down to base and up again on
every pull request (job `postgres`; locally, `scripts\ci_local.ps1`). **"Has a downgrade" doesn't mean "safe to
run in production":** a downgrade that drops a table drops its data.

| Revision | What the downgrade does | Safe on live data? |
|---|---|---|
| 0013 `qa_samples` | drops the QA samples table | **No:** loses QA reviews. Not needed: older code ignores the table |
| 0012 `job_trace_context` | drops one nullable telemetry column | Yes (the value is telemetry only), and also not needed |
| 0011 `a2a_tasks` | drops the A2A task table | **No:** loses A2A evidence requests. Not needed: older code ignores it |
| 0010 security hardening | drops rate limits, recovery and API tokens; removes columns from `users` and `cases` | **No:** signs everyone out and removes legal holds |
| 0009 AI runs, spend, attachments | drops AI runs, steps, spend totals and attachments | **No:** loses the spend record the caps rely on |
| 0008 recommendations, feedback | drops recommendations and feedback | **No** |
| 0007 kill switch, one live credit | drops the switch and the one-credit-per-stay index | **No:** removes a guard against double credits |
| 0006 jobs | drops the job queue | **No:** loses queued and dead jobs |
| 0005 approval binding | removes binding columns | **No:** approvals lose what they were bound to |
| 0004 append-only audit | gives the app role update and delete rights on the audit tables again | **No:** weakens the audit trail |
| 0003 policies, system events | drops policies and the system audit log | **No** |
| 0002 case tables | drops every case table | **No** |

**So in production, nothing is downgraded.** A bad migration is fixed forward with a new one. A downgrade is for a
development database, or for a migration that never reached live data.

## Cases in progress while versions change
- **Jobs:** a job's payload holds IDs only (ADR-0060), so a job queued by one version runs under the next. A job
  kind that the running version doesn't know goes dead with `unknown_kind`, and a person decides
  (`docs/runbooks/dead-jobs.md`). Nothing is guessed.
- **Executions:** an adjustment is executed under its idempotency key, so a version change mid-execution can't
  credit twice; reconciliation settles "execution unknown" (ADR-0061). Before a rollback during execution work,
  switch the kill switch on, roll back, then switch it off.
- **Approvals** are bound to what they approved (ADR-0059). If a rollback changes how evidence is read, the binding
  no longer holds and the approval is invalidated, never silently reused.
- **Sessions** survive an image rollback (they're rows in the database). A schema rollback past 0010 would sign
  everyone out.

## Before any rollback
1. Note the current image digest and the schema revision (`/readyz` says `not_migrated` if the code is older).
2. Switch the kill switch on if executions are running (`/admin`).
3. Roll back the image. Check `/readyz`, one sign-in, one investigation.
4. Switch the kill switch off. Record what happened and why (an incident note), and open the fix-forward change.
