# Milestone 13b plan: operational drills, recovery and incident readiness

Spec F.3 (rollout, drills, recovery), E5 (AI incident register), E6 (break-glass), E8 (continuity). These moved from
Milestone 13 to 13b by the owner's decision of 2026-11-26 (`CLAUDE.md`, ADR-0090). Written 2026-11-27. Mock AI and
synthetic data only. **No drill on the local stack runs until the owner says the machine is free** (the owner,
2026-11-27: Stage 10 is running a long batch).

## Approval checklist (answer yes or no)

| # | Decision | Recommended |
|---|---|---|
| 1 | Start the docs-only and code-only work now (parts A and B below), with no Docker and no live service | **Yes** |
| 2 | Run the seven F.3 drills and the executed SEC-21 exercises on the local Compose stack later, when you say the machine is free (part C) | **Yes** |
| 3 | Build break-glass as code: a time-limited administrator grant that needs a reason, raises a security event and is audited, and ends by itself (default 60 minutes, capped at 4 hours) | **Yes** |
| 4 | Proposed recovery targets: RTO 1 hour, RPO 24 hours for the Compose stack, kept apart from the measured restore | **Yes** |
| 5 | No drill against the live Cloud Run demo or its Neon database (local only; a local drill isn't proof of production availability) | **Yes** |
| 6 | No spend: no live model call, no new cloud resource | **Yes** |

## Scope: eight requirements

| ID | What it needs | Part |
|---|---|---|
| ROLL-01 | Rollout stages (offline evaluation → shadow → limited pilot → human-approved execution → broader rollout), each with stop and rollback criteria tied to measures this repo already has | A |
| ROLL-02 | `docs/drills.md` with **actual** results of the seven F.3 drills, including a **measured** restore | C |
| ROLL-03 | Restoring never replays completed actions or reinstates revoked access; proposed RTO/RPO apart from measured | B (tests), C (measured) |
| ROLL-04 | Runbooks, an incident response guide, an ownership and escalation matrix, and an **example incident report from an executed drill** | A (guide, matrix), C (the report) |
| SEC-21 | Incident exercises: leaked model key, compromised integration credential, unauthorized access, malicious policy, unexpected agent action, compromised dependency, excessive spend | A (tabletop), B and C (executed where possible) |
| ENT-20 | An AI incident register | A |
| ENT-26 | Break-glass: time limits, reason, alert, audit | A (procedure), B (code, if item 3 is yes) |
| ENT-36 | Business continuity during a provider outage; the DR approach (documentation only) | A |

## Part A: documents (now)
1. **`docs/rollout-stages.md` (ROLL-01).** Five stages. For each: entry criteria, what runs, who approves, stop
   criteria and rollback. Criteria use what the repo already measures: the release gate on the frozen mock
   regression, drift signals, QA sampling, the seven alerts and their runbooks, the spend caps, and the execution
   flag. Nothing goes past "limited pilot" without real participants (BIZ-02 is still open).
2. **`docs/incident-response.md` (ROLL-04).** Severity levels, first 15 minutes, who decides, how to stop execution
   (the execution flag), how to stop AI (the kill switch), evidence to keep, and the post-incident report template.
   It links the existing runbooks in `docs/runbooks/` rather than repeating them.
3. **`docs/ownership-matrix.md` (ROLL-04).** Each component and runbook gets an owner role, a backup and an escalation
   path. Roles only, since this is a simulation with one owner. Real names come with a real customer.
4. **`docs/ai-incident-register.md` (ENT-20).** The format: date, what happened, the harm or near harm, detection,
   the controls that held or failed, the fix and the test that holds it, and status. It starts with **real** entries
   only, taken from the verification log where the AI or its measurement went wrong. Drills add entries, each marked
   "drill". Nothing is invented.
5. **`docs/break-glass.md` (ENT-26).** When break-glass is allowed, who may grant it, and the reason it requires. The
   time limit, the alert, the audit trail, and the review afterwards.
6. **`docs/continuity.md` provider-outage section (ENT-36).** Arms A and B work without a model. Arm C degrades to
   "needs a person", since the harness already stops on provider errors. Recovery and the DR approach are
   documentation only, as the spec says.
7. **SEC-21 tabletop scripts** in `docs/incident-exercises.md`. One per scenario: the trigger, the expected
   detection, the steps, the evidence to collect, and the pass criteria. Each is marked "tabletop" until executed.

## Part B: code and tests that need no stack (now)
1. **Restore never replays (ROLL-03).** Unit and SQLite tests: after a restore to an earlier snapshot, a completed
   adjustment's idempotency key still refuses a second posting, and reconciliation finds the gap instead of
   re-executing. A revoked session or key stays revoked. The Postgres variants run in CI's Postgres job.
2. **Break-glass (ENT-26, if item 3 is yes).**
   - A CLI command grants an administrator session for N minutes, with a required reason.
   - It records a security event (ECS export) and an audit row.
   - Every request made in the session is tagged `break_glass`, and the grant expires on its own.
   - Tests cover expiry, a missing reason, the audit row, and a second grant while one is active.
3. **Executed SEC-21 exercises that pytest can run.** For example:
   - excessive spend against the stored caps;
   - unexpected agent action against the tool allowlist;
   - malicious policy against the publishing approval;
   - compromised dependency against the lockfile audit.

   Each records its actual result.

## Part C: drills on the local Compose stack (waits for "the machine is free")
The seven F.3 drills, each with real timings and outputs in `docs/drills.md`:
1. Model/provider outage: mock provider faults. Arm C stops safely.
2. Customer API outage: the mock API's fault switch. The circuit breaker and backpressure (503 + `Retry-After`).
3. Worker crash: kill the worker mid-job. The lease expires and the job resumes once, with no double posting.
4. Database backup and restore, **measured:** `pg_dump` / `pg_restore` per `docs/backup-restore.md`, timed. Then
   check that the restore replays nothing (ROLL-03).
5. Uncertain adjustment: execution result unknown. Reconciliation settles it.
6. Incorrect recommendation: arm C proposes a wrong amount. A supervisor rejects it, and it gets a register entry.
7. Emergency execution shutdown: the execution flag stops postings, and resuming is clean.

Then the stack-only SEC-21 exercises: compromised integration credential, where the mock API token is rotated and
the old one is **proven to fail**; leaked model key, as a test key rotation (no real key exists); and unauthorized
access. Then **one example incident report**, written from a drill that was actually run (ROLL-04).

## Order, size and cost
- **PR 1:** part A, documents only.
- **PR 2:** part B, items 1 and 3.
- **PR 3:** break-glass, if approved.
- **PR 4:** part C, after "machine free". It takes about 2-3 hours of stack time (an estimate).

Every PR merges on green. Cost: **$0** (mock AI, local only).

## Coordination
Milestone 13 (safe AI caching) is in progress in another session. This plan writes new files, and touches shared
files only at each PR's end: the requirements matrix, implementation status, the verification log's new Milestone
13b section, and the handoff. Each PR is merged with the latest `main` first.

## What would change this plan
- The owner prefers break-glass as a documented procedure only. Then part B item 2 drops, and ENT-26 is
  documentation only.
- A drill finds a real bug. It's then fixed in its own PR with a test before the drill is re-run, and recorded as
  found.
- The machine stays busy. Parts A and B finish, and part C waits. The milestone isn't called complete without the
  measured restore.
