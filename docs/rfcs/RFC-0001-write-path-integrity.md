# RFC-0001: Approvals, idempotency, reconciliation and durable jobs
Status: accepted      Milestone: 6      Author: Claude Code (Opus 5.5), for the owner      Date: 2026-11-04

Approved by the owner on 2026-11-04, with the ten recommended choices (D1–D10) below. Decisions: ADR-0055 onward.
Everything here is a simulation with synthetic data. "Live" in this document means the local stack.
**Built as described on 2026-11-04;** results are in `docs/verification-log.md`, Milestone 6. Differences while building: `FOR NO
KEY UPDATE`, not `FOR UPDATE`, on the case row (a real-Postgres test deadlocked), and the case-row lock sits in `record()` too.

## Context

Stage 9 must prove something stages 0–8 do not: a correct write path for a money-like action (spec Part 0.7). Today's
write path (`app/services/write_path.py`, ADR-0044) is deliberately thin. It runs inside the web request, doesn't bind
an approval to its evidence, and doesn't lock against concurrent executes (TD-12, TD-13).

Requirements: ELIG-01, POL-01 to POL-06, POL-08, WP-01 to WP-11, MOCK-09, JOB-01 to JOB-03, DB-01, TEST-01, TEST-02;
spec B.6, B.7, B.10, B.12 and Appendix C.

Constraints:
- Eligibility, approval, amounts and execution are deterministic Python. Domain code imports no web, session or HTTP code.
- Safeguards are identical across arms (B.8), but the platform must not quietly fix arm A's pre-registered defects
  (D06, D07, D08, D09, D15; ADR-0044). The benchmark depends on both being true.
- Reads and the write go to a customer system that can time out, lose responses and lag.
- Exactly-once business effects need the customer system's cooperation. No local checkpoint can guarantee them (B.9).

### Faults found while reading the current code

| # | Fault | Why it matters |
|---|---|---|
| 1 | A `200` to a write with a malformed body, or one that fails the schema, is treated as "refused, safe to re-run" (`write_path.py:208`) | A `200` means the credit was probably applied |
| 2 | A `409` idempotency conflict returns the case to `Approved` | The key was already used for a different request, so something was applied under it |
| 3 | Reconciliation accepts any record found under the key without comparing it to what was approved | A different amount would count as success |
| 4 | One "not found" lookup allows a resubmit | Real platforms can lag after a write (`docs/real-system-swap-guide.md`) |
| 5 | With the simulated clock on, reads use the case's received time | A re-check can't see a posting that landed after approval |
| 6 | `loyalty_app` owns the database and runs migrations | An owner can always edit its own tables, so an append-only role is impossible as things stand |
| 7 | A shared re-check using the correct rules would change arm A's results | It would fix D06–D09 for arm A without saying so |

## Options considered

### Where execution runs

| Option | Pros | Cons | Cost |
|---|---|---|---|
| Keep it in the web request; a worker only reconciles | Smallest change; the browser sees the result at once | A crash mid-request leaves a stranded case; slow upstreams hold web workers; breaks "no in-memory work" in spirit | Low now, debt later |
| **All execution through a durable queue (chosen, D1)** | One path, crash recovery by design, retries bounded in one place | The page polls; browser tests need a worker running | One more process |
| External queue (SQS, RabbitMQ) | Better fan-out | A second system to keep consistent with Postgres, which needs an outbox (Stage 10) | Highest |

### How concurrent executes are stopped

| Option | Pros | Cons |
|---|---|---|
| Optimistic `version` only | No locks | The loser needs retry logic everywhere; two approvals for one stay aren't stopped |
| **Short `FOR UPDATE` on the case, plus a partial unique index on one live credit per stay (chosen)** | Clear transaction boundaries; the index holds even if the code has a bug; also closes TD-13's two-approval gap | Must never hold a lock across a network call |
| Advisory locks | Flexible | Invisible in the schema; easy to get wrong with connection pools |

### What an approval binds to

