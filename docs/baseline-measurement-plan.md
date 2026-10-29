# Baseline measurement plan (spec E.2)

> Simulated client engagement, synthetic data. Requirement LEG-01 (with `docs/experiment-plan.md`). How the legacy
> workflow (arm A) and its as-is variant are measured, before any improvement is built.

## 1. Two baselines, kept apart
1. **Synthetic operating history (F2, Milestone 3):** 12 months of generated legacy operations, 2025-11-01 to
   2026-10-31. It shows what the legacy process *would* produce under the catalog's assumptions: outcomes, contacts,
   reopen loops, SLA and backlog. It is generated, so it proves the analysis method, not real performance.
2. **Measured legacy arm (Milestone 5 build, Milestone 10 runs):** the scripted legacy agent runs real cases through
   the real arm-A code against the mock customer API. This is what the benchmark compares.

## 2. What arm A is instrumented to capture (per case)

| Metric | How it is captured | Automated or human |
|---|---|---|
| Correct outcome and eligibility | Compared with the label at the settlement horizon | Automated |
| Incorrect approval / incorrect denial | Final ledger vs labelled ledger | Automated |
| Appropriate escalation | Escalation vs label | Automated |
| Missing-information detection | Information requests vs label | Automated |
| Time to find evidence | Scripted steps until every required evidence item is on screen | Automated, **scripted steps, not human time** |
| Time to complete | Scripted steps until resolution | Automated, scripted steps |
| Manual steps | Count of screen visits, searches and typed fields | Automated, scripted |
| Reopened cases | Member journey reopens | Automated, simulated |
| Duplicate adjustments | Write-path log (arm A: expected 0; A as-is: measured) | Automated |
| Overrides | Supervisor rejections of a proposal | Automated, simulated supervisor |
| System errors | Typed errors from the mock API and the app | Automated |

Human usability measurements (handling time, satisfaction) are separate and only come from real participants using
`docs/timing-protocol.md` (Milestone 10). If nobody takes part, they are reported as **unmeasured**.

## 3. Procedure
1. Generate data and labels with a fixed seed; record the dataset version and checksum.
2. Run arm A once per split; repeat once to confirm identical output (it is deterministic).
3. Run the A as-is variant on the same cases, plus the fault-injection pass (`docs/hypotheses.md` §3a).
4. Store every result with dataset, policy, application version and run ID in `benchmarks/results/`.
5. Produce the baseline report: counts, denominators, per-scenario and per-defect breakdowns, the failure funnel.

## 4. Root-cause analysis (Milestone 10, `docs/root-cause-analysis.md`)
Each failing legacy case gets one of the spec's categories (missing or incorrect source data, delayed upstream,
integration failure, incorrect rules, outdated policy configuration, poor search, ambiguous language, fragmented UI,
excessive manual work, training or process issue, unknown) with reproduction, expected vs actual, evidence,
frequency, business consequence and the recommended intervention. The catalog's "intervention class" is the
prediction; the RCA is the measurement. Where they disagree, the RCA wins and the difference is explained.
