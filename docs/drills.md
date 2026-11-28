# Operational drills (Milestone 13b; spec F.3, ROLL-02 and ROLL-03, SEC-21)

**Status: prepared, not run.** Each drill below has its setup, steps, measures and pass criteria written down. No
drill has run yet: they need the local Compose stack, and the owner said on 2026-11-27 not to run anything heavy until
the machine is free. Each **Result** reads "Not run" until the drill really runs. Then it holds the actual outcome:
times, counts and what failed, with the evidence file. Local drills aren't proof of production availability.

Plan and approval checklist: `docs/m13b-plan.md`. Mock AI and synthetic data only. Never against the live Cloud Run
demo or its Neon database. Cost: $0.

## Where each drill runs (owner's order, 2026-11-27: GitHub Actions wherever possible)
The drills run in `.github/workflows/drills.yml`: each on its own throwaway Compose stack on a GitHub runner, started
the way CI's Compose job starts it. The full output is kept as an artifact for 90 days: the drill's JSON, its console
output, and the stack's logs. **None needs the owner's laptop.** Each needs only Docker and the stack, and a runner
has both. Timings measured there are a GitHub runner's, not the laptop's, and each result says so.

| Drill | Where | Status |
|---|---|---|
| D7 emergency execution shutdown | GitHub Actions (`scripts/drill.py d7`) | Written; first run on its pull request |
| D3 worker crash, D5 uncertain adjustment, D2 customer API outage, D1 model outage, D6 incorrect recommendation, D4 backup and restore | GitHub Actions, one pull request each, in that order | Not run |
| SEC-21: integration credential, unauthorized access, leaked test key | GitHub Actions, on the stack | Not run |
| SEC-21: malicious policy, unexpected agent action, compromised dependency, excessive spend | GitHub Actions, as pytest in the existing CI | Not run |

The laptop steps below stay for anyone running a drill by hand.

## Before any drill
1. **The machine is free:** the owner says so, and `docker stats --no-stream` shows no other project's stack busy.
   Record the number of other running containers with each result. On 2026-11-26 a busy machine doubled timings
   (verification log M12 row 45).
2. **Start a throwaway stack:** `powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1 -Keep`.
   It builds the stack from an empty volume with its own env file and Compose project (`loyalty-check`), runs
   its checks, and keeps it running. The drills never touch the owner's `.env` or database volume. Its checks
   must pass before a drill starts.
3. **Save the full output** of every command to `observability/drills/<date>/<drill>.txt`, not just a summary (the
   owner's rule, 2026-11-26). Mask nothing by hand: the stack prints no secret, and a drill that would is stopped.
4. **Starting state:** the demo dataset, plus one case worked to Resolved / adjusted (DV-001, 14,840 points). It's
   the "completed action" that must never be replayed.

## Proposed recovery targets (not measured)
- **RTO: 1 hour** for the Compose stack. That's the time from "the database is lost" to serving again from the last
  backup.
- **RPO: 24 hours**, from a daily `pg_dump`.

These are proposals for this simulated engagement, stated apart from the measured restore in D4, and a real customer
sets their own. The live demo has no backup of its own: its data is reset every day, and Neon's own restore window
is the only copy (`docs/backup-restore.md`).

## The seven drills

### D1. Model provider outage
- **Setup:** arm C on the mock provider, with provider failures switched on (`ProviderUnavailable` from the mock
  model adapter; the circuit breaker in `app/adapters/circuit.py`).
- **Steps:** start 5 arm C investigations. Let the breaker open, then restore the provider and start 5 more.
- **Measure:**
  - how many runs stopped as "needs a person";
  - how long until the breaker opened, and until it closed after recovery;
  - spend recorded during the outage.
- **Pass:**
  - no proposal and no adjustment request is made from a failed run;
  - arms A and B keep working;
  - the breaker closes once the provider recovers;
  - no spend is counted for failed calls beyond what the cap rules say.
- **Result:** Not run.

### D2. Customer API outage
- **Setup:** the mock API's fault switch (`MOCK_API_FAULTS=true`, `X-Mock-Fault: unavailable`, then `timeout` and
  `partial`; ADR-0038).
- **Steps:** investigate 5 cases while the API is down, then bring it back.
- **Measure:**
  - 503 + `Retry-After` from our API (backpressure);
  - retries per job;
  - time to recover;
  - the `error-rate` and `queue-backlog` alerts firing and clearing.
- **Pass:**
  - no case shows evidence it didn't fetch;
  - jobs retry and complete after recovery, or go to dead jobs with a reason;
  - the runbooks the alerts link to match what happened.
- **Result:** Not run.

### D3. Worker crash
- **Setup:** one worker, then a second as the replacement.
- **Steps:** start an execution of an approved adjustment, kill the worker container mid-job (`docker kill`), and
  start the replacement.
