# Verification log

Every check run, with the command, date and result. Newest milestone first. Results are copied from real runs;
nothing here is predicted.

## Milestone 6 (started 2026-11-04)

All work by Claude Code (Opus 5.5). The owner approved the plan and its ten design choices (D1–D10) on 2026-11-04,
including pushing this milestone's branches, opening its pull requests and merging them when CI is green, and moving
API-01 and API-02 to Milestone 7. The owner asked for the real-Postgres tests and the compose check at each step.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | PR #2 merged before this milestone | `gh run list --commit 68deba1f…`; Actions run 41885597620 | Merge commit `68deba1` (branch `docs/handoff-m6`), CI on `main` **success** |
| 2 | This repo's git email | `git config --local user.email` | Already `339370878+vamsialladev@users.noreply.github.com`; not changed |
| 3 | Baseline before any change, offline | `scripts\test.ps1` on `68deba1` | Exit 0: ruff and mypy clean, **337 passed, 13 skipped**, coverage 94.69%, 5 min 56 s. 4 skips need a POSIX `sh`; the other 9 are the Postgres-only tests, which need a running stack |
| 4 | Baseline before any change, compose check with its real-Postgres tests (step 1: RFC) | `scripts\compose_check.ps1 -Browser` on `68deba1` plus the RFC files | **"compose check passed"**, exit 0: every step, Playwright 2 passed against the stack, upgrade path. The real-Postgres step printed no count, because pytest's `-q` was given twice; its exit code passed. The later steps print it |
| 5 | Step 1 merged | PR #3, Actions run 41941879891, `gh pr merge 3 --merge` | All 3 jobs green; merge commit `6cb58cb` |
| 6 | Eligibility engine, rule by rule | `uv run pytest tests/test_eligibility.py` | All passed: rounding, boundary days and time-zone edges, channels, profiles, both clocks, stale evidence, every refusal to decide. First run: 1 failed, **my test's arithmetic**: 200,001 cents is still 20,000 points, so it wasn't over the limit; the test now uses 200,010 |
| 7 | Engine against the independent labeler, dev split only | `uv run pytest tests/test_eligibility_differential.py` | No disagreement on any claimed stay or case verdict **on the first run**. A first-run match needed checking, so 5 tests now change one rule each and require a disagreement; all 5 did. Validation, held-out and stress splits not opened |
| 8 | Offline checks, step 2, first run | `scripts\test.ps1` | **1 failed, 399 passed:** `test_app_cannot_read_labels_or_generator_metadata` found the word `evaluations` in `app/domain/eligibility.py`'s docstring. The test is right; the docstring was reworded |
| 9 | Offline checks, step 2 | `scripts\test.ps1` | Exit 0: ruff, format and mypy clean, **400 passed, 13 skipped**, coverage 94.98%, 11 min 44 s |
| 10 | Compose check, step 2 (one at a time, after row 9) | `scripts\compose_check.ps1 -Browser` | **"compose check passed"**, exit 0: real-Postgres tests **9 passed**, Playwright 2 passed, upgrade path. No schema or stack change in this step. The script now prints the Postgres count |
| 11 | Step 2 merged | PR #4, Actions run 41945383411, `gh pr merge 4 --merge` | All 3 jobs green; merge commit `129bdf3` |
| 12 | Policies, offline | `uv run pytest tests/test_policies.py` | All passed: selection on the change-over days, exact excerpts, drafts never applying, every publish refusal, escaping, administrator and auditor limits |
| 13 | Offline checks, step 3 | `scripts\test.ps1` | **1 failed, 427 passed, 20 skipped**, coverage 95.07%, **35 min 6 s**. The failure: `test_seed_command_migrates_then_calls_the_mock` stubs the migration but not the new policy load, which read `DATABASE_URL`. The stub was added, and the seed test that uses a real database now also checks the policies load, once. `uv run pytest tests/test_app_shell.py`: 5 passed. The whole offline suite was not repeated locally; CI runs it on the pull request |
| 14 | Compose check, step 3, first run | `scripts\compose_check.ps1 -Browser` | **Failed, in the upgrade path only.** Real-Postgres 16 passed and Playwright 2 passed, then `mock-api` went unhealthy, so the app was never created and the 5 upgrade steps after it failed. `stack_diagnose` said it "is answering now but took longer". This code didn't change `mock-api` |
| 15 | Machine load during rows 13 and 14 | `Get-Counter`, `Win32_OperatingSystem`, `Get-Process` CPU deltas | CPU 99–100%; 1.1 to 3.6 GB of 32 GB free. Another project's `uvicorn` (PID 80480) at about 2 cores, a screen recorder at about 1.4. Not touched. **Cause of the failure, read from this evidence, not proven by a controlled test:** the health check starts Python inside a 3-second limit. Limit raised to 10 s (ADR-0052, updated) |
| 16 | Compose check, step 3, after the change | `scripts\compose_check.ps1 -Browser` | **"compose check passed"**, exit 0: real-Postgres **16 passed**, Playwright 2 passed, upgrade path from revision 0001 to `0003`, seed twice with 6 demo accounts, stopped app named as the cause. One pass under lighter load doesn't prove the longer limit was what fixed it |
| 17 | Step 3 merged | PR #5, Actions run 41955571193, `gh pr merge 5 --merge` | All 3 jobs green: **431 passed, 17 skipped** offline, **13 passed, 3 skipped** real-Postgres (the 3 need a stack container), no leaks, no known vulnerabilities; merge commit `514f0e7` |
| 18 | State machine and related files, step 4 | `uv run pytest tests/test_state_machine.py tests/test_stack_diagnose.py tests/test_preflight.py tests/test_compose.py tests/test_case_workflow.py` | **215 passed, 5 skipped**, 10 min 23 s under load. Every pair of 10 states against a table written by hand. The first run had 8 failures, all in test setup: the preflight fixtures lacked the new password (6), and my 2 new diagnose tests used a wrong module name |
| 19 | One existing assertion changed on purpose | `tests/test_case_workflow.py` | It asserted `Resolved -> Investigating` is refused, which encoded "no reopen yet". The spec now requires reopening; the assertion now checks `Resolved -> Approved` is refused, and `tests/test_state_machine.py` tests every pair |
| 20 | Compose check, step 4 | `scripts\compose_check.ps1 -Browser` | **"compose check passed"**, exit 0: real-Postgres **40 passed**, Playwright 2 passed. Rebuilt the old single-role state and ran `stack.ps1 -Action up`: `owner before: loyalty_app`, `owner after: loyalty_owner; loyalty_app can update case_events: f; can insert: t` |
| 21 | Audit role, as the real runtime role | `tests/test_audit_postgres.py` (inside row 20) | UPDATE, DELETE, TRUNCATE, ALTER and DROP on `case_events` and `system_events` all refused by Postgres; INSERT and SELECT work; the role can't create tables or change `alembic_version`. A test records the limit: the owner role can still edit |
| 22 | Close rules on real Postgres, for the first time | `tests/test_audit_postgres.py` (inside row 20) | Passed: all 5 rule-based codes refused with a long note and incomplete evidence; `deny_not_found` needs the latest logged search to have found nothing, read back from JSON in Postgres; close then reopen keeps the history. This closes the gap in row 7 of the previous section |
| 23 | Step 4 merged | PR #6, Actions run 41958700719, `gh pr merge 6 --merge` | All 3 jobs green: **558 passed, 41 skipped** offline, **36 passed, 4 skipped** real-Postgres; merge commit `672e140` |
| 24 | Approval binding, offline | `uv run pytest tests/test_approval_binding.py tests/test_case_workflow.py tests/test_console_web.py tests/test_scripted_agent.py` | **118 passed**, plus 2 for the arm A defects test. First run: 1 failed, **my test's assertion**: the page escapes the apostrophe in "can't", so it now looks for `can&#39;t` |
| 25 | Bug found while writing the race test | read `SharedWritePath.decide` | It re-read the evidence and then wrote with no lock, so a publish committing in between could be overwritten by "approved". Not yet seen failing; fixed before any test could catch it: it now locks the case and re-checks under the lock |
| 26 | Arm A's defects kept | `tests/test_approval_binding.py::test_the_recheck_does_not_quietly_fix_arm_as_defects` | On D06 and D07 dev cases arm A still approves and credits: the re-check uses its own view (ADR-0044). No scoring; held-out split not touched |
| 27 | Compose check, step 5 | `scripts\compose_check.ps1 -Browser` | **"compose check passed"**, exit 0: real-Postgres **44 passed**, Playwright 2 passed, upgrade path to `0005`. Includes publish invalidating in one transaction, a publish failing part way changing nothing, and publish racing approve |
| 28 | Secret scan on PR #7, CI run 41960676075 | gitleaks job; same command locally: `docker run ... gitleaks git /repo --redact` | **Failed: 1 finding,** `generic-api-key` at `tests/test_approval_binding.py:311`, commit `87f7d1e`. Read by hand: a fake value I wrote for the key-rotation test, not a real secret. The test now uses low-entropy values. Because merge commits keep that commit in history, `.gitleaksignore` lists that one exact fingerprint. No force-push; no other rule or path is ignored |
| 29 | Step 5 merged | PR #7, `gh pr merge 7 --merge` | All 3 jobs green after the row 28 fix; counts in the merged run |
| 30 | Job queue, offline | `uv run pytest tests/test_jobs.py tests/test_case_workflow.py tests/test_state_machine.py tests/test_console_web.py` | **200 passed.** First run: 2 failed. One was my test, where a lease had run out so the older job correctly came back first. **One was a real fault:** the SQLite driver's savepoints released as commits, so a rollback didn't undo a job. The engine now uses SQLAlchemy's documented recipe |
| 31 | Compose check, step 6 | `scripts\compose_check.ps1 -Browser` | **"compose check passed"**, exit 0: real-Postgres **51 passed**, Playwright 2 passed. `worker exit code after SIGTERM: 0`, from a real `docker compose stop`. A real process ended with `os._exit` mid-job was recovered by the next claim, with attempt 2 and `recovered` set. 8 workers claimed 50 jobs each exactly once |
| 32 | Secret scan before pushing, from here on | `docker run ... gitleaks git /repo --redact` | **no leaks found**, with the `.gitleaksignore` from row 28 |
| 34 | Step 6 merged | PR #8, Actions run 41963696996, `gh pr merge 8 --merge` | All 3 jobs green after row 33: **640 passed, 52 skipped** offline, **47 passed, 4 skipped** real-Postgres; merge commit `97fceec` |
| 35 | Execution, offline | `uv run pytest tests/test_execution.py tests/test_case_workflow.py tests/test_console_web.py tests/test_jobs.py tests/test_scripted_agent.py tests/test_arm_a_boundaries.py` | **136 passed.** Scripted agent still reaches a resting state on all dev cases. Two existing tests changed because requirements changed: `test_reconciled_as_not_applied...` now needs two lookups (RFC-0001, fault 4), and the console test now queues and drains a worker (D1). Neither assertion about credits was loosened |
| 36 | Compose check, step 7, first run | `scripts\compose_check.ps1 -Browser` | **Failed: real-Postgres 4 failed, 61 passed.** **Two real bugs, invisible on SQLite:** `record()` deadlocked 11 of 12 threads (an insert referencing a case holds a key-share lock, and `FOR UPDATE` conflicts with it; now `FOR NO KEY UPDATE`), and the one-credit index's refusal surfaced during a flush outside the `try`, in 2 tests (widened). The fourth was my test: it expected `Execution unknown` after a drain that had already run the second lookup |
| 37 | Compose check, step 7, after the fixes | `scripts\compose_check.ps1 -Browser` | **"compose check passed"**, exit 0: real-Postgres **65 passed**, Playwright 2 passed with the real worker service doing the execution, `worker exit code after SIGTERM: 0`, upgrade path to `0007` |
| 38 | Appendix C criteria, all inside row 37 | `tests/test_execution_postgres.py`, `tests/test_write_path_postgres.py`, `tests/test_worker_postgres.py`, `tests/test_mock_api_postgres.py` | **Idempotency atomicity:** a failure before the upstream commit writes nothing, and the same key then applies once. **Concurrent execute:** 10 threads, 1 credit. **Duplicate prevention:** 2 approvals for 1 stay, 1 credit, including with the code's check switched off. **Timeout-after-commit:** 1 credit, no resubmit. **Lease recovery:** a real process killed before and after submitting, 1 credit each. **Approval invalidation:** in one transaction, a failed publish changes nothing |
| 39 | Kill switch under concurrency, inside row 37 | `tests/test_execution_postgres.py` | Turning it off waits for a claim in progress, then new claims stop. While off: 10 requests refused, 10 reads worked. 6 jobs, 3 workers, thrown mid-run: late submissions were within the stated limit of one per worker, every held job used no attempts, and after turning back on each stay had exactly one credit |

