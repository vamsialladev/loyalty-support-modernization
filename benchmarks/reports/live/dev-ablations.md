# Comparison on the dev split

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed yet.

**No verdict.** Hypotheses are decided on the held-out split only. This is dev.

| Metric | C [live] | C (ablation-no-repair) [live] | C (ablation-three-turns) [live] | C (ablation-half-context) [live] |
|---|---|---|---|---|
| Case success (final ledger, outcome, no duplicate) | 96/100 (96.0%) | 96/100 (96.0%) | 96/100 (96.0%) | 96/100 (96.0%) |
| Final ledger correct | 100/100 (100.0%) | 100/100 (100.0%) | 100/100 (100.0%) | 100/100 (100.0%) |
| Correct first action | 98/100 (98.0%) | 98/100 (98.0%) | 97/100 (97.0%) | 98/100 (98.0%) |
| False approvals (over-credit) | 0/100 (0.0%) | 0/100 (0.0%) | 0/100 (0.0%) | 0/100 (0.0%) |
| False denials (under-credit) | 0/100 (0.0%) | 0/100 (0.0%) | 0/100 (0.0%) | 0/100 (0.0%) |
| Left unresolved | 4/100 (4.0%) | 4/100 (4.0%) | 4/100 (4.0%) | 4/100 (4.0%) |
| Duplicate credits | 0 | 0 | 0 | 0 |
| Unauthorized actions | 0 | 0 | 0 | 0 |
| Clarification found | 2/2 (100.0%) | 2/2 (100.0%) | 2/2 (100.0%) | 2/2 (100.0%) |
| Unnecessary information requests | 2 | 2 | 3 | 2 |
| Simulated contacts per case | 1.17 | 1.18 | 1.18 | 1.17 |
| Simulated days per case | 2.46 | 2.49 | 2.49 | 2.46 |
| Modelled satisfaction proxy (not real sentiment) | 4.67 | 4.66 | 4.67 | 4.67 |
| Model cost at list price, total / per case | $0.1804 / $0.00180 | $0.1711 / $0.00171 | $0.1467 / $0.00147 | $0.1800 / $0.00180 |
| Cases that kept arm B's result (model run ended early) | 2 | 13 | 36 | 2 |
| Script time p50 / p95 (not human timing) | 7.50 s / 11.20 s | 7.61 s / 9.58 s | 6.91 s / 9.17 s | 7.88 s / 12.06 s |

## Where each case first went wrong (failure funnel)

| First failed link | C [live] | C (ablation-no-repair) [live] | C (ablation-three-turns) [live] | C (ablation-half-context) [live] |
|---|---|---|---|---|
| request_understood | 2 | 2 | 2 | 2 |
| evidence_found | 0 | 0 | 0 | 0 |
| policy_version | 0 | 0 | 0 | 0 |
| eligibility | 0 | 0 | 1 | 0 |
| action_proposed | 0 | 0 | 0 | 0 |
| approval_decision | 0 | 0 | 0 | 0 |
| execution | 0 | 0 | 0 | 0 |
| final_ledger | 0 | 0 | 0 | 0 |
| case_outcome | 2 | 2 | 2 | 2 |
| every link held | 96 | 96 | 95 | 96 |

## By scenario: cases, successes, right ledgers, false approvals, false denials

| Scenario | C [live] | C (ablation-no-repair) [live] | C (ablation-three-turns) [live] | C (ablation-half-context) [live] |
|---|---|---|---|---|
| B01 | 2 / 0 / 2 / 0 / 0 | 2 / 0 / 2 / 0 / 0 | 2 / 0 / 2 / 0 / 0 | 2 / 0 / 2 / 0 / 0 |
| B02 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D01 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D02 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D03 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D04 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D05 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D06 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D07 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D08 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D09 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D10 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D11 | 2 / 0 / 2 / 0 / 0 | 2 / 0 / 2 / 0 / 0 | 2 / 0 / 2 / 0 / 0 | 2 / 0 / 2 / 0 / 0 |
| D12 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D13 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D15 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D16 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D17 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D18 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D19 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D20 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D21 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D22 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D23 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| D24 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| D25 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 | 2 / 2 / 2 / 0 / 0 |
| K01 | 14 / 14 / 14 / 0 / 0 | 14 / 14 / 14 / 0 / 0 | 14 / 14 / 14 / 0 / 0 | 14 / 14 / 14 / 0 / 0 |
| K02 | 8 / 8 / 8 / 0 / 0 | 8 / 8 / 8 / 0 / 0 | 8 / 8 / 8 / 0 / 0 | 8 / 8 / 8 / 0 / 0 |
| K03 | 6 / 6 / 6 / 0 / 0 | 6 / 6 / 6 / 0 / 0 | 6 / 6 / 6 / 0 / 0 | 6 / 6 / 6 / 0 / 0 |
| K04 | 6 / 6 / 6 / 0 / 0 | 6 / 6 / 6 / 0 / 0 | 6 / 6 / 6 / 0 / 0 | 6 / 6 / 6 / 0 / 0 |
| K05 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |
| K06 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 | 3 / 3 / 3 / 0 / 0 |

## Paired differences (later column minus earlier column)

- **C (ablation-no-repair) [live] minus C [live]**
- Case success: +0.0 pp (95% interval +0.0 to +0.0; 96 vs 96 of 100)
- Correct first action: +0.0 pp (95% interval +0.0 to +0.0; 98 vs 98 of 100)
- **C (ablation-three-turns) [live] minus C (ablation-no-repair) [live]**
- Case success: +0.0 pp (95% interval +0.0 to +0.0; 96 vs 96 of 100)
- Correct first action: -1.0 pp (95% interval -3.0 to +0.0; 98 vs 97 of 100)
- **C (ablation-half-context) [live] minus C (ablation-three-turns) [live]**
- Case success: +0.0 pp (95% interval +0.0 to +0.0; 96 vs 96 of 100)
- Correct first action: +1.0 pp (95% interval +0.0 to +3.0; 97 vs 98 of 100)

