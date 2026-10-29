# Experiment plan

> Simulated client engagement, synthetic data. Requirement LEG-01. The binding parts (definitions, thresholds,
> decision rules) are pre-registered in `docs/hypotheses.md` and `docs/legacy-defect-catalog.md` (commit 1f8b8e6).
> This file describes how the experiment is run; it must not contradict them.

## 1. Arms and variant
| Name | What runs | Write path | In hypotheses |
|---|---|---|---|
| A | Scripted legacy agent on arm-A code | Shared safe path | H1, H6 |
| A as-is | Same agent | Legacy path (no binding, no re-check, fresh key per attempt) | Descriptive only (§3a); excluded from H6 |
| B | Improved conventional workflow, deterministic | Shared safe path | H1–H4, H6 |
| C | B plus the bounded AI layer | Shared safe path | H2–H6 |

## 2. Data
240 labelled cases (dev 100, validation 30, held-out 80, stress 30), grouped by member, held-out written last and
covering both sides of the 2026-07-01 policy change (`docs/legacy-defect-catalog.md` §10). Labels come from generator
facts and the written policy; about 30 are reviewed by the owner (`evaluations/label-review/`).

## 3. Fairness rules (spec B.8, F9)
- Same cases, same mock API state, same seeds for every arm; cache state declared.
- The same defects are present for every arm. Arm B gets a fair fix for every non-AI-addressable defect.
- No arm sees labels, generator metadata or the held-out split during development.
- Interface and integration gains are credited to B, not C. Write-path gains are credited to the platform (A vs A as-is).
- Every slice where A or B beats C is reported.

## 4. Runs
- A, A as-is, B: one run per split plus one repeat to confirm determinism.
- C: 3 live runs on held-out with Claude Haiku 5.5 and a budget cap (first run suggested at $5); mock runs only for
  development and CI, never for hypotheses. 10 selected cases repeated 3× more to show variability.
- Every run stores dataset version and checksum, prompt version, model ID, policy version, application version,
  configuration, timings, tokens and cost.

## 5. Ablations (one factor at a time, spec E.4; after the main comparison)
Prompt version; context selection; retrieval (FTS vs a hybrid variant, only as a separate experiment); loop limits;
structured validation on/off; bounded repair on/off; rules-only vs retrieval + structured generation vs bounded agent.
Each is a new, labelled experiment; none changes the pre-registered verdicts.

## 6. Analysis
Paired bootstrap 95% intervals (10,000 resamples, seed 9), counts and denominators, per-scenario and per-defect
breakdowns, the failure funnel along the F7 proof chain, results re-weighted to the history's frequencies, and the
predicted-vs-actual table per defect (F8). Error analysis in `docs/error-analysis.md` (Milestone 10).

## 7. Budget and stop rules
- Live spend stops at the configured cap; an interrupted live run is reported as interrupted, never extrapolated.
- If H6 fails anywhere, analysis stops until the write path is fixed and every run is repeated.