| Option | Pros | Cons |
|---|---|---|
| Status flag (today) | Simple | This is defect D11 |
| Plain SHA-256 (Appendix B's default) | Detects change | Anyone with database write access can edit the row and recompute |
| **HMAC-SHA256, key derived from `APP_SECRET_KEY` (chosen, D3)** | A database writer without the app's secret can't forge one; no new secret | Rotating the secret forces re-approval, which fails safe |

### What "append-only" rests on

| Option | Pros | Cons |
|---|---|---|
| Convention or an ORM guard | Free | Protects nothing |
| Trigger on the table | No role change | The owner can disable it, and the app is the owner |
| **Split the role: a new owner runs migrations; `loyalty_app` gets INSERT and SELECT only (chosen, D4)** | A compromised app role can't rewrite history | One new `.env` password; existing volumes need an upgrade step |
| Hash chain on top | Detects some edits | Whoever can rewrite the table can recompute the chain unless its head is anchored outside; deferred (D4) |

## Decision

### Eligibility and policy
- `app/domain/eligibility.py`: a pure function. Input: canonical records, two times, rules from the policy in force and
  customer configuration. Output: `eligible | ineligible | insufficient_evidence | needs_escalation`, plus action,
  points, reasons and policy references. **Two times:** the claim's received time drives the window and waiting period;
  the as-of time decides which ledger and queue entries count.
- It is written separately from `evaluations/labeler.py`. A test proves neither imports the other, and they are compared
  on the **dev split only**. Held-out data is never touched.
- Arm A keeps its checklist. Arm B and C use the engine from Milestones 7 and 8.
- Policies live in `policy_versions` and `policy_chunks`, selected by checkout date in the property's time zone. Search
  is Postgres full-text. Publishing runs structure, date-overlap, rule-field and golden-outcome checks, then invalidates
  the affected approvals **in the same transaction**. No policy, or more than one in force, returns `needs_escalation`.

### State machine (D2, D6)
New transitions: `Pending approval`/`Approved` → `Investigating` (invalidated or expired); `Executing`/`Execution
unknown` → `Escalated` (conflict or mismatch); `Resolved`/`Escalated`/`Rejected` → `Investigating` (reopened with a
reason). An invalidated approval is never revived: the agent re-requests, which creates a new request, a new approval
and a new key.

### Approval binding (D3, D5, D8)
At request time, store the proposal: member, stay, points, the policy versions in force for the checkout date, and an
evidence hash. At approval, re-read the evidence; if it changed, invalidate instead of approving. Otherwise store the
approver, the expiry (24 hours, per customer) and an HMAC over all of it. At execution, recompute it from fresh reads.

The evidence hash covers only facts about this stay that **the arm actually read**, so an unrelated posting invalidates
nothing and arm A's defects stay intact. The bound policy version is chosen by the platform, not the arm's evaluator, so
publishing invalidates arm A's approvals too while its checklist still ignores that policy (D15 stays). Evidence change
is detected at approve and execute; policy change acts immediately (D9).

### Execution: five steps, no lock across a network call

| Step | Who | What happens | If it crashes here |
|---|---|---|---|
| 1 | Web request | Lock the case, check the switch and state, queue the job | Nothing happened |
| 2 | Worker | Fresh reads; re-run the arm's own evaluator and the ledger check | Job re-runs from step 2 |
| 3 | Worker | Lock the case, re-check everything, record the attempt and `Executing`, commit | Next worker sees `Executing` and treats the outcome as unknown |
| 4 | Worker | Check the switch again, then submit with the key derived from the approval | Same |
| 5 | Worker | Record the outcome | Same |

Outcome classes:

| Upstream result | Meaning | Next |
|---|---|---|
| `200`, valid, matches the approval | Applied | `Resolved` |
| `200`, valid, differs from the approval | Something else was applied | `Escalated`, stay stays blocked |
| `200` malformed or schema mismatch; timeout; lost response; 500, 502, 504 | May have been applied | `Execution unknown` |
| `409` conflict | The key was used for another request | `Escalated`, stay stays blocked |
| `400`, `401`, `403`, `404`, `422` | Refused before applying | `Approved`, nothing applied |
| `429`, `503` | Not processed | Job retries with backoff, same key |

**Reconciliation:** look up by key. Found and matching: `Resolved`. Found and different: `Escalated`. Not found: it counts
as absent only after 2 lookups and a settle window since the last submit; then back to `Approved`, and the job re-runs
the full re-check with the **same key**. `Execution unknown` is never escalated automatically, because that would hide
the uncertainty. If its job goes dead, the case stays visibly unknown and an event is raised.

### Durable worker
Postgres queue with `SELECT … FOR UPDATE SKIP LOCKED`. A partial unique index allows one active job per case and kind.
Leases use the database clock; a lease token stops a worker that lost its lease from writing results; a heartbeat
thread extends it. Backoff is exponential with deterministic jitter and honours `Retry-After`. Retries are bounded, then
the job goes dead. On SIGTERM or SIGINT the worker stops claiming and finishes its current job within a grace period. A
periodic sweep re-queues stranded cases. Correlation IDs run from the request through the job, the events and the
upstream header. Job payloads hold IDs only.

### Kill switch (D7)
A database row, so it reaches web and worker without a restart. Claims hold `FOR SHARE`; toggling takes `FOR UPDATE`,
so once a toggle commits no new claim can pass. Held jobs wait without using up retries. Reads and reconciliation keep
running. If the switch can't be read, adjustments stop. **Stated limit:** a submit already past the last check can land.

### Audit: what it does and does not guarantee
`loyalty_app` has INSERT and SELECT on `case_events` and `system_events`. It stops the app role, or a compromise of it,
from editing or deleting history. It does **not** stop the owner role, a superuser or anyone with backup access. It
doesn't apply on offline SQLite. Timestamps come from the writer's clock. **It isn't tamper-proof, and we don't claim it
is.** Approval and job rows stay mutable; the events record each change.

## Risks

| Risk | How we'd notice | Response |
|---|---|---|
| A posting lands between the re-check and the submit | Over-credit in the benchmark's final ledger | Residual and stated. Narrowing it needs a platform-side conditional credit |
| "Absent" after the settle window, then the old submit lands late, and the case has been re-approved under a new key | Two adjustments for one stay in the ledger | Same-key retries are safe. Across keys, the ledger check catches it only if it landed first. Stated; a real vendor's lag must be measured (swap guide) |
| Upstream forgets idempotency keys after a retention period | A retry after the period double-credits | Open question for each real vendor; bound the age of a retry |
| Worker stops; nothing executes | Queue age grows; the case page says "queued" | Compose health check now; alerts in Milestone 12 |
| Lease too short for a slow call | Duplicate work (safe through the key, but noisy) | Lease is 3× the heartbeat and longer than the adapter's timeouts |
| Dead jobs pile up unnoticed | `job_dead` events | Listed by a CLI now; alert in Milestone 12 |
| Role split breaks an upgrade | Compose check's upgrade path fails | The step is idempotent, and the compose check runs it from an old volume |
| Queue on the primary database limits throughput | Load test (Milestone 12) | Estimates only until then (`docs/scaling-and-limits.md`) |

## Rollout
1. Each step is its own pull request, merged with a merge commit when CI is green. The real-Postgres tests and the compose
   check run for each.
2. Migrations are additive. Approvals created before binding have no hash, so they must be approved again.
3. The role split needs one new `.env` value and one upgrade command. The owner runs them; the exact steps are in
   `docs/onboarding.md`. Because the app must no longer hold migration rights, migrations move from the app's start
   command to a one-shot `migrate` service with the owner's credentials (this replaces part of ADR-0052's decision).
4. No hosted deployment exists, so there is no traffic to migrate. Rollback is `alembic downgrade` plus the previous
   image. The role split isn't reversed automatically; `REASSIGN OWNED BY loyalty_owner TO loyalty_app` undoes it.

## Open questions

| Question | Who decides |
|---|---|
| How long does each real vendor keep idempotency keys, and how long can its lookup lag? | The customer's platform owner, per engagement |
| Is 24 hours the right approval expiry? It's an assumption, not a measurement | The business owner, in a pilot |
| Should publishing need a second person? | The owner; on the tech debt register until a real customer's governance decides |
| Should a daily check compare executed rows with the ledger? | Milestone 13 (drills) |
| Should the audit chain be anchored outside the database? | The security team, if a real customer needs evidence beyond the role |
