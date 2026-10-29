# Session handoff

**Updated:** 2026-10-29, end of Milestone 4.

## Where things stand
- Milestones 1–4 are done and committed on `main` (local only; no remote exists). 204 offline tests pass; the 6
  real-Postgres tests pass inside `scripts\compose_check.ps1`.
- The local stack works from scratch on a throwaway env file (compose check). **It has not been started on the
  owner's `.env`**, which still lacks `APP_DB_PASSWORD` and `MOCK_API_DB_PASSWORD`.
- Waiting on the owner: the 30-label review; running `scripts\update-local-env.ps1` (adds only the missing values).

## Start the next session with
1. Read `CLAUDE.md`, `docs/MASTER-SPEC.md`, this file and `docs/implementation-status.md`.
2. Run the checks (regenerate data first after a fresh clone):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action generate
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1
```

3. **Before Milestone 5, say whether to use plan mode and wait for the owner.** Recommendation: optional; worth it
   for the legacy arm's screen flow and what exactly makes it "legacy" without making it incompetent (spec B.8).

## Milestone 5 scope (spec N.1 item 5; B.8 arm A, B.13, E.2)
- Legacy arm A, runnable end to end in the browser: case queue, separate member and stay searches (exact match),
  ledger lookup (90-day view that groups re-posts later), keyword policy search over a frozen 2026-03-15 index,
  legacy rule configuration (Mountain Lodge still 30 days; v1 channel rules), manual notes and escalation,
  supervisor approval (status flag in the as-is variant; the shared write path for arm A), simulated adjustment
  through the `CustomerSystems` port.
- Server-rendered console start (Jinja2 + HTMX): login placeholder, banner (SYNTHETIC DATA · profile · AI mode ·
  customer), queue, case detail.
- Instrumentation for E.2 (outcome, steps, timings as scripted steps).
- App business tables begin here or in M6 (decide in the plan: the safe write path is M6).

## Open items for the owner
- Label review; `scripts\update-local-env.ps1`, then preflight READY, then `scripts\stack.ps1 -Action up` and
  `-Action seed` to run the stack on your own `.env`.
- When ready: approval to create the GitHub repo and push.
- Milestone 4 exercise: see the end of the milestone report.

## Blockers
None for Milestones 5–7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
