# Session handoff

**Updated:** 2026-10-29, end of Milestone 3.

## Where things stand
- Milestones 1–3 are done and committed on `main` (local only; no remote exists). 151 offline tests pass.
- **Pre-registration** (`1f8b8e6`) is untouched except three logged additions in the catalog's change log.
- **Data layer:** `python -m seed_data.generator generate` rebuilds `seed_data/v1/` (git-ignored) in about 5 s warm;
  `benchmarks/datasets/v1/` (cases, labels, manifest) is committed. Run `scripts\data.ps1 -Action generate` after a
  fresh clone before anything needs `seed_data/v1/`.
- **Waiting on the owner:** the 30-label review (`evaluations/label-review/review-sheet.csv`, instructions in the
  README there). When it comes back: record counts in the README status table, `docs/verification-log.md` and
  EVAL-04; fix any wrong label at its source (generator or policy), regenerate, log the change.
- The owner's `.env` is still the unfilled template; Milestone 4 needs local values (`POSTGRES_PASSWORD`,
  `MOCK_API_TOKEN`, `APP_SECRET_KEY`); preflight lists them.

## Start the next session with
1. Read `CLAUDE.md`, `docs/MASTER-SPEC.md`, this file and `docs/implementation-status.md`.
2. Run the checks and regenerate data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action generate
```

3. **Before Milestone 4, say whether to use plan mode and wait for the owner.** Recommendation: optional; plan mode
   is worth it for the contract and idempotency-record design, which Milestone 6 builds on.

## Milestone 4 scope (spec N.1 item 4; B.3, B.11, F.2)
- Mock customer API (separate service): member, stay, ledger, posting-queue lookups; ticket creation; adjustment
  submission with an idempotency key; status lookup; typed errors; pagination; deterministic failure injection
  (header + seeded scenarios); reset and seed; persisted atomically with its idempotency record.
- Versioned OpenAPI contracts and adapter interfaces; contract tests incl. malformed and schema-changed responses.
- Postgres 16 + Alembic; Docker Compose (non-root, profiles); `docker compose up`, migrate, seed from `seed_data/v1/`
  succeed from scratch (Appendix C, M3–4 part). "As of" queries so a case sees the world at its `received_at_utc`.
- Pay down TD-05 (move generator libraries to a `data` dependency group) before the first Dockerfile.
- Purpose lenses: swap-guide section for the mock API, onboarding section, role coverage (Backend / Platform).

## Open items for the owner
- Label review (above).
- Optional check: start Claude Code inside this folder and ask it to read `.env`; it should be refused (ACC-03).
- When ready: approval to create the GitHub repo `vamsialladev/loyalty-support-modernization` and push.
- Milestone 3 exercise: see the end of the milestone report.

## Blockers
None for Milestones 4–7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
