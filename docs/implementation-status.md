# Implementation status

**Last updated:** 2026-10-28 · **Current milestone:** 1 of 20 complete · **Next:** Milestone 2 (discovery package,
defect catalog and hypotheses), after the owner confirms the plan-mode choice.

## Completion scores (spec Part 0.5)
Counted from `docs/requirements-matrix.md` by `uv run python scripts/matrix_scores.py`. Only "Implemented and
verified" (or "Not applicable") counts as done.

| Score | Done (verified) | Total | % | In progress (unverified / configured / docs) |
|---|---|---|---|---|
| Core product functionality | 2 | 108 | 2% | 3 |
| Benchmarks and evaluation | 0 | 61 | 0% | 0 |
| Actual-tool exercises | 0 | 16 | 0% | 3 |
| Protocol labs | 0 | 16 | 0% | 0 |
| Security controls | 5 | 55 | 9% | 4 |
| Owner's demonstrated understanding | 0 | 3 | 0% | 1 |
| Other tracked work (not a Part 0.5 score) | 16 | 96 | 17% | 7 |

355 requirements: Tier 1: 188, Tier 2: 102, Tier 3: 26, Tier 4: 39.

The two "core" items done are the preflight command (PROF-04) and the one offline test command (TEST-06). No product
feature exists yet. The security items done are secret hygiene only (ACC-01, ACC-02, ACC-05, ACC-07, ACC-10).

## Milestones

| M | Status | Evidence |
|---|---|---|
| 1 | **Implemented and verified** (Appendix C: tracking files, requirements matrix with IDs, tool access matrix exist and are linked) | `tests/test_repo_guidance.py`, `tests/test_matrix_scores.py`; `docs/verification-log.md` Milestone 1 |
| 2–20 | Planned | `docs/implementation-plan.md` |

## Milestone 1 deliverables
- Continuity review of the live site and 13 public repos: `docs/continuity.md`
- Guidance: `CLAUDE.md` (with "Model and mode guidance"), `AGENTS.md`, `.cursor/rules/project-standard.mdc`
- Addendum saved: `docs/portfolio-presentation-addendum.md` (matrix rows PA-01 to PA-10, Tier 4)
- Tracking files: plan, status, requirements matrix (355 rows), feature checklist, verification log, decisions
  (ADR-0001 to ADR-0017), known limitations, session handoff
- Backlog with Stage 10 items; tool access matrix; accounts setup (first version); portfolio coverage map
- Secrets: `.gitignore`, `.claude/settings.json` deny rules, `python -m app.preflight`, `python -m app.env_leaks`
- Project config: `pyproject.toml`, `uv.lock`, `Makefile`, `scripts\test.ps1`, `scripts\preflight.ps1`, `LICENSE`,
  first `README.md`

## Work attribution
All Milestone 1 work was done by Claude Code (Opus 5.5) in this session. No other tool touched the repository.
