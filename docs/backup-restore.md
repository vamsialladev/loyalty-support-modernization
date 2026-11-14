# Backup and restore

Spec F.2; DEL-09; ADR-0085. **Instructions, not a measured result:** a timed restore drill is Milestone 13. All data
is synthetic. Two databases matter: the app's (`loyalty`), and the mock customer API's (`mock_customer_api`, a
stand-in for the customer's own system, which the customer backs up).

## What must be recoverable
| Data | Why | Where |
|---|---|---|
| Cases, events, adjustments, approvals, executions | The audit record and money movements | app database |
| Jobs | Work in flight; a lost job is a stuck case | app database |
| AI runs and spend totals | What the spending caps count | app database |
| QA samples, feedback | Online quality evidence | app database |
| Policy versions | Which rule was in force when a case was decided | app database (and `policies/` in Git) |
| Secrets | `.env` locally; Secrets Manager or the host's dashboard when hosted | never in a backup file |

## Local and Compose
Back up (custom format, compressed, as the owner role):

```powershell
docker compose exec -T db pg_dump -U loyalty_owner -d loyalty -Fc -f /tmp/loyalty.dump
docker compose cp db:/tmp/loyalty.dump .\backups\loyalty-$(Get-Date -Format yyyy-MM-dd).dump
```

Restore into an empty database, then check:

```powershell
docker compose cp .\backups\loyalty-YYYY-MM-DD.dump db:/tmp/loyalty.dump
docker compose exec -T db createdb -U loyalty_owner loyalty_restore
docker compose exec -T db pg_restore -U loyalty_owner -d loyalty_restore --no-owner --role=loyalty_owner /tmp/loyalty.dump
```

Then point a copy of the app at `loyalty_restore` and confirm `/readyz` is ready, case counts match, and the latest
`case_events` step matches the source. **Re-apply the role grants** (`infrastructure/postgres/sql/app-owner.sql`): a
dump made with `--no-owner` doesn't carry them, and append-only audit depends on them (ADR-0058). `backups/` is
Git-ignored; a dump holds personal data in a real deployment, so encrypt it and keep it off laptops.

## AWS reference path
- **Automated backups:** RDS keeps daily snapshots plus transaction logs for point-in-time recovery: 7 days in
  staging and 14 in production (`infrastructure/terraform/aws/rds.tf`). Encrypted with the project's KMS key.
- **Restore:** RDS restores into a **new** instance (point in time or snapshot). Then point the services'
  `DATABASE_URL` secrets at it, run the migrate task, and check as above. The old instance stays until the new one
  is confirmed.
- **Deletion:** production has deletion protection, and a final snapshot is taken on delete.

## Render + Neon (the demo)
Neon's free plan keeps a short restore window (its own point-in-time history); the demo's data is synthetic and
reset on a schedule, so a lost demo database is re-seeded, not restored (`docs/hosting-options.md`).

## What a backup doesn't fix
Retention and data-subject erasure don't reach backups: erased data lasts until the backup expires
(`docs/known-limitations.md`). A restore brings back what was erased after the backup was taken, so erasures since
then must be re-applied. The retention log (`retention_applied`, `data_subject_erasure` events) lists them.

**Proposed targets** (not measured; `docs/slos.md`): RPO 5 minutes (point-in-time recovery), RTO 2 hours.