## First push and the close fix (2026-11-04)

All work by Claude Code (Opus 5.5) on the owner's instructions. The owner unticked GitHub's email block for the first
push; commits up to `ca58fdc` keep the Gmail address, so every cited hash stays valid.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | First CI run, on a throwaway branch | `git push -u origin ci/first-run`; Actions run 41871746872 | Push accepted. **Green first time, on Linux:** lint, types, tests (318 passed, 10 skipped, coverage 95%, including the browser tests), real-Postgres mock API tests (6 passed), gitleaks (no leaks), pip-audit (no known vulnerabilities) |
| 2 | `main` on GitHub | `git push -u origin main:main`; `gh repo edit --default-branch main`; Actions run 41873750792 | `main` = `ca58fdc`, all 3 jobs green. Default branch `main`, visibility `PRIVATE`. `ci/first-run` deleted locally and on GitHub. This repo's `user.email` set to the noreply address |
| 3 | Close rules, per rule | `uv run pytest tests/test_case_workflow.py tests/test_console_web.py tests/test_scripted_agent.py` | All passed. New tests: every rule-based code refused with a long note and no evidence; refused with part of the evidence; a close that agrees with complete evidence needs no note; a rule-based code against complete evidence stays an override; `deny_not_found` with no search, after an empty search, when a later search found the record, on the missing record's screen, and with both records attached; `deny_other` under and at 20 characters; a forged POST with a valid CSRF token gets 409; a rejected search input doesn't count as a search |
| 4 | Scripted agent over the dev split, mechanics only | a temporary test printing how each run ended, deleted afterwards | 102 runs, **0 took the new "ask for the member number" path**, 16 `deny_not_found` (4 member, 12 stay), each after a logged empty search. No labels read for this count, nothing scored, held-out split not touched |
| 5 | Catalog and hypotheses unchanged | `git diff --stat -- docs/legacy-defect-catalog.md docs/hypotheses.md` | No difference, so no change-log entry (F9) |
| 6 | Full offline suite on the fix | `uv run pytest --cov` (PowerShell) | **337 passed, 13 skipped**, coverage 95% (94.69%), including the 2 browser tests; ruff and mypy clean. The skips are the real-Postgres and role tests plus the 4 `sh` tests, which need Git Bash |
| 7 | Not run for this fix | `scripts\compose_check.ps1` | Skipped: nothing in the stack changed. **So the new close rules have run on SQLite only.** The rules read `case_events.detail` as JSON through SQLAlchemy, with no Postgres-specific query |
| 8 | CI on the pull request's first head | PR #1, Actions run 41876636066, commit `85b6a16` | **No test result.** Postgres and secret-scan jobs passed; `playwright install --with-deps chromium` ran for 8 min 41 s, against a whole job of about 3 min on the other runs, until my next push cancelled it. Cause unknown; it has not recurred on the 2 runs since |
| 9 | CI on the pull request's final commit | PR #1, Actions run 41877881776, commit `f5c55cf` | **Green:** 340 passed, 10 skipped, coverage 95% (94.69%), real-Postgres mock API tests 6 passed, no leaks, no known vulnerabilities. Its log shows it ran at 17:29–17:32 UTC, while `gh run view` still said "queued" until after 17:38. I took that for a stuck queue and tried to cancel the old run twice; both were refused because it had already finished, and neither changed anything |
| 10 | Merge | `gh pr merge 1 --merge`, head pinned to `f5c55cf` | Merge commit `0a199a0`, so every cited hash stays valid. Branch deleted locally and on GitHub. Visibility `PRIVATE` |
| 11 | CI on the merged `main` | Actions run 41880671275, commit `0a199a0` | **Green:** all 3 jobs; 340 passed, 10 skipped, coverage 95% (94.69%), real-Postgres mock API tests 6 passed, no leaks, no known vulnerabilities |

