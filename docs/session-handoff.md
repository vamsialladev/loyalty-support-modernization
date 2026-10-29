# Session handoff

**Updated:** 2026-10-28, end of Milestone 2.

## Where things stand
- Milestones 1 and 2 are done and committed on `main` (local only; no remote exists).
- **Pre-registration is committed:** `docs/legacy-defect-catalog.md` and `docs/hypotheses.md` at `1f8b8e6`,
  owner-approved, with the "A as-is" variant. Any change from now on goes in their change logs and is a new
  experiment (F9). No arm-B or arm-C code exists yet; keep it that way until Milestone 7 / 8.
- No product code yet beyond `app/preflight.py` and `app/env_leaks.py`. 108 offline tests pass.
- The owner's `.env` is still the unfilled template (fine until Milestone 4).

## Start the next session with
1. Read `CLAUDE.md`, `docs/MASTER-SPEC.md`, this file and `docs/implementation-status.md`.
2. Run the checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

3. **Before Milestone 3, say whether to use plan mode and wait for the owner.** Recommendation: **plan mode yes**
   (`docs/implementation-plan.md`): the generator, label rules and split design decide every later number.

## Milestone 3 scope (spec N.1 item 3; Appendices F2, H1; E.1)
- Reproducible generator (fixed seed, same seed → same checksum) for members, stays, channels, ledger (incl.
  pending, reversed and re-posted), policy versions, requests, notes, events, approvals, adjustments.
- Seed exactly the pre-registered defects D01–D25, controls K01–K06, safety S01–S05 at the catalog's frequencies
  (configurable). Fictional facts: catalog §1 (both properties `America/New_York`; policy v1/v2 on 2026-07-01).
- 12-month legacy history 2025-11-01 to 2026-10-31 with the modelled satisfaction proxy (labelled).
- Synthetic folios and receipt images (Appendix H1) with generator ground truth.
- 240 labelled cases: dev 100, validation 30, held-out 80, stress 30, grouped by member; checksums recorded.
- Fill `evaluations/label-review/review-sheet.csv` with the 30-case stratified sample (README sampling plan) and
  set its status to "Sheet ready"; ask the owner to review.
- Policies as Markdown with front matter (`policies/`), `docs/data-dictionary.md`, `evaluations/financial_model.py`,
  day-one discovery analysis (Pareto, cost of failures, rework loops, SLA/backlog), one-page problem statement,
  opportunity sizing.
- A test that the application package never reads `evaluations/label-review/` or generator metadata.

## Open items for the owner
- **Label review:** agreed 2026-10-28; the sheet is filled in Milestone 3. Record the result in
  `evaluations/label-review/README.md`, `docs/verification-log.md` and EVAL-04.
- Optional check: start Claude Code inside this folder and ask it to read `.env`; it should be refused (ACC-03).
- When ready (not urgent): approval to create the GitHub repo `vamsialladev/loyalty-support-modernization` and push.

## Blockers
None for Milestones 3–7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
