# 2026-11-28 An adjustment's result was lost after it posted (SEV3, **drill D5**)

*An example report from an executed drill (ROLL-04), written with `docs/incident-response.md`'s template. It's a
drill on a throwaway stack in GitHub Actions (run 46095480270), with synthetic data and mock AI. No real member, and
no real money.*

**Summary:** the customer's loyalty system applied a 14,840-point adjustment for DV-001 and then timed out (504), so
the app couldn't tell whether it had posted. The case went to "Execution unknown". Reconciliation looked the posting up
by its idempotency key and settled it as executed, with exactly one posting and no retry.

**Timeline (UTC, from the case's audit trail):**
- before 02:00:22: the adjustment was approved by a supervisor, and execution was requested;
- `execution_started`: the worker submitted the adjustment;
- 02:00:22.248: **`execution_unknown`**. The customer's system answered 504 after committing (the injected
  `commit_then_lost` fault);
- 02:00:22.258: **`reconciled_applied`**, 10 ms later. The status lookup by idempotency key found the adjustment;
- then `adjustment_executed`. The adjustment's status read `executed`.

**Impact:** one adjustment, 14,840 points, posted **exactly once**. That's checked by counting the ledger entries for
the stay in the customer's system: 0 before, 1 after. No member saw anything wrong. Time unresolved: about 10 ms in
"Execution unknown", and about 1.0 s from the request to settled.

**Cause:** the customer's gateway lost the response after the adjustment committed. In a real system that's a timeout
on the way back. The app can't know from a 504 whether the change happened.

**What held:**
- The worker recorded "Execution unknown" instead of "failed", and didn't submit again.
- Reconciliation asked the customer's system by the same idempotency key, which the lookup doesn't fault, and found
  the truth.
- The idempotency key would also have made a second submission harmless (drill D4 checks that across a restore).

**What didn't work, and was fixed:** the drill's first run (46094877745) reported a failure. It wasn't the app's
fault: the drill polled the case status every 0.5 s and missed a state that lasted 10 ms. The check now reads the
order of states from the audit trail, which is the record.

**Fix:** none needed in the app. Held by `scripts/drill.py d5` in `.github/workflows/drills.yml`.

**Follow-ups:** none for the app. For a real deployment: alert when a case stays in "Execution unknown" longer than
the reconciliation retry window (the `dead-jobs` and `queue-backlog` alerts cover it today only indirectly).
