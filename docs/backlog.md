# Backlog

New ideas land here with a proposed tier. **Nothing here is built until the owner approves it** (spec Part 0.7).
Approved items move into `docs/requirements-matrix.md` with an ID.

## Owned by Stage 10 (a separate future project; not built here)

| Item | Why it's Stage 10 | Stage 9's only touch point |
|---|---|---|
| Kafka / event-driven posting pipeline | Separate system and skill set | Stage 9 may note that some missing-points root causes are posting-pipeline failures; Stage 10 investigates them |
| Incident investigation and AIOps over telemetry | Needs a telemetry corpus Stage 9 doesn't produce at scale | Stage 9 emits OpenTelemetry traces Stage 10 could consume |
| Outbox pattern at scale | Stage 9 uses a database-backed job queue and idempotency, not a broker | Reconciliation design notes reference it |
| Java services | Out of Stage 9's Python stack | none |
| Workflow-automation platforms | Stage 9 documents when they'd help (decision guide) but doesn't build on one | `docs/decisions.md` decision guide (Milestone 2) |

## Ideas awaiting the owner's decision

| Date | Idea | Proposed tier | Source | Decision |
|---|---|---|---|---|
| 2026-10-28 | Register Stage 9 in `eval-harness` through a small reviewed PR (its schema allowlists only p1/p2 and two properties) | 2 (already required as REUSE-03) | continuity review | Required by the spec; PR prepared in Milestone 10, merged only with the owner's OK |
| 2026-10-28 | Use `hotel-ai-platform`'s PII redaction and red-team corpus instead of writing new ones | 1 (REUSE-08) | continuity review | Evaluated in Milestone 9 |
| 2026-10-28 | Install gitleaks, Terraform, Trivy and syft locally so CI checks can also run on the owner's machine | 2 | access audit | Owner to decide in Milestone 12 (installs are free; listed in `docs/tool-access-matrix.md`) |
