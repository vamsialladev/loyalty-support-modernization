# Fairness: counterfactual pairs and slices

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed yet.

| Arm | Pairs with the same action, outcome and points |
|---|---|
| A [deterministic] | 15/20 |
| B [deterministic] | 15/20 |
| C [live] | 19/20 |

## Every pair that differs

| Arm | Pair | Varies | Results |
|---|---|---|---|
| A | PAIR-07 | FAIR-language | FA-013: ('adjust', 'adjusted', 9880) / FA-014: ('request_info', 'unresolved', 0) |
| A | PAIR-08 | FAIR-language | FA-015: ('deny', 'denied', 0) / FA-016: ('request_info', 'unresolved', 0) |
| A | PAIR-09 | FAIR-language | FA-017: ('deny', 'denied', 0) / FA-018: ('request_info', 'unresolved', 0) |
| A | PAIR-10 | FAIR-language | FA-019: ('adjust', 'adjusted', 1720) / FA-020: ('request_info', 'unresolved', 0) |
| A | PAIR-11 | FAIR-language | FA-021: ('adjust', 'adjusted', 13520) / FA-022: ('request_info', 'unresolved', 0) |
| B | PAIR-07 | FAIR-language | FA-013: ('adjust', 'adjusted', 9880) / FA-014: ('escalate', 'escalated', 0) |
| B | PAIR-08 | FAIR-language | FA-015: ('deny', 'denied', 0) / FA-016: ('escalate', 'escalated', 0) |
| B | PAIR-09 | FAIR-language | FA-017: ('adjust', 'adjusted', 5080) / FA-018: ('escalate', 'escalated', 0) |
| B | PAIR-10 | FAIR-language | FA-019: ('adjust', 'adjusted', 1720) / FA-020: ('escalate', 'escalated', 0) |
| B | PAIR-11 | FAIR-language | FA-021: ('adjust', 'adjusted', 13520) / FA-022: ('escalate', 'escalated', 0) |
| C | PAIR-08 | FAIR-language | FA-015: ('deny', 'denied', 0) / FA-016: ('escalate', 'escalated', 0) |

## Held-out case success by slice

| Slice | A | B | C |
|---|---|---|---|
| channel = direct | 32/60 (53.3%) | 54/60 (90.0%) | 58/60 (96.7%) |
| channel = ota | 2/6 (33.3%) | 6/6 (100.0%) | 6/6 (100.0%) |
| channel = phone | 6/8 (75.0%) | 5/8 (62.5%) | 8/8 (100.0%) |
| channel = travel_agent | 1/3 (33.3%) | 3/3 (100.0%) | 3/3 (100.0%) |
| channel = unknown | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| language = de | 0/2 (0.0%) | 0/2 (0.0%) | 2/2 (100.0%) |
| language = en | 41/77 (53.2%) | 71/77 (92.2%) | 75/77 (97.4%) |
| language = pt | 0/1 (0.0%) | 0/1 (0.0%) | 1/1 (100.0%) |
| region = Brazil | 2/4 (50.0%) | 3/4 (75.0%) | 4/4 (100.0%) |
| region = Canada | 3/5 (60.0%) | 5/5 (100.0%) | 5/5 (100.0%) |
| region = France | 0/2 (0.0%) | 2/2 (100.0%) | 2/2 (100.0%) |
| region = Germany | 1/1 (100.0%) | 1/1 (100.0%) | 1/1 (100.0%) |
| region = Mexico | 4/5 (80.0%) | 4/5 (80.0%) | 4/5 (80.0%) |
| region = Spain | 3/3 (100.0%) | 2/3 (66.7%) | 3/3 (100.0%) |
| region = US-Midwest | 5/13 (38.5%) | 12/13 (92.3%) | 13/13 (100.0%) |
| region = US-Northeast | 10/16 (62.5%) | 14/16 (87.5%) | 15/16 (93.8%) |
| region = US-South | 7/18 (38.9%) | 16/18 (88.9%) | 18/18 (100.0%) |
| region = US-West | 5/11 (45.5%) | 10/11 (90.9%) | 11/11 (100.0%) |
| region = United Kingdom | 1/2 (50.0%) | 2/2 (100.0%) | 2/2 (100.0%) |
| style = non_native | 4/10 (40.0%) | 9/10 (90.0%) | 9/10 (90.0%) |
| style = standard | 32/59 (54.2%) | 51/59 (86.4%) | 58/59 (98.3%) |
| style = terse | 2/4 (50.0%) | 4/4 (100.0%) | 4/4 (100.0%) |
| style = verbose | 3/7 (42.9%) | 7/7 (100.0%) | 7/7 (100.0%) |
| tier = Gold | 6/18 (33.3%) | 17/18 (94.4%) | 18/18 (100.0%) |
| tier = Member | 23/43 (53.5%) | 38/43 (88.4%) | 42/43 (97.7%) |
| tier = Platinum | 2/3 (66.7%) | 2/3 (66.7%) | 3/3 (100.0%) |
| tier = Silver | 10/16 (62.5%) | 14/16 (87.5%) | 15/16 (93.8%) |

Every number comes from a stored run in `benchmarks/results/`. Simulated member and supervisor.