**Case A-000010 stays as the audit record of the wrong denial** (ADR-0054). The fix applies to new closes only and no row
was changed. It lives in the owner's local database, so it isn't evidence anyone else can read; row 7 of the next section
records what it held.

## After Milestone 5: upgrade path, A-000010, private repository (2026-11-03)

**Reported by the owner:** on a volume from Milestone 4, `stack.ps1 -Action up` failed with `loyalty-app-1` unhealthy (logs
showed only `/healthz` 200) until `-Action seed` ran; `-Action seed` then failed with `409 already_seeded`; and case
A-000010 was closed as `deny_claim_window` with no evidence.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Reproduce on a real Milestone 4 stack | `git archive b238be7` into a scratch folder, its own compose project `loyalty-upg` and ports, `up`, `app.seed`; then this code's `stack.ps1 -Action up` and `-Action seed` on the same volume | App database at `0001` before; **seed failure reproduced** (`409 already_seeded`); **unhealthy not reproduced**: `up` passed, and the container's start command migrated to `0002` before any seed. So seed was not what fixed the owner's run |
| 2 | The owner's run, after the fact | `docker inspect` on `loyalty-app-1`, `docker events --since ... --until ...`, read-only | Healthy now; Docker no longer holds that run's health events (0 returned). **Cause unproven**; a slow cold start is a hypothesis only (ADR-0052) |
| 3 | Fault found by the reproduction | read `app/main.py`; new test | `/readyz` said the database was "ok" at any revision, including a Milestone 4 database. Now compared with this code's Alembic head; `tests/test_app_shell.py` checks `0001` is `not_migrated` |
| 4 | Fixes on the throwaway stack | `stack.ps1 -Action up`, `-Action seed` twice, stop the app, `stack_diagnose.py` | `stack: ready`; seed exit 0 both times with `mock data already loaded, skipped` and 4 demo accounts; the stopped app is named as the cause. Stack, volume and images removed; the owner's stack was not touched |
| 5 | New tests | `uv run pytest tests/test_stack_diagnose.py tests/test_app_shell.py tests/test_compose.py` | All passed. One existing assertion changed on purpose: `already_seeded` used to count as a refusal; the owner asked for success, so the refusal test now uses a 401 and a new test covers `already_seeded` |
| 6 | Compose check with the upgrade path | `scripts\compose_check.ps1 -Browser` | "compose check passed": real-Postgres tests, Playwright 2 passed, back to revision 0001 with mock data kept, `up` reports ready at `0002`, a running app on an old schema is reported "not migrated" and migrated, seed twice with 4 accounts, a stopped app named as the cause |
| 7 | A-000010, read-only | `psql` in `loyalty-db-1`: case, events, evidence, requests; mock database: stay | Evidence rows 0; event `case_closed` with `checklist_outcome: incomplete_evidence`, `override: true`. Stay ML-9701 checked out 2025-05-20, claim 2026-01-06: inside the 12-month window, so the denial was factually wrong. **Gap, not a legacy defect** (TD-17); nothing changed in the database |
| 8 | Dependencies audit | `uvx pip-audit -r <uv export> --no-deps --disable-pip` | No known vulnerabilities |
| 8a | Machine load during these runs | `Get-Process` CPU deltas, `Win32_OperatingSystem` | **722 MB of RAM free out of 32 GB**; a screen recorder at 2.3 cores, Teams, Zoom, and another project's server (`daypilot`, port 8011) at 0.6–0.9 of a core. Not touched. This made the full suite take 63 minutes (about 4 on a quiet machine) and supports, but does not prove, a slow start as the cause of the owner's "unhealthy" run |
| 8b | Browser fixture under that load | full suite, then `pytest tests/browser` | Setup error twice: "server exited early" (message lost to my own output filter) during a concurrent compose check, then "did not come up" within 60 s. Fixture hardened: 180 s wait, 5 s per request, server output kept in a log file and quoted in any failure. Then **2 passed** in 317 s |
| 8c | Full offline suite on the final code | `pytest --cov` (from Git Bash, so the 4 `sh` tests ran too) | **317 passed, 9 skipped** (the real-Postgres and role tests, which the compose check runs), coverage 95%; the only errors were the 2 browser setup errors from the old fixture (8b) |
| 9 | Secret scan before the first push | `docker run ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --redact` | 35 commits scanned, no leaks. `git log --all --name-only`: no `.env` file ever committed (only `.env.example`) |
| 10 | Create the private repository | `gh repo create vamsialladev/loyalty-support-modernization --private`; `gh repo view --json visibility` | `PRIVATE`. Second scan just before pushing: gitleaks no leaks; env-leak check 0 of 8 values |
| 11 | First push | `git push -u origin ci/first-run` | **Refused:** `push declined due to email privacy restrictions`. All commits carry the Gmail address; other repositories use the noreply address. History not rewritten; the owner decides (`docs/session-handoff.md`). **CI has not run** |

