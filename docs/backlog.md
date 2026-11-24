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
| 2026-11-03 | **Fix the evidence-free close (TD-17).** In `close_case`: while the checklist says `incomplete_evidence`, refuse every rule-based code (`no_adjustment_credited`, `wait_until`, `not_checked_out`, `deny_channel_ineligible`, `deny_claim_window`) whatever the note says. `deny_not_found` needs a logged member or stay search that found nothing. `deny_other` stays available with a note, is logged as an override, and needs at least 20 characters (a length check can't judge quality; overrides stay countable for review). The scripted agent asks for information instead of denying when it has nothing to search with. Tests for each. No catalog or hypothesis change, so no change-log entry: the catalog has no such defect and no prediction uses this path. Recorded as a new ADR | 1 | owner finding on A-000010 | **Approved by the owner 2026-11-04; built** (ADR-0054, ARMA-01) |
| 2026-10-28 | Register Stage 9 in `eval-harness` through a small reviewed PR (its schema allowlists only p1/p2 and two properties) | 2 (already required as REUSE-03) | continuity review | Required by the spec; PR prepared in Milestone 10, merged only with the owner's OK |
| 2026-10-28 | Use `hotel-ai-platform`'s PII redaction and red-team corpus instead of writing new ones | 1 (REUSE-08) | continuity review | Evaluated in Milestone 9 |
| 2026-11-22 | **Sample cases in the public demo after each reset.** A visitor's first screen is an empty queue. After the daily reset, load three or so synthetic cases for visitors to work: one that ends in an adjustment (DV-001's message, which reaches 14,840 points on the live clock; verification log M12 row 41), one where the member isn't found, and one that needs escalation. They would go through the normal intake, as arm B, and count toward the daily cap. Each would need checking on the live clock first, as DV-001 was | 2 (SEC-18, LIVE-02) | owner's question on the live demo | **Approved by the owner 2026-11-23 (arms A, B and C, one going to a posting); built:** `app/services/demo_samples.py`, verification log M12 row 42 |
| 2026-10-28 | Install gitleaks, Terraform, Trivy and syft locally so CI checks can also run on the owner's machine | 2 | access audit | Owner to decide in Milestone 12 (installs are free; listed in `docs/tool-access-matrix.md`) |