- **Measure:**
  - the time until the lease runs out and the job is claimed again (`recovered: true`);
  - postings in the ledger for that adjustment.
- **Pass:**
  - **exactly one posting** (the idempotency key);
  - the job finishes once;
  - the case's timeline shows the recovery.
- **Result:** Not run.

### D4. Database backup and restore, measured (ROLL-03)
- **Steps:**
  1. Back up per `docs/backup-restore.md` (Local and Compose).
  2. Make the "after the backup" changes: resolve one more case, and revoke the demo agent's session.
  3. Drop and restore into `loyalty_restore`, re-apply the role grants, and point a copy of the app at it.
- **Measure:**
  - backup seconds and dump size;
  - restore seconds;
  - the time from "start restore" to `/readyz` ready, which is the measured RTO;
  - what was lost: the changes after the backup, which is the measured RPO.
- **Pass, the ROLL-03 rules:**
  - re-running reconciliation after the restore **doesn't post DV-001 again**, so its idempotency key still holds;
  - the case resolved after the backup is reported missing, not silently re-executed;
  - **access revoked after the backup stays revoked:** the session revoked in step 2 must not work against the
    restored database. If it does, the restore runbook must rotate `APP_SECRET_KEY` before reopening (that
    voids approvals not yet executed, by design; `docs/credential-rotation.md`), and the drill records it as
    found;
  - append-only audit holds after the grants are re-applied.
- **Result:** Not run.

### D5. Uncertain adjustment
- **Setup:** `X-Mock-Fault: commit_then_lost`. The adjustment commits, then the gateway times out.
- **Steps:** execute one approved adjustment.
- **Measure:** how long the case sits in "Execution unknown", and how long until reconciliation settles it.
- **Pass:**
  - the case goes to "Execution unknown", not "failed" and not a retry;
  - reconciliation finds the posting by status lookup and resolves it;
  - **one posting**.
- **Result:** Not run.

### D6. Incorrect recommendation
- **Setup:** arm C with a scripted mock model (`ScriptedModel`) that proposes a wrong amount for a case with a known
  label.
- **Steps:** an agent requests the adjustment, and a supervisor reviews it.
- **Measure:** whether the validation layer or the supervisor caught it, and what the case shows.
- **Pass:**
  - the wrong amount never posts;
  - the catch is recorded;
  - an entry goes in `docs/ai-incident-register.md`, marked "drill".
- **Result:** Not run.

### D7. Emergency execution shutdown
- **Setup:** two approved adjustments waiting.
- **Steps:**
  1. Turn execution off (`FEATURE_ADJUSTMENT_EXECUTION=false`), and turn AI off with the kill switch.
  2. Try to execute.
  3. Turn both back on.
- **Measure:** the time from the switch to the first refused execution, and any posting made while it was off.
- **Pass:**
  - **zero postings while off**;
  - a clear message in the console;
  - an audit event for each switch;
  - resuming posts each adjustment once.
- **Result:** Not run.

## SEC-21 incident exercises
Each starts as a tabletop. Those marked **executed** are run for real: in `pytest` with no stack, or on the stack.

| Exercise | How | Pass | Result |
|---|---|---|---|
| Leaked model key | Tabletop, plus a test-key rotation on the stack (no real key exists in this project) | Rotation steps work, and **the old key is proven to fail** | Not run |
| Compromised integration credential | Executed on the stack: rotate `MOCK_API_TOKEN` | The old token gets 401, the new one works, and the security event is logged | Not run |
| Unauthorized access | Executed on the stack: a revoked session, a wrong customer's case, and a forged CSRF token | All refused, each with a security event | Not run |
| Malicious policy | Executed in pytest: publishing a policy without the second approval, or with an injected instruction | Refused, or treated as data, never as an instruction | Not run |
| Unexpected agent action | Executed in pytest: a scripted model calls a tool outside its allowlist, or tries to execute | The call is refused, the run stops, the attempt is recorded | Not run |
| Compromised dependency | Executed: `pip-audit` on the lockfile, plus the steps to pin back a bad release | No known vulnerability, or the pin-back steps work | Not run |
| Excessive spend | Executed in pytest: runs past the stored daily cap | Blocked at the cap, and the cap survives a restart | Not run |

## After the drills
- **One example incident report,** written from a drill that actually ran (ROLL-04). It follows the template in
  `docs/incident-response.md`.
- **Every surprise is recorded as found.** A real bug gets its own PR with a test, then the drill runs again.
- **The milestone isn't complete without D4's measured restore** (`docs/m13b-plan.md`).
- **Estimated stack time** for the whole set: about 2-3 hours. That's an estimate, to be replaced by the measured time.
