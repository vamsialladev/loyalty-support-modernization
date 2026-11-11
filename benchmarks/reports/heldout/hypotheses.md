# Hypotheses on the held-out split

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed: the owner reviewed 30 of 280 (human review, AI-assisted), and no label error was confirmed (`evaluations/label-review/`).

Arm C's runs here are **live**. Business thresholds are provisional: no stakeholder has approved them. Statistical difference and practical value are separate questions, and zero observed doesn't prove zero risk.

| Hypothesis | Verdict | Observed | Why |
|---|---|---|---|
| H1 | **supported** | +37.5 pp (95% interval +25.0 to +50.0; 41 vs 71 of 80) | B minus A on case success |
| H2 | **supported** | +10.0 pp (95% interval +3.8 to +17.5; 72 vs 80 of 80) | C minus B on correct action |
| H3 | **supported** | +31.8 pp (95% interval +13.6 to +50.0; 0 vs 7 of 22) | B minus C on false denials |
| H4 | **not supported** | +0.0 pp (95% interval +0.0 to +0.0; 2 vs 2 of 2) | (a) not supported; (b) holds; (c) holds |
| H5 | **supported** | n/a | $0.00174 per correct case; p95 11.58 s, over 234 correct cases |
| H6 | **supported** | n/a | 0 unauthorized, 0 duplicates, over 2000 case runs |
| H7 | **not tested (NOT RUN)** | n/a | no real participants |

## The same rates, re-weighted to the history's defect frequencies

Defect cases are over-represented in held-out, so raw differences run larger than in normal traffic.

| Metric | A | B | C |
|---|---|---|---|
| Case success | 41/80 (51.2%) raw; 68.6% re-weighted | 71/80 (88.8%) raw; 93.9% re-weighted | 78/80 (97.5%) raw; 99.8% re-weighted |
| Correct first action | 38/80 (47.5%) raw; 64.6% re-weighted | 72/80 (90.0%) raw; 93.5% re-weighted | 80/80 (100.0%) raw; 100.0% re-weighted |
| False approvals | 8/80 (10.0%) raw; 5.8% re-weighted | 0/80 (0.0%) raw; 0.0% re-weighted | 0/80 (0.0%) raw; 0.0% re-weighted |
| False denials | 24/80 (30.0%) raw; 22.1% re-weighted | 7/80 (8.8%) raw; 5.8% re-weighted | 0/80 (0.0%) raw; 0.0% re-weighted |
| Right ledger | 48/80 (60.0%) raw; 72.1% re-weighted | 73/80 (91.2%) raw; 94.2% re-weighted | 80/80 (100.0%) raw; 100.0% re-weighted |

## What rests on treating an escalation as un-credited

**The verdicts above follow the pre-registered definition, and don't change.** The simulation has no person who works an escalated case, so a case handed to a person stays un-credited at settlement. If a person worked every escalation correctly, these would read:

| Question | If a person works every escalation correctly |
|---|---|
| H3: B minus C, false denials | +4.5 pp (95% interval +0.0 to +13.6; 0 vs 1 of 22). By the same rule: **not supported** |
| B minus A, case success | +45.0 pp (95% interval +33.8 to +56.2; 41 vs 77 of 80) |
| C minus B, case success | +1.2 pp (95% interval +0.0 to +3.8; 77 vs 78 of 80) |
| Cases handed to a person when the label says the system could settle them | A 0, B 6, C 0, of 80 |

**So arm C's gain over arm B is mostly fewer handoffs to a person, not a better final answer.** How much that's worth depends on what a handoff costs, which is an assumption here: `business-value.md`.

## What these verdicts can't say

- **H4 had 2 clarification cases.** Both arms found both, so its first part can't separate them. That's a weakness in the held-out set, not evidence they're equal. Its other two parts favour C.
- **Case success doesn't check that a complaint reached someone.** Arm A scores 3/3 on D20 by ignoring the complaint.
- **One generator wrote every message,** in phrasing arm C also saw on dev. Real messages will be messier.
- **H2 rests on one case, HO-062, alone.** Read without the simulated member's reply, arm C's credit there would count as a false approval in 3 of 3 runs, and H2 would be not supported. The owner checked the planted reply (it names only ML-8565) and kept the label (`benchmarks/reports/heldout/label-review-sensitivity.md`).
- **The labels aren't independently reviewed.** The owner reviewed 30 of 280 (human review, AI-assisted): 2 disagreed, 1 unsure, none confirmed wrong. The catalog wasn't reviewed by anyone independent.
- **The simulated supervisor approves whatever the engine proposes,** so nothing here tests real reviewers.

Every number comes from a stored run in `benchmarks/results/`. Simulated member and supervisor.
