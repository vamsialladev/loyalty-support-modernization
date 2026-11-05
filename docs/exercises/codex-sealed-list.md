# Claude Code's sealed list for the Codex exercise

> Written by Claude Code (Opus 5.5) on 2026-11-04, before any Codex run. **Don't open this until Codex has finished.** It
> isn't in the commit Codex reviews. Its SHA-256 is in `docs/verification-log.md`, so it can't be edited afterwards unnoticed.

These are the weaknesses the author already knows about, in the reviewed files. A Codex finding with the same cause counts as
"known". The author's list says what the author saw; it doesn't mean nothing else is there.

## Known and accepted (each stated in RFC-0001, an ADR or the tech debt register)

| # | Weakness | Sequence of events | Effect |
|---|---|---|---|
| K1 | A posting can land between the re-check and the submit | Step 1 reads the ledger; a batch posting commits; step 3 submits | An over-credit. Needs the platform to offer a conditional credit |
| K2 | "Absent" after the settle window can still be wrong on a platform with longer lag | Submit stalls past the window; 2 lookups find nothing; the case returns to `Approved`; the approval is then invalidated or expires; a new approval gets a new key; the old submit lands | Two credits under two keys, unless the ledger check sees the first. Same-key retries are safe |
| K3 | A platform that forgets idempotency keys after some time | A retry long after the first submission | A second credit. A question for each real vendor |
| K4 | The last switch check isn't atomic with the submit | The switch commits just after step 3's read | One submission per worker can land after the switch is off. Measured, not assumed |
| K5 | Changed evidence is only seen at approve and execute (D9) | Evidence changes while the approval sits | The page shows the approval as valid until someone acts. Nothing stale executes |
| K6 | `self._clock` is the app's clock; leases use the database's | Clock skew between app and database | Expiry and the settle window can be off by the skew. Leases aren't |
| K7 | HMAC holds only against someone without the secret | A person with database write access and `APP_SECRET_KEY` | A forged approval |
| K8 | Audit is append-only for the runtime role only | The owner role or a superuser edits `case_events` | History rewritten, unnoticed. There's no hash chain |

## Known and not fully tested

| # | Weakness | Sequence of events | Effect |
|---|---|---|---|
| K9 | `rejected_upstream` ends the job with the case `Approved`, with no automatic retry | A `401` from a rotated platform credential | A person must click Execute again. Deliberate, but each click uses up approval time |
| K10 | A case in `execution_conflict` can be reopened, but its stay stays blocked forever | A supervisor reopens it to fix the problem | Any new credit is refused by the index. Nothing in the app clears it; a person must correct the data |
| K11 | A dead `execute_adjustment` job leaves the case `Approved` with the button back | 5 attempts all failing on the re-check reads | Correct but quiet: only `job_dead` in the Configuration history says so. Alerts are Milestone 12 |
| K12 | The sweep looks up the requester by `started_by`, and falls back to user ID 0 | A stranded case whose attempt was started by a removed account | Reconciliation still runs. A later resubmission goes dead with `requester_inactive`, leaving `Approved` |
| K13 | `_submissions` counts attempts with outcome `unknown` only | Submits that came back `busy` or were `held` | Those aren't counted against the 3-per-approval bound. They're bounded by the job's own attempts instead |
| K14 | The settle check counts lookups by anyone, including a person's status check | A supervisor clicks "Check status" twice right after a timeout, with the settle window set low | The two-lookup rule is met sooner. The time window still holds |
| K15 | `request_execution` from `Execution unknown` uses the default job attempts, not the reconcile bound | A person clicks Execute on an unknown case | The job gets 5 attempts, not 12. It can go dead sooner, and the case stays visibly unknown |
| K16 | A worker with a lost lease can still finish its upstream call | A stall longer than the lease; the next worker recovers; both talk to the platform | Same key, so one credit; both try to record. The state check handles it, and only reconciliation's race is tested at this exact interleaving |

## Things the author believes are safe, and why

- Two approvals for one stay: the partial unique index, tested with the code's check switched off.
- A re-run of a finished job: state checks under the row lock make it a no-op.
- A deadlock between publish, approve and claim: each locks one case row, publish in case order, and the switch only ever
  after the case row.
- A held lock across a customer call: every call is preceded by a commit in `execute`, `_reconcile` and `decide`. This is
  checked by reading the code, not by a test.
