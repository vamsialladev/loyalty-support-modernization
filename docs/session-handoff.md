# Session handoff

**Updated:** 2026-11-04, after Milestone 5 and the close fix, ready to start Milestone 6.

## Where things stand
- Milestones 1–5 and the close fix (ADR-0054) are on `main` in the **private** GitHub repository. CI was green on merge
  commit `0a199a0`: 340 passed, 10 skipped, coverage 95%, real-Postgres mock API tests 6 passed, no leaks, no known
  vulnerabilities (run 41880671275). https://github.com/vamsialladev/loyalty-support-modernization (ADR-0053).
- **Work on a branch and open a pull request**; CI runs on both (ADR-0013). Merge with a merge commit, not squash or
  rebase, so cited hashes stay valid. Never push without the owner's OK. Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`; check
  `gh auth status` shows `vamsialladev` active).
- This repo's `user.email` is the noreply address, so the account's email block won't refuse new commits. Earlier commits
  keep the Gmail address, as the owner chose, so every cited hash stays valid.
- Legacy arm A runs end to end in the browser. Upgrading an existing volume works and is checked by the compose check
  (ADR-0052); `docs/onboarding.md` §4c has the commands.
- Latest results: `docs/verification-log.md`, section "First push and the close fix".

## Waiting on the owner
1. **Label review:** the 30-label sheet (`evaluations/label-review/`).
2. **Email block:** tick "Block command line pushes that expose my email" again at https://github.com/settings/emails, if
   not already done. New commits use the noreply address, so it won't block them.
3. **Milestone 6 plan mode:** confirm before it starts (see below).

## Known and open
- **The new close rules have run on SQLite only** (verification log, row 7). Milestone 6's real-Postgres test file is the
  natural place to add one close-rule test.
- **Slow CI browser install:** one run's `playwright install --with-deps chromium` ran for 8 min 41 s before a newer push
  cancelled it; cause unknown, not seen on the 2 runs since. The job's 30-minute limit is the only guard. Also, `gh run
  view` can lag: it showed "queued" for a run whose log shows it had finished. Check the log before treating a run as
  stuck.
- **Case A-000010** (owner's local database) stays closed as `deny_claim_window`, as the audit record of the wrong denial
  (ADR-0054); the close fix applies to new closes only. There is no reopen until Milestone 6. To redo the work now, use
  "New case" with the same details (see `docs/onboarding.md` failure modes); no credit was made, so the duplicate check
  won't interfere. The owner's stack needs `-Action up` first to pick up the fix.
- **The owner's "unhealthy" run has no proven cause** (ADR-0052). If it happens again, `stack.ps1 -Action up` prints it.
- **The owner's stack:** the last `up` predates these fixes. Run `-Action up` once to pick up the new `/readyz`, the health
  settings and the close fix; nothing else is needed.
- **Making the repository public** stays the owner's decision. When approved: `gh repo edit
  vamsialladev/loyalty-support-modernization --visibility public --accept-visibility-change-consequences`, then turn on
  secret scanning and push protection (free on public repositories) under Settings → Advanced Security.

## Start the next session with
1. Read `CLAUDE.md`, `docs/MASTER-SPEC.md`, this file and `docs/implementation-status.md`.
2. Run the checks (regenerate data first after a fresh clone; install Chromium once):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action generate
```

```powershell
uv run playwright install chromium
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1 -Browser
```

Don't run the last two at the same time. Close heavy apps first if you can: with a recorder, a video call and little
free memory, the suite took 63 minutes instead of about 4 (verification log).

3. **Before Milestone 6, say whether to use plan mode and wait for the owner.** Recommendation: **yes** (`CLAUDE.md`:
   approvals, idempotency, reconciliation). Milestone 6 also writes its RFC in `docs/rfcs/`.

## Milestone 6 scope (spec N.1 item 6; Appendix C)
- Deterministic eligibility (ELIG-01) and policy retrieval by checkout date over Postgres full-text search (POL-*).
- The full state machine (**reopening**, every transition tested), approval binding hash with expiry and invalidation
  (WP-03, WP-06), revalidation before execution (WP-07: re-run the arm's own evaluator on fresh reads, the
  constraint from ADR-0044), row locks or versioned updates (WP-08), the reconciliation job (MOCK-09), the durable
  worker (JOB-*), the kill switch (WP-10), the append-only audit role (WP-11).
- Appendix C: real-Postgres tests for idempotency atomicity, concurrent execute, duplicate prevention,
  timeout-after-commit reconciliation, lease recovery, approval invalidation. The CI `postgres` job only runs
  `tests/test_mock_api_postgres.py` today; add the new file to it.
- Pays down TD-12 and TD-13. Arm A keeps calling the same `WritePath` and gains the safeguards without code changes.
- Reopening must keep the audit trail: A-000010's `case_closed` event stays as the record of the wrong denial, and a
  reopened case's next close goes through the ADR-0054 rules in `cases.close_case`.
- Check first: `case_events` is the audit log the append-only role will protect, and the close rules read it
  (`cases.latest_search_found_nothing`), so the app role still needs to read it.

## Blockers
None for Milestones 6–7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
