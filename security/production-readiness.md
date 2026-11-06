# Production readiness: security gates (spec C.10)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

| Gate | Local / demo | Staging | Production |
|---|---|---|---|
| Authorization tests pass | **Yes** (CI) | Not started | Not started |
| Approval and idempotency tests pass | **Yes** (CI, real Postgres) | Not started | Not started |
| No exposed secrets | **Yes** (gitleaks on the full history, CI) | Not started | Not started |
| Validated configuration | **Yes** (`app.preflight`) | Not started | Not started |
| Findings triaged | `residual-risks.md` | Not started | Not started |
| High-impact risks have accountable decisions | **No:** no real owner exists in a simulation | Required | Required |
| Monitoring and recovery | Partial; Milestone 12 | Required | Required |
| External reviews identified | Penetration test, privacy review, legal: **none done** | Required | Required |

**Maintenance schedule** (each needs a named owner in a real engagement, and keeps its evidence):

| Activity | How often | Evidence |
|---|---|---|
| Dependency and container updates | Weekly (Dependabot) | Merged PRs, `pip-audit` |
| Access review | Quarterly | `/admin/access-review.csv` |
| Provider and model changes | Monthly while live | `docs/ai-system-card.md`, `config/ai/` |
| Protocol upgrades | Quarterly, from Milestone 11 | Contract tests |
| Prompt, model and policy changes | On change | Version files; Milestone 10's evaluation |
| Restore drill | Quarterly, from Milestone 12 | Runbook log |
| Incident exercise | Twice a year | `incident-runbooks.md` notes |
| Retention job | Daily (worker) | `retention_applied` events |
| Exception expiry | Monthly | `residual-risks.md` |
