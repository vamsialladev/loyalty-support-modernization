# Incident response guide (ROLL-04; spec F.3, C.10)

What to do when something goes wrong in production: how serious it is, the first 15 minutes, who decides, how to
stop things, what evidence to keep, and the report to write. Roles are **proposed** (`docs/ownership-matrix.md`);
a real customer names the people. The runbooks for each alert are in `docs/runbooks/`. An example report from an
executed drill is in `docs/incident-reports/`.

## Severity
| Level | Meaning | Examples | Respond |
|---|---|---|---|
| **SEV1** | Money or a real member affected, or data exposed | A wrong posting reached a member's ledger; another customer's case was visible; a secret leaked | At once, any hour. Incident commander from Security |
| **SEV2** | Postings or service stopped, or a wrong result reached a person who had to catch it | The worker is down and execution is stuck; a wrong recommendation was approved, then caught | Within 1 hour, working hours |
| **SEV3** | Degraded, and caught by code | The customer's system is slow and jobs retry; a model outage, so arm C falls back | Within a working day |
| **SEV4** | A measurement or reporting error | A dashboard or a metric is wrong | Next planned work |

## The first 15 minutes
1. **Stop the harm.** If postings may be wrong, engage the **kill switch** (`/admin`, an administrator). It stops
   every new posting at once, and is audited. If AI may be wrong, use the prompt-cache switch or turn arm C off for
   new cases. Emergency administrator access, if no administrator can be reached: `docs/break-glass.md`, at most 60
   minutes, granted by a second person.
2. **Name an incident commander** (Security for SEV1, the application team's lead otherwise) and one channel.
3. **Keep the evidence** before anything restarts:
   - the security events export (`python -m app.services.security_events --since <date>`);
   - the affected cases' audit trails;
   - `docker compose logs app worker mock-api`, which are JSON lines with `correlation_id` and `trace_id`;
   - the dead-jobs list.
4. **Find out what really posted.** Reconciliation asks the customer's system by idempotency key. A case in
   "Execution unknown" is settled that way and never retried blindly (drill D5).
5. **Tell the people who need to know:** the sponsor, and for SEV1 the data owner and Security. For member impact,
   the customer's own process decides what members are told.

## After it's over
- **Recover:** release the kill switch, then check that each held adjustment posts once (drill D7). Requeue dead
  jobs only once the cause is fixed (`docs/runbooks/dead-jobs.md`).
- **Restore from backup only as a last resort** (`docs/backup-restore.md`). Postings made after the backup stay in
  the customer's system, and access revoked after it must be revoked again. Drill D4 tests both.
- **Write the report** within 2 working days, using the template below. Add AI-related incidents to
  `docs/ai-incident-register.md`.

## Report template
```
# <date> <short title> (<SEV>)
Summary: two sentences.
Timeline (UTC): detected, stopped, fixed, closed. Each line says how it was known.
Impact: cases, members, points, money. "None" only if checked, with how.
Cause: what failed, and why the controls did or didn't catch it.
What held: the controls that worked.
Fix: the change, and the test or drill that now holds it.
Follow-ups: each with an owner and a date.
```
