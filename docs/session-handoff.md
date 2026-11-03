# Session handoff

**Updated:** 2026-10-29, end of Milestone 5.

## Where things stand
- Milestones 1–5 are done and committed on `main` (local only; no remote exists). Milestone 5's checks are in
  `docs/verification-log.md` (Milestone 5 section): offline suite, Playwright end to end, compose check.
- Legacy arm A runs end to end in the browser (Appendix C, Milestone 5): sign-in, queue, four evidence screens,
  rules checklist, request, approval by a different supervisor, execution, reconciliation by key.
- Owner's plan decisions applied: D1 thin shared write path (ADR-0044), D1b duplicate check on adjustments only,
  D2 local demo sign-in with CSRF (ADR-0045), D3 tables from Milestone 5 (ADR-0046), D4 90-day ledger with "Show
  older" (ADR-0050), D5 Playwright for Python (ADR-0049), D6 demo cases from request files only (ADR-0048).
- One change from the plan: the demo-case loader is `benchmarks/intake.py` (`python -m benchmarks.intake`), not
  `app/demo_cases.py`. The existing guard `tests/test_generator.py::test_app_cannot_read_labels_or_generator_metadata`
  forbids app code from even naming the benchmark folders, so the loader moved instead of weakening the test.
- Waiting on the owner: the 30-label review.

## To use the console on your own stack
Your `.env` needs `DEMO_USER_PASSWORD` (new in Milestone 5) and the running stack needs the new app image:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action up
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action seed
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action demo-cases
```

Then open http://127.0.0.1:8010 (walkthrough: `docs/onboarding.md` §4c). Set `MOCK_API_SIM_CLOCK=true` in `.env`
first if you want each case's evidence as of its request date.

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

3. **Before Milestone 6, say whether to use plan mode and wait for the owner.** Recommendation: **yes** (CLAUDE.md:
   approvals, idempotency, reconciliation). Milestone 6 also writes its RFC in `docs/rfcs/`.

## Milestone 6 scope (spec N.1 item 6; Appendix C)
- Deterministic eligibility (ELIG-01) and policy retrieval by checkout date over Postgres full-text search (POL-*).
- The full state machine (reopening, every transition tested), approval binding hash with expiry and invalidation
  (WP-03, WP-06), revalidation before execution (WP-07: re-run the arm's own evaluator on fresh reads, the
  constraint from ADR-0044), row locks or versioned updates (WP-08), the reconciliation job (MOCK-09), the durable
  worker (JOB-*), the kill switch (WP-10), the append-only audit role (WP-11).
- Appendix C: real-Postgres tests for idempotency atomicity, concurrent execute, duplicate prevention,
  timeout-after-commit reconciliation, lease recovery, approval invalidation.
- Pays down TD-12 and TD-13. Arm A keeps calling the same `WritePath` and gains the safeguards without code changes.

## Open items for the owner
- Label review.
- When ready: approval to create the GitHub repo and push.
- Milestone 5 exercise: see the end of the milestone report.

## Blockers
None for Milestones 6–7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
