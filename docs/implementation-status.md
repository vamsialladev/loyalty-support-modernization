# Implementation status

**Last updated:** 2026-10-28 · **Current milestone:** 2 of 20 complete · **Next:** Milestone 3 (synthetic data
generator, legacy history, supporting documents, labels and splits), after the owner confirms the plan-mode choice.

## Completion scores (spec Part 0.5)
Counted from `docs/requirements-matrix.md` by `uv run python scripts/matrix_scores.py`. Only "Implemented and
verified" (or "Not applicable") counts as done.

| Score | Done (verified) | Total | % | In progress (unverified / configured / docs) |
|---|---|---|---|---|
| Core product functionality | 2 | 108 | 2% | 3 |
| Benchmarks and evaluation | 4 | 62 | 6% | 0 |
| Actual-tool exercises | 0 | 16 | 0% | 3 |
| Protocol labs | 0 | 16 | 0% | 0 |
| Security controls | 5 | 55 | 9% | 5 |
| Owner's demonstrated understanding | 0 | 3 | 0% | 1 |
| Other tracked work (not a Part 0.5 score) | 34 | 96 | 35% | 7 |

356 requirements: Tier 1: 189, Tier 2: 102, Tier 3: 26, Tier 4: 39.

Still no product feature. The four benchmark items done are the pre-registration (LGF-01), the defect catalog
(LGF-03), the hypotheses (LGF-06) and the KPI tree (LGF-04): documents, not results.

## Milestones

| M | Status | Evidence |
|---|---|---|
| 1 | Implemented and verified | `tests/test_repo_guidance.py`, `tests/test_matrix_scores.py`; verification log, Milestone 1 |
| 2 | **Implemented and verified** (Appendix C: discovery and architecture docs exist and are linked; catalog and hypotheses committed before any arm code) | `tests/test_discovery_docs.py`, `tests/test_preregistration.py`; pre-registration commit `1f8b8e6`; verification log, Milestone 2 |
| 3–20 | Planned | `docs/implementation-plan.md` |

## Milestone 2 deliverables
- **Pre-registered (commit `1f8b8e6`, owner-approved 2026-10-28):** `docs/legacy-defect-catalog.md` (25 defects,
  6 controls, 5 safety scenarios, the "A as-is" variant), `docs/hypotheses.md` (H1–H7 plus the A as-is comparison).
- Discovery: customer discovery (FICTIONAL sessions), stage 0 loyalty addendum, business and product requirements,
  workflow, legacy discovery (with source register and data quality assessment), KPI tree.
- Design and plans: architecture, baseline measurement plan, experiment plan, threat model draft
  (`security/threat-model.md`), governance and RACI, registers, ADR-0018 to ADR-0027 and the decision guide.
- Label review package: `evaluations/label-review/` (owner agreed to review about 30 labels).

## Work attribution
All Milestone 1–2 work was done by Claude Code (Opus 5.5). The owner approved the catalog and hypotheses and chose
the A as-is variant. No other tool touched the repository.
