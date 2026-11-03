# Session handoff

**Updated:** 2026-11-03, after Milestone 5, ready to start Milestone 6.

## Where things stand
- Milestones 1–5 are done. `main` is on the **private** GitHub repository
  https://github.com/vamsialladev/loyalty-support-modernization (ADR-0053). **From here on, work on a branch and open a pull
  request**; CI runs on both (ADR-0013). Never push without the owner's OK. Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`; check
  `gh auth status` shows `vamsialladev` active).
- Legacy arm A runs end to end in the browser. Upgrading an existing volume works and is checked by the compose check
  (ADR-0052); `docs/onboarding.md` §4c has the commands.
- Latest results: `docs/verification-log.md`, section "After Milestone 5".

## Decisions waiting on the owner
1. **The evidence-free close (TD-17).** A case can be closed with a rule-based code and no evidence by writing any note.
   It is a gap, not a legacy defect. The proposed fix is in `docs/backlog.md`; it needs no catalog change. **Not applied.**
   If approved, do it first, on its own branch, before Milestone 6.
2. **Label review:** the 30-label sheet (`evaluations/label-review/`).

## Known and open
- **Case A-000010** (owner's local database) stays closed as `deny_claim_window`. There is no reopen until Milestone 6.
  To redo the work now, use "New case" with the same details (see `docs/onboarding.md` failure modes); no credit was made,
  so the duplicate check won't interfere.
- **The owner's "unhealthy" run has no proven cause** (ADR-0052). If it happens again, `stack.ps1 -Action up` prints it.
- **The owner's stack:** the last `up` predates these fixes. Run `-Action up` once to pick up the new `/readyz` and health
  settings; nothing else is needed.
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

## Blockers
None for Milestones 6–7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
