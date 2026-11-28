# Business continuity and disaster recovery (ENT-36; documentation only, as the spec asks)

What keeps working when a part fails, and how the system comes back. The provider-outage behaviour is drilled (D1),
and so is the restore (D4). The rest is the approach, stated plainly as design, not as measured availability.

## When the model provider is down
- **Arms A and B don't use a model,** so they work as normal. Agents can work every case without AI.
- **Arm C falls back to the engine's deterministic result** and says so (`fallback: provider_failures`). It never
  shows a proposal from a failed run (drill D1, passed 5 of 5).
- **Amounts and eligibility never depend on the model:** the engine computes them, and a proposal has no amount field.
  So an outage costs the agents some help, and no money.
- **To choose:** send arm C's cases to arm B for the duration, or keep arm C on and let it fall back case by case.
  Both are safe.
- **A second provider** (Claude through Amazon Bedrock) is configured but not built (ENT-13, no AWS access). It would
  be a fallback, not a failover: the same prompts, re-evaluated first, because a different model isn't the same arm.

## When the customer's loyalty system is down
Investigations wait and retry. No case shows evidence it couldn't read, and nothing posts. Drill D2 passed: a 16 s
outage recovered on its own. A longer one would leave investigations dead until they're requeued (BL-M13b-02).

## Disaster recovery approach
| | Target (proposed) | Measured | How |
|---|---|---|---|
| **Compose stack** | RTO 1 hour, RPO 24 hours | **RTO 5.5 s** (restore and grants 0.22 s) on a GitHub runner, with a small synthetic database (drill D4, run 46153749325); not a production estimate | A daily `pg_dump`, plus restore steps (`docs/backup-restore.md`) |
| **AWS reference path** | RTO 1 hour; RPO set by RDS point-in-time recovery from transaction logs (not checked against AWS's pages here) | Not measured: never applied | RDS automated backups, 7 days in staging and 14 in production, and point-in-time restore into a new instance (`infrastructure/terraform/aws/rds.tf`, validate only; `docs/backup-restore.md`) |
| **Public demo** | Not a target: it resets every day | Not applicable | Re-seeded on its next start; Neon's own restore window (`docs/backup-restore.md`) |

Targets are proposals for this simulated engagement. A real customer sets their own from the business's tolerance,
not from what's convenient to build.

## What a restore must never do (ROLL-03)
- **Replay a completed posting.** The customer's system keeps what really posted. The idempotency key and
  reconciliation stop a second posting (drill D4).
- **Bring back access that was revoked.** Sessions, API tokens and break-glass grants revoked after the backup must
  be revoked again before anyone signs in (drill D4).
- **Weaken the audit trail.** Audit history stays append-only after the grants are re-applied (drill D4).
