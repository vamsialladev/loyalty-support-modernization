# Comparison on the dev split

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed: the owner reviewed 30 of 280 (human review, AI-assisted), and no label error was confirmed (`evaluations/label-review/`).

**No verdict.** Hypotheses are decided on the held-out split only. This is dev.

| Metric | A [deterministic] | B [deterministic] |
|---|---|---|
| Case success (final ledger, outcome, no duplicate) | 61/100 (61.0%) | 89/100 (89.0%) |
| Final ledger correct | 67/100 (67.0%) | 93/100 (93.0%) |
| Correct first action | 60/100 (60.0%) | 90/100 (90.0%) |
| False approvals (over-credit) | 7/100 (7.0%) | 0/100 (0.0%) |
| False denials (under-credit) | 26/100 (26.0%) | 7/100 (7.0%) |
| Left unresolved | 11/100 (11.0%) | 5/100 (5.0%) |
| Duplicate credits | 0 | 0 |
| Unauthorized actions | 0 | 0 |
| Clarification found | 1/2 (50.0%) | 2/2 (100.0%) |
| Unnecessary information requests | 8 | 4 |
| Simulated contacts per case | 1.35 | 1.24 |
| Simulated days per case | 3.23 | 2.61 |
| Modelled satisfaction proxy (not real sentiment) | 4.12 | 4.52 |
| Model cost at list price, total / per case | $0.0000 / $0.00000 | $0.0000 / $0.00000 |
| Cases that kept arm B's result (model run ended early) | 0 | 0 |
| Script time p50 / p95 (not human timing) | 0.53 s / 1.09 s | 1.74 s / 3.93 s |

## Where each case first went wrong (failure funnel)

| First failed link | A [deterministic] | B [deterministic] |
|---|---|---|
| request_understood | 28 | 3 |
| evidence_found | 5 | 0 |
| policy_version | 22 | 0 |
| eligibility | 11 | 8 |
| action_proposed | 1 | 0 |
| approval_decision | 0 | 0 |
| execution | 0 | 0 |
| final_ledger | 0 | 0 |
| case_outcome | 1 | 2 |
| every link held | 32 | 87 |

## By scenario: cases, successes, right ledgers, false approvals, false denials

| Scenario | A [deterministic] | B [deterministic] |
|---|---|---|
| B01 | 2 / 2 / 2 / 0 / 0 | 2 / 0 / 2 / 0 / 0 |
| B02 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D01 | 2 / 0 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D02 | 2 / 0 / 0 / 0 / 2 | 2 / 2 / 2 / 0 / 0 |
| D03 | 2 / 0 / 0 / 0 / 2 | 2 / 2 / 2 / 0 / 0 |
| D04 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D05 | 2 / 0 / 0 / 0 / 2 | 2 / 2 / 2 / 0 / 0 |
| D06 | 3 / 2 / 2 / 1 / 0 | 3 / 3 / 3 / 0 / 0 |
| D07 | 2 / 0 / 0 / 2 / 0 | 2 / 2 / 2 / 0 / 0 |
| D08 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D09 | 2 / 0 / 0 / 0 / 2 | 2 / 2 / 2 / 0 / 0 |
| D10 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D11 | 2 / 0 / 2 / 0 / 0 | 2 / 0 / 2 / 0 / 0 |
| D12 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D13 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D15 | 2 / 0 / 0 / 2 / 0 | 2 / 2 / 2 / 0 / 0 |
| D16 | 3 / 0 / 0 / 0 / 3 | 3 / 3 / 3 / 0 / 0 |
| D17 | 2 / 0 / 0 / 0 / 2 | 2 / 2 / 2 / 0 / 0 |
| D18 | 3 / 1 / 1 / 0 / 2 | 3 / 3 / 3 / 0 / 0 |
| D19 | 3 / 2 / 2 / 0 / 1 | 3 / 2 / 2 / 0 / 1 |
| D20 | 3 / 1 / 1 / 0 / 2 | 3 / 0 / 0 / 0 / 3 |
| D21 | 2 / 0 / 0 / 0 / 2 | 2 / 2 / 2 / 0 / 0 |
| D22 | 3 / 0 / 0 / 0 / 3 | 3 / 3 / 3 / 0 / 0 |
| D23 | 3 / 0 / 0 / 0 / 3 | 3 / 0 / 0 / 0 / 3 |
| D24 | 2 / 0 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D25 | 2 / 0 / 0 / 2 / 0 | 2 / 2 / 2 / 0 / 0 |
| K01 | 14 / 14 / 14 / 0 / 0 | 14 / 14 / 14 / 0 / 0 |
| K02 | 8 / 8 / 8 / 0 / 0 | 8 / 8 / 8 / 0 / 0 |
| K03 | 6 / 6 / 6 / 0 / 0 | 6 / 6 / 6 / 0 / 0 |
| K04 | 6 / 6 / 6 / 0 / 0 | 6 / 6 / 6 / 0 / 0 |
| K05 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| K06 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |

## Paired differences (later column minus earlier column)

- **B [deterministic] minus A [deterministic]**
- Case success: +28.0 pp (95% interval +18.0 to +38.0; 61 vs 89 of 100)
- Correct first action: +30.0 pp (95% interval +20.0 to +40.0; 60 vs 90 of 100)

