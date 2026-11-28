# Ownership and escalation matrix (ROLL-04)

Who owns each part of the running system, who backs them up, and where it goes next. Roles are **proposed** for this
simulated engagement (`docs/governance.md` has the responsibility boundaries and the RACI); a real customer puts names
here at handover. L1 is first response, L2 the owning team, L3 the specialist or decision-maker.

| Component | Owner (L2) | Backup | Escalate to (L3) | Runbooks and drills |
|---|---|---|---|---|
| App and console | Application team | Platform team | Incident commander | `app-not-ready.md`, `error-rate.md` |
| Worker and job queue | Application team | Platform team | Incident commander | `queue-backlog.md`, `dead-jobs.md`; drills D3, D2 |
| Adjustments: execution, reconciliation, kill switch | Application team, with the supervisors' lead | Sponsor (business decision to stop or resume) | Sponsor and Security | Drills D5, D7; `docs/rollback.md` |
| Arm C: model, prompts, prompt caching | AI operations owner | Application team | Sponsor, for any model or prompt change | `ai-quality-drift.md`, `ai-spend.md`, `prompt-cache.md`; drills D1, D6 |
| App database: backups, restore | Platform team | Application team | Incident commander | `docs/backup-restore.md`; drill D4 |
| Identity, sessions, break-glass | Identity team (client) | Security | Security | `auth-failures.md`; `docs/break-glass.md` |
| Secrets and credentials | Platform team | Security | Security | `docs/credential-rotation.md`; SEC-21 (`docs/incident-exercises.md`) |
| Protocol doors (MCP, A2A, AG-UI) | Application team | Security | Security | `protocol-read-volume.md` |
| The customer's loyalty system (upstream) | The customer's platform owner | Their vendor | The customer's incident process | Drill D2 (an outage) |
| Public demo (Cloud Run + Neon) | Owner (this portfolio) | None | None | `docs/hosting-cloud-run.md` |

## Escalation rules
- **Anything that might post wrongly:** L1 engages the kill switch first, then escalates. Stopping is never wrong;
  resuming is the sponsor's call.
- **A security event of severity 4** (`app.services.security_events`, for example a break-glass grant): Security is
  told within the hour, even when it was planned.
- **The customer's system is down:** nothing in this system can fix it. Watch the retries, tell the customer's
  owner, and requeue dead jobs once it's back (drill D2 found a 16 s outage used all 5 attempts; BL-M13b-02).
