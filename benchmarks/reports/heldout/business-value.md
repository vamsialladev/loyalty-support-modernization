# Business value: the numbers

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed: the owner reviewed 30 of 280 (human review, AI-assisted), and no label error was confirmed (`evaluations/label-review/`).

**Everything in dollars is an estimate under stated assumptions. Nobody saved this money.** Rates are held-out, re-weighted to the synthetic history's defect frequencies. Conclusions: `docs/business-value-report.md`.

## Assumed

| Assumption | Value | Source |
|---|---|---|
| Monthly volume | 320 | Discovery assumption A1 |
| Agent cost per hour | $32.00 | A3 |
| Value per point | $0.008 | A4 |
| Handling cost per case | $10.01 | Synthetic history's assumed handling times |
| Maintenance per month | 4.0 hours, $128.00 | Assumption |

## Observed on synthetic held-out cases

| Measure | A | B | C | Kind |
|---|---|---|---|---|
| Case success | 68.6% | 93.9% | 99.8% | Observed, re-weighted |
| False approvals | 5.8% | 0.0% | 0.0% | Observed, re-weighted |
| False denials (nobody works an escalation) | 22.1% | 5.8% | 0.0% | Observed, re-weighted |
| Handed to a person when it could have been settled | 0.0% | 5.2% | 0.0% | Observed, re-weighted |
| Over-credited points per case | 373 | 0 | 0 | Observed, re-weighted |
| Under-credited points per case | 1863 | 395 | 0 | Observed, re-weighted |
| Simulated contacts per case | 1.29 | 1.25 | 1.10 | Simulated |
| Model cost per case | $0.00000 | $0.00000 | $0.00171 | Observed, at list price |

## Estimated per month, at the assumed volume

| Item | A | B | C | Kind |
|---|---|---|---|---|
| Points leakage per month | $953.72 | $0.00 | $0.00 | Estimate |
| Value under-credited to members per month | $4769.49 | $1011.10 | $0.00 | Estimate; member harm |
| Person time on avoidable handoffs per month | $0.00 | $165.42 | $0.00 | Estimate |
| Model cost per month | $0.00 | $0.00 | $0.55 | Estimate from observed cost |

## Changes

- **A to B, case success:** +25.4 pp (+37% relative). False approvals -5.8 pp (-100% relative).
- **B to C, case success:** +5.8 pp (+6% relative). Avoidable handoffs -5.2 pp (-100% relative).
- **H2 rests on one case, HO-062, alone.** Read without the simulated member's reply, arm C's credit there would count as a false approval in 3 of 3 runs, and H2 would be not supported. The owner checked the planted reply (it names only ML-8565) and kept the label (`benchmarks/reports/heldout/label-review-sensitivity.md`).
- **Incremental AI cost:** $0.55 a month at list price (from observed cost).
- **Estimated saving per case:** A to B $2.463; B to C $0.515, net of the model.
- **Break-even for C over B on maintenance alone:** 248.4 cases a month, against an assumed 320. Estimate.

## Unmeasured

- **Human handling time:** scripted timing isn't employee time. H7 is not tested.
- **Infrastructure:** Milestone 12 measures it, so it's left out of the break-even above.
- **Real satisfaction:** the proxy is modelled. Synthetic cases can't establish it.
- **Review, support and integration effort,** and overrides by real reviewers.
- **Whether real messages behave like these.** One generator wrote them.
