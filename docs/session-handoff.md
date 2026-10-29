# Session handoff

**Updated:** 2026-10-28, end of Milestone 1.

## Where things stand
- Milestone 1 is done and committed on `main` (local only; no remote exists).
- No product code yet beyond `app/preflight.py` and `app/env_leaks.py`.
- The owner's `.env` is an unfilled copy of `.env.example`; that is fine until Milestone 4 (local values) and
  Milestone 8 (Claude API key).

## Start the next session with
1. Read `CLAUDE.md`, `docs/MASTER-SPEC.md`, this file and `docs/implementation-status.md`.
2. Run the checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

3. **Before Milestone 2, say whether to use plan mode and wait for the owner** (`CLAUDE.md`, "Model and mode
   guidance"). Recommendation for Milestone 2: plan mode not needed (documents), but the defect catalog and
   hypotheses are pre-registration, so the owner may prefer to review an outline first.

## Milestone 2 scope (spec N.1 item 2, Appendix F placement, ADR-0016)
- Discovery package (A.2): customer-discovery, business-requirements, product-requirements, workflow,
  architecture, legacy-discovery; stage 0 loyalty addendum (REUSE-01) reusing the four-check test.
- Baseline measurement plan (E.2), threat model draft (`security/threat-model.md`, C.2).
- **Pre-registered:** `docs/legacy-defect-catalog.md` (F3), `docs/kpi-tree.md` (F4), `docs/hypotheses.md` (F5),
  committed before any arm-B or arm-C code.
- Loyalty facts to reuse are in `docs/continuity.md` §4 (Guest Rewards: Silver 5+ / Gold 15+ / Platinum 40+
  nights, 10 points per US dollar on the room rate, taxes and fees excluded; member numbers `GR-#####`).

## Open items for the owner
- **Pending approval:** `docs/legacy-defect-catalog.md` and `docs/hypotheses.md` are uncommitted drafts. Commit them
  (the pre-registration) only after the owner approves, before any arm-B or arm-C code.
- **Label review:** the owner agreed (2026-10-28) to review ~30 labels. Instructions and sheet format are in
  `evaluations/label-review/`; Milestone 3 fills `review-sheet.csv`; record the result in its README status table,
  `docs/verification-log.md` and EVAL-04.
- Optional check: start Claude Code inside this folder and ask it to read `.env`; it should be refused (ACC-03).
- When ready (not urgent): approval to create the GitHub repo `vamsialladev/loyalty-support-modernization` and push.
- Milestone 1 exercise (Part K.1): see the end of the milestone report.

## Blockers
None for Milestones 2–7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