## Milestone 5 (2026-10-29)

All work by Claude Code (Opus 5.5) on the owner-approved plan (decisions D1–D6). No value from `.env` was read or
printed; tests and the compose check use generated throwaway values.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | State before work | `scripts\test.ps1` equivalent (ruff, format, mypy, `pytest -p no:cacheprovider`) | All clean; **211 passed, 13 skipped** (real-Postgres and Docker tests) |
| 2 | Dependencies | `uv add --group api jinja2~=3.1.6 python-multipart~=0.0.32 argon2-cffi~=25.1.0`; `uv add --group dev pytest-playwright~=0.10.0 playwright~=1.64.1` | Resolved and locked (`uv.lock`) |
| 3 | htmx vendored and verified | download `htmx.org-2.0.11.tgz` from the npm registry; compare SHA-512 with the registry's `dist.integrity` | Match; `dist/htmx.min.js` extracted unchanged, SHA-256 `d6fdc75f…f717` recorded in `app/web/static/vendor/README.md` and checked by a test |
| 4 | Chromium for Playwright | `uv run playwright install chromium` | Installed (exit 0) |
| 5 | Frozen keyword index | `uv run python scripts/build_legacy_index.py`, then `--check` | Built from Missing Points Requests v1 and Earning v2 (the policies in force on 2026-03-15), 11 sections; `--check` matches |
| 6 | First in-process smoke of the console | a scratch script driving the routes with TestClient | **Failed first:** every page answered 422 "missing query parameter s". Cause: the dependency aliases were defined inside a function while the module uses postponed annotations, so FastAPI couldn't resolve them. Fixed by moving them to module level. Then DV-001 went New → Resolved with adjustment `ADJ-…` and one 14,840-point `adjustment` entry in the mock ledger |
| 7 | Idempotency key design | review while writing the tests | **Bug found before any test ran:** a key built from the approval's row number repeats after an app database reset, and the mock platform would answer 409. Fixed: the key uses a random ID stored with the approval (ADR-0044) |
| 8 | Workflow and write path | `uv run pytest tests/test_case_workflow.py` | First run: 1 failed. The D20 test picked a case whose out-of-scope item is a noise complaint, which doesn't mention a refund, so the legacy rule correctly left it in the points queue. **The test was wrong, not the rule:** it now picks the refund variant (the routing keyword was not widened, which would tune arm A toward its predictions). Then **17 passed** |
| 9 | Screens on seeded data | `uv run pytest tests/test_legacy_screens.py` | 12 passed; the D18 test was hard-coded to one case, made generic over the three dev D18 cases: **14 passed** |
| 10 | Scripted agent | `uv run pytest tests/test_scripted_agent.py` | First run: 2 failed, both real. (a) The simulated supervisor rejected K01: the stored checklist lines were a tuple and the review expected a list; the checklist is now stored as plain JSON. (b) The English check (three common English words) took "Missing points. Beach Resort, December 16-17, 2025." for another language, an unregistered failure; it now looks for unmistakable Spanish, French, Portuguese or German words, checked on the dev split only (3 of 3 non-English found, 0 of 99 English flagged). The full-dev test passed during (a) because "Rejected" counts as a resting state, so it now also asserts that no adjustment is rejected. Then **8 passed**; all 102 dev contacts end in a resting state, no `system_error` event, no label file opened |
| 11 | Console over HTTP | `uv run pytest tests/test_console_web.py` | **16 passed** (sessions, CSRF, revocation, expiry, deactivation, the requester's forged approve refused, a form "role" ignored, banner and headers on every page, escaping, every visible control) |
| 12 | Boundaries | `uv run pytest tests/test_arm_a_boundaries.py` | **6 passed** (legacy layer pure, `app/` never imports `benchmarks/`, loader never opens labels, migration 0002 = models, htmx hash, no inline script or style) |
| 13 | Playwright, offline | `uv run pytest tests/browser` | **2 passed**: DV-001 through the four screens to 14,840 points, approved and executed by `supervisor.sam`, the ledger shows exactly that adjustment; htmx loaded under the CSP, an HTMX search request was observed, no console errors. The requester sees no Approve button and a forged POST with a valid CSRF token gets 403 |
| 14 | Full offline checks | `scripts\test.ps1` | **Failed first:** `tests/test_generator.py::test_app_cannot_read_labels_or_generator_metadata` (an existing guard) flagged `app/demo_cases.py`, which named the benchmark folder. The guard is right: the loader moved to `benchmarks/intake.py`; the test was not changed. Then exit 0: ruff and mypy clean, **299 passed, 13 skipped**, coverage 92% (gate 70%) |
| 15 | Matrix scores | `uv run python scripts/matrix_scores.py` | 369 requirements; core 25/108, benchmarks 14/64, security 5/55 verified |
| 16 | Compose check next to the owner's running stack | `scripts\compose_check.ps1 -Browser` | The owner's `loyalty` stack holds ports 5432/8020/8010 and another session may use it, so it was **not** stopped. The compose file now takes `DB_HOST_PORT`, `MOCK_API_HOST_PORT`, `APP_HOST_PORT` (defaults unchanged) and the check uses 15432/18020/18010 |
| 17 | Compose check, real Postgres and built images | same | Every step passed (up from an empty volume, migrate, seed incl. demo accounts, `/readyz` ready, live adapter checks, no labels in either image, 9 real-Postgres tests, app role refused by the mock database) **except the browser step, which failed intermittently**: 1 of 3 runs. With full output: the self-approval test clicked "Attach this view" while the HTMX swap to "Show older entries" was still in flight, so it attached the default 90-day view; the checklist correctly refused it (ADR-0050) and "Request adjustment" stayed disabled. **A test race, not an app bug.** Offline it passed 3 of 3 (faster swap) |
| 18 | Fix and re-check | wait for the swapped-in "all entries" view (as the first test already did) and for checklist outcome `adjust` before clicking; `scripts\compose_check.ps1 -Browser` twice | "compose check passed" both times; Playwright 2 passed each time, against real Postgres and the built images |
| 19 | Final offline checks (after the HTTP every-control test and the race fix) | `scripts\test.ps1` | Exit 0: ruff and mypy clean, **300 passed, 13 skipped**, coverage **94.5%** (gate 70%) |

## Milestone 4 follow-up: blank `${NAME}` expansion in the owner's `.env` (2026-10-29)

**Reported by the owner** after running `scripts\update-local-env.ps1` on their `.env`: (1) preflight called
`DATABASE_URL` and `MOCK_API_DATABASE_URL` "invalid format"; (2) `scripts\stack.ps1 -Action up` and `-Action seed`
warned `The "APP_DB_PASSWORD" variable is not set. Defaulting to a blank string.` (same for `MOCK_API_DB_PASSWORD`),
while preflight showed both as set. The stack started and seeding worked. No value was printed or read by hand at
any step; the owner's `.env` was handled only by the script and preflight.

**Root cause (one cause, both symptoms):** the script appended missing keys at the end of the file but rewrote the
URL lines in place, so the URLs used `${APP_DB_PASSWORD}` / `${MOCK_API_DB_PASSWORD}` above the lines defining
them. python-dotenv (preflight) and Docker Compose both expand `${NAME}` in a `.env` file top to bottom, so both
URLs got a blank password. The containers were not affected: `docker-compose.yml` builds their URLs from
`${APP_DB_PASSWORD:?}` itself and never uses the `.env` URL lines. The compose check missed it because it builds a
fresh file from the template, where the order is already right.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Reproduce on a fake pre-Milestone-4 file (fake values, scratchpad) | old `update-local-env.ps1`, then preflight and `docker compose config --quiet` | Both symptoms reproduced: URL lines at lines 24-25, the appended passwords at 97-98; preflight NOT READY (2 problems, both URLs "invalid format"); Compose printed both "variable is not set" warnings |
| 2 | Did the blank value reach the containers? | `docker compose config --format json` on the same file, lengths only | No: `db` got both role passwords (48 characters each); the `app` and `mock-api` URLs had 48-character passwords |
| 3 | Live roles on the owner's original stack, before any change (read-only) | `pytest tests/test_db_roles_postgres.py` with `TEST_DB_ROLES_CONTAINER=loyalty-db-1` | 3 passed: `loyalty_app` and `mock_api` each have a stored SCRAM-SHA-256 password, and both refuse a blank password over TCP. No role was created with a blank password |
| 4 | Fix | commit `6adbc3b` | Script moves each definition above the first line that uses it (repairs old files too); preflight names a `${NAME}` used above its definition or never defined; compose uses `${NAME:?}` for every secret; `01-roles.sh` refuses blank or short role passwords before `psql` runs; `stack.ps1` stops on Compose's unset-variable warning and gains `-Action verify-roles` |
| 5 | New tests catch the bug | the 9 new offline tests with the four fixed files stashed (old code) | All 9 failed on the old code; all pass on the fix (preflight per-role URL form x3, compose strictness x1, init script refusing blank or short passwords x3, script repair from two starting files x2) |
| 6 | Full offline suite | `scripts\test.ps1` | Exit 0: ruff and mypy clean; **215 passed, 9 skipped** (6 mock-API and 3 role tests need a running stack); coverage 94% |
| 7 | Guard on the owner's unrepaired `.env` | `scripts\stack.ps1 -Action status` | Refused: "Compose would use a blank value for: APP_DB_PASSWORD, MOCK_API_DB_PASSWORD" |
| 8 | Repair the owner's `.env` | fixed `update-local-env.ps1` | "moved above the lines that use them: APP_DB_PASSWORD, MOCK_API_DB_PASSWORD"; nothing added, generated or rewritten; backup `.env.bak` |
| 9 | Preflight after the repair | `python -m app.preflight --profile portfolio` | **READY**; both URLs and both role passwords `set` |
| 10 | Reset the owner's stack (owner approved deleting `loyalty_pgdata`) | `stack.ps1 -Action clean`, `up`, `seed` | Volume removed and recreated (21:09 UTC); `01-roles.sh` ran: `CREATE ROLE` x2, `CREATE DATABASE` x2; all three services healthy; seed: 3,286 members, 6,800 stays, 3,836 ledger entries, 12 queue items; app and mock `/readyz` both ready (each role logged in with its real password) |
| 11 | Roles after the reset | `stack.ps1 -Action verify-roles` | 3 passed (stored SCRAM password for both roles; blank password refused for both); `docker compose config` printed 0 unset-variable warnings; preflight READY |
| 12 | Appendix C again (changed init script and compose check) | owner stack `down` (volume kept), `scripts\compose_check.ps1`, owner stack `up` | **compose check passed**, every step including the real-Postgres step with the new role tests; owner stack back up with its seeded data |

## Milestone 4 (2026-10-29)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Owner's `.env` before starting anything (owner's request) | `python -m app.preflight --profile portfolio` | `POSTGRES_PASSWORD`, `MOCK_API_TOKEN`, `APP_SECRET_KEY` set; `APP_DB_PASSWORD`, `MOCK_API_DB_PASSWORD` missing (new in M4, ADR-0036). The stack was **not** started on the owner's `.env` |
| 2 | Base images exist and are pinned | `docker pull` | `postgres:16.15-alpine` (PostgreSQL 16.15), `python:3.12.10-slim-bookworm`, `ghcr.io/astral-sh/uv:0.13.5` |
| 3 | In-process smoke test | scratch script: migrate SQLite, seed, adapter calls | Seed loaded 3,286 / 6,800 / 3,836 / 12; replay returned the same `ADJ-` ID; commit-then-lost raised `UncertainOutcome`, then found by key; bad token gave a typed 401 |
| 4 | Contract tests, first run | `pytest tests/test_mock_api.py` | 1 failure: a test helper passed `timeout_fault_seconds` twice (test bug). Fixed; 41 passed |
| 5 | Label-isolation scan after adding the mock API | `pytest -k app_cannot` | The word scan flagged Alembic's `branch_labels` and a docstring. Changed to path-like references (`labels/`, `benchmarks`, `evaluations`, `ground_truth`, `label-review`); the mock may read `seed_data/v1`, the app may not |
| 6 | Lint and types | `ruff check`, `ruff format`, `mypy` (strict, 44 files) | Clean after configuring bugbear for FastAPI's `Depends`/`Query`/`Header` defaults |
| 7 | Compose check, first run | `scripts\compose_check.ps1` | Failed at step 1: PowerShell 5.1 turns Docker's stderr progress into errors under `Stop`. Scripts switched to exit-code checking |
| 8 | Compose check, second run | same | Everything passed except the image-contents step: PowerShell 5.1 stripped the inner double quotes of the `sh -c` script. Re-run by hand on the built images with a quote-free script: both pass (no `benchmarks`/`evaluations`/`seed_data`/`docs`/`tests`, no `.jsonl` on the image file system, UID 10001, `/srv` not writable) |
| 9 | **Compose check, third run (Appendix C, M3-4)** | same | **Passed**: from an empty volume, `up --build --wait` healthy; `app.seed` migrated the app and loaded 3,286 members, 6,800 stays, 3,836 ledger entries, 12 queue items; app `/readyz` ready; 6/6 live checks (member, stay, sim clock, idempotent replay, real network timeout, commit-then-lost found by key); both images clean; **6/6 real-Postgres tests** (atomicity, 20 concurrent same-key requests apply once, conflict, two keys both apply, full seed, commit-then-lost over HTTP); `loyalty_app` refused by `mock_customer_api`. Stack and volume removed |
| 10 | Full offline suite | `scripts\test.ps1` | Exit 0: ruff and mypy clean; **204 passed, 6 skipped** (the real-Postgres tests, which skip without `TEST_MOCK_API_DATABASE_URL` and passed in row 9); coverage 94% (gate 70%) |

## Milestone 3 (2026-10-28 to 2026-10-29)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Purpose docs committed before any M3 code | `git log` | `f0b3c34`; 124 tests passed at that commit |
| 2 | Libraries work on Windows (incl. time-zone data) | `python -c "import zoneinfo, PIL, reportlab, matplotlib, pydantic"` | `America/New_York` resolves (tzdata installed); Pillow 13.0, reportlab 5.1, pydantic 2.14.1 |
| 3 | First full generation | `python -m seed_data.generator generate --root <scratch>` | Failed: case DV-079 found no valid checkout date (wasteful sampling for post-July stays). Fixed by sampling inside the valid range |
| 4 | Second full generation | same | **The label cross-check failed on DV-078 (D16):** the labeler said escalate (24,809 points, above the 20,000-point supervisor limit in the policy); the builder intent said adjust. The labeler was right; the D16 builder now keeps multi-stay totals under the limit, and the limit rule has its own unit test |
| 5 | Third full generation | same | Failed on a reportlab font name (`Times-Roman-Bold` → `Times-Bold`). Fixed |
| 6 | Performance | `cProfile` at scale 0.2 | 54 s under the profiler on a cold machine; hot spots: `strptime` and PNG encoding. Switched to `fromisoformat` and `compress_level=1`. Warm full generation now about 5 s (first cold run about 70 s) |
| 7 | History volume matches assumption A1 | generation counts | First run 4,022 cases (seasonality multipliers averaged 1.033). Normalised to average 1: 3,872 (A1 × 12 = 3,840) |
| 8 | Lint and types | `ruff check`, `ruff format`, `mypy` (strict, 24 files) | 19 lint findings fixed (long lines, en dashes; S311 allowed for seeded generation; `RUF001` allowed on one Turkish name); 14 mypy errors fixed (covariant `Sequence`, misplaced ignores after formatting, reportlab has no stubs) |
| 9 | Full suite | `scripts\test.ps1` | Exit 0: **151 passed**, coverage **97%** (gate 70%), about 27 s including a full generation in a temp folder |
| 10 | Reproducibility | `scripts\data.ps1 -Action generate` twice | Manifest SHA-256 identical (`883095…6294`) |
| 11 | Clean removes regenerated data only | `scripts\data.ps1 -Action clean` | `seed_data/v1` removed; `benchmarks/datasets/v1/manifest.json` kept |
| 12 | Verify against the committed manifest | `scripts\data.ps1 -Action verify` | `verify: identical` |
| 13 | Split sizes and held-out composition | `tests/test_generator.py` | dev 100, validation 30, held-out 80, stress 30, fairness 40; held-out controls 20, every defect ≥ 2 (D24, D25 ≥ 3) |
| 14 | Documents match ground truth (one per type, opened) | viewed `ATT-DV-048-1.png`, `ATT-DV-004-1.pdf`, `ATT-DV-018-1.eml` | All fields match `labels/documents.jsonl` (confirmation, dates, member, totals); the receipt shows its planted crop, rotation and speckle |
| 15 | Day-one analysis | `python -m evaluations.discovery_analysis` | 3,872 cases, 1,057 failures (27%). **First version overstated the non-AI share (79%):** it counted D16 as partly fixable by B because it read the catalog's "Partial" cell, while catalog §11 says D16 is C-only. Now read from §11: **61% predicted fixable without AI, 21% AI-only, 9% split** (D18, D22). Committed reports equal a regeneration from the data (test) |
| 16 | Label-review sheet | open `review-sheet.csv` | 30 rows, template columns, strata 6/6/2/5/6/5, held-out rows within 10–20 (test) |

## Milestone 2 (2026-10-28)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Property time zones in existing stages | `grep` over the cloned repos | Mountain Lodge's shuttle serves Asheville (AVL) in stage 1; Beach Resort is near Miami; stage 6 uses `America/New_York`. Both properties are Eastern time, so D04 became "UTC read as local" |
| 2 | Drafts shown to the owner before commit | — | Owner asked for a summary by intervention class and a restatement of choice 1, then approved with one change (A as-is variant) |
| 3 | Pre-registration content pinned | `uv run pytest tests/test_preregistration.py` | 7 passed |
| 4 | Pre-registration commit | `git commit` of catalog, hypotheses, decisions, matrix rows, test | `1f8b8e6`; no arm-B or arm-C code exists in the repository at this commit |
| 5 | Discovery docs test, first run | `uv run pytest` | 2 failed. `docs/legacy-discovery.md` named the category "known functionality" only in lower case (heading fixed). `docs/kpi-tree.md` had the phrase but wrapped over two lines: **a measurement problem**, fixed by matching with line breaks ignored |
| 6 | Full suite | `uv run pytest -q` | 108 passed |
| 7 | Completion scores | `uv run python scripts/matrix_scores.py` | 356 requirements; scores in `docs/implementation-status.md` |
| 8 | Full offline checks on Windows | `powershell -ExecutionPolicy Bypass -File scripts\test.ps1` | Exit 0: ruff clean, mypy clean, **108 passed**, coverage 97% (gate 70%) |
| 9 | Mermaid diagrams render | — | **Not checked**: no renderer installed; code fences checked closed by a test. To check on GitHub once the repo exists (registers PR-09) |

## Milestone 1 (2026-10-28)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Repo state before work | `git status`, `git log --oneline` | Branch `master`, 3 commits, `docs/MASTER-SPEC.md` committed with no uncommitted changes; only `.env` untracked |
| 2 | `.env` contents without opening it | `cmp -s .env .env.example` | Identical: every value in `.env` is still empty |
| 3 | `.env.example` holds no secrets | read the committed template | Comments and non-secret defaults only |
| 4 | `.env` ignored after adding `.gitignore` | `git check-ignore -v .env` | `.gitignore:2:.env` |
| 5 | Branch rename | `git branch -m master main` | On `main` (ADR-0013) |
| 6 | Local tools | `<tool> --version` for git, gh, python, uv, docker, node, npm, ruff; `command -v` for the rest | See `docs/tool-access-matrix.md` §3: gitleaks, terraform, make, trivy, syft, aws, supabase, psql, pwsh, codex missing |
| 7 | GitHub CLI | `gh auth status` | Signed in as `vamsialladev` (active) and a second account; no remote on this repo (`git remote -v` empty) |
| 8 | Docker daemon | `docker info --format '{{.ServerVersion}} {{.OperatingSystem}}'` | 27.0.3, Docker Desktop, running |
| 9 | Public repos listed | `gh repo list vamsialladev --limit 50` | 14 public repos plus 1 private (`python-fluency-drills`, not reviewed, never listed publicly) |
| 10 | Public repos cloned read-only | `git clone --depth 1` × 13 into the session scratchpad | All 13 cloned; commits recorded in `docs/continuity.md` §1 |
| 11 | Live site matches the website repo | `curl "https://vamsialla.com/<page>?cb=<epoch>"` then `diff` against `main` for `data/projects.json`, `projects.html`, `index.html`, two case studies | All 200 and **identical** |
| 12 | Dependencies and lockfile | `uv add python-dotenv`, `uv add --dev pytest pytest-cov ruff mypy`, `uv lock`, `uv sync` | Resolved 17 packages; python-dotenv 1.2.4, pytest 9.2, pytest-cov 7.1, ruff 0.17.3, mypy 2.4.1 |
| 13 | First test run | `uv run pytest` | Collection error: `app` not importable. Fixed with `pythonpath = ["."]` in `pyproject.toml` |
| 14 | Second test run | `uv run pytest` | 7 failed, 61 passed. Six were tracking files not yet written. **One was a wrong measurement:** `test_env_example_has_no_secret_values` flagged `DATABASE_URL`, whose template value only references `${POSTGRES_PASSWORD}`. Fixed by reading the template without interpolation and allowing only a `${VAR}` reference as a URL password; added a test that the check still catches a literal key and a literal URL password |
| 15 | Lint and types | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | First run: 16 lint findings (long lines, an en dash, tuple concatenation) and 1 mypy error (`leaks` annotation). Fixed; then all clean (mypy strict: 4 source files, no issues) |
| 16 | Preflight on the owner's real `.env` | `uv run python -m app.preflight --profile portfolio` | NOT READY, 5 problems: `APP_SECRET_KEY`, `POSTGRES_PASSWORD`, `MOCK_API_TOKEN` missing; `DATABASE_URL`, `MOCK_API_DATABASE_URL` invalid (empty password). No value printed. Correct for an empty template |
| 17 | Leak check on the owner's real `.env` | `uv run python -m app.env_leaks` | "Checked 0 secret value(s) from .env against tracked files: 0 leak(s)." (no secrets set yet, so this run proves only that the check runs; the planted-value tests prove it detects) |
| 18 | Completion scores | `uv run python scripts/matrix_scores.py` | 355 requirements (Tier 1: 188, Tier 2: 102, Tier 3: 26, Tier 4: 39); scores in `docs/implementation-status.md` |
| 19 | Full offline checks on Windows | `powershell -ExecutionPolicy Bypass -File scripts\test.ps1` | Exit 0. ruff clean, 26 files formatted, mypy no issues, **71 passed**, coverage **97%** (`app/preflight.py` 98%, `app/env_leaks.py` 92%), gate 70% |
| 20 | PowerShell preflight wrapper | `powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1 -Profile live-model` | Exit 1, NOT READY: the core variables above plus "live-model needs AI_PROVIDER set to a real provider, not mock" and "live-model needs FEATURE_LIVE_AI=true". No value printed |
| 21 | `make` targets | — | Not run: `make` is not installed on this machine. The `scripts\*.ps1` equivalents were run instead |
