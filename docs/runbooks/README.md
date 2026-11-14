# Runbooks

Step-by-step responses for the situations the alerts in `observability/` point to (spec F.1, C.10; OPS-04,
SEC-20). Each one says how you notice it, what to do, and how to check it worked: the same shape as Stage 5's
runbooks (`hotel-ai-handoff/docs/RUNBOOKS.md`, REUSE-05), with this system's own content.

Everything here is a **simulated engagement with synthetic data**. Owners are **proposed roles**, not people; a
real customer names them at handover (`docs/governance.md`).

| Alert | Runbook | Proposed owner |
|---|---|---|
| App not ready | [app-not-ready.md](app-not-ready.md) | Application team (L2) |
| Queue backing up | [queue-backlog.md](queue-backlog.md) | Application team (L2) |
| Jobs giving up | [dead-jobs.md](dead-jobs.md) | Application team (L2) |
| Error rate high | [error-rate.md](error-rate.md) | Application team (L2) |
| AI spend near its cap | [ai-spend.md](ai-spend.md) | AI operations owner (L3) |
| AI quality drift | [ai-quality-drift.md](ai-quality-drift.md) | AI operations owner (L3) |
| Unusual protocol read volume | [protocol-read-volume.md](protocol-read-volume.md) | Security (L3) |
| Repeated sign-in failures | [auth-failures.md](auth-failures.md) | Security (L3) |

Where to look:

| Where | What |
|---|---|
| Grafana (local, `--profile observability`) | <http://127.0.0.1:3000> → Dashboards → Loyalty support; Explore → traces by trace ID |
| Console | `/metrics` (supervisors, administrators, auditors); `/admin` (kill switch, policy versions) |
| Logs | `docker compose logs app worker mock-api`: JSON lines with `correlation_id` and `trace_id` |
| Worker | `docker compose exec worker python -m app.worker --list-dead` |
