# Business-value report (BIZ-01, BIZ-04; spec E.7, F4)

> **SYNTHETIC data, simulated engagement, for a fictional hotel group. No real customer, and nobody saved any of this money.** Dollar figures are estimates under stated assumptions. Rates are observed on synthetic held-out cases, and re-weighted to the synthetic history. The numbers and their labels: `benchmarks/reports/heldout/business-value.md`.

## Conclusion, chosen by the evidence

**Non-AI fixes deliver most of the value. AI helps only in certain categories.**

Of arm A's 39 failed held-out cases, arm B fixed 33 (85%), and arm C alone fixed 4 (10%). The catalog predicted about 61% and 21% before any arm existed. Better tools and corrected rules did more than predicted, partly because the simulated member answers arm B's questions so readily. On D11, nothing changes: all arms end the same.

**In one sentence:** build arm B first. Add arm C for messy messages only if avoiding handoffs is worth it to the customer. Its model cost is small, so that decision rests on handoff cost and the risk of real messages, not on the API bill.

## What was observed

| Measure, held-out, re-weighted | A | B | C |
|---|---|---|---|
| Case success | 68.6% | 93.9% | 99.8% |
| False approvals (over-credit) | 5.8% | 0.0% | 0.0% |
| False denials, as registered | 22.1% | 5.8% | 0.0% |
| Handed to a person when it could have been settled | 0.0% | 5.2% | 0.0% |
| Model cost per case, at list price | $0 | $0 | $0.00171 |

Raw, of 80: case success 41, 71, 78. H1 to H7's verdicts: `benchmarks/reports/heldout/hypotheses.md`.

**H2 rests on one case, HO-062, alone.** Read without the simulated member's reply, arm C's credit there would count as a false approval in 3 of 3 runs, and H2 would be not supported. The owner checked the planted reply (it names only ML-8565) and kept the label (`benchmarks/reports/heldout/label-review-sensitivity.md`).

**A caution on arm C's false denials.** If a person works every escalation correctly, arm B's 7 false denials fall to 1, and arm C's case success is 78 against arm B's 77 of 80. Arm C's value is then fewer handoffs, not better answers. See `docs/error-analysis.md`.

## What was estimated

| Per month, at an assumed 320 cases | A | B | C |
|---|---|---|---|
| Points leakage | $953.72 | $0 | $0 |
| Value under-credited to members (harm, not a saving) | $4,769.49 | $1,011.10 | $0 |
| Person time on avoidable handoffs | $0 | $165.42 | $0 |
| Model cost | $0 | $0 | $0.55 |

- **Change, A to B:** case success +25.4 percentage points (+37%). False approvals -5.8 points (-100%).
- **Change, B to C:** case success +5.8 points (+6%). Avoidable handoffs -5.2 points (-100%).
- **Incremental AI cost:** $0.55 a month, from observed cost at list price.
- **Break-even for C over B:** about 248 cases a month, on an assumed $128 of monthly maintenance and $10.01 per handoff, against an assumed 320. **It moves directly with the handoff cost, which is an assumption.** Half that cost, and C doesn't break even at this volume. Infrastructure isn't included, because Milestone 12 measures it.

## What was assumed

Volume 320 a month, agent $32 an hour, a point worth $0.008, handling cost per case from the synthetic history's assumed times, 4 hours of maintenance a month. All from `docs/customer-discovery.md` section 6, and none confirmed by anyone.

## What wasn't measured

- **Human handling time.** H7 is **not tested**: no participants. Scripted timing isn't employee time. Protocol: `docs/timing-protocol.md`.
- **Real satisfaction.** The proxy (4.16, 4.62, 4.90) uses a modelled formula, and isn't real sentiment. Synthetic cases can't establish satisfaction.
- **Real reviewers,** review effort, overrides, automation bias in real people. The simulated supervisor approves what the engine proposes.
- **Whether real messages behave like these.** One generator wrote them all.
- **Infrastructure, support, integration and maintenance effort.**

## What a pilot would have to show

Before believing any of this: real messages, real reviewers, labels reviewed by someone independent, a measured handoff cost and a customer's own point value. The KPIs and go/no-go criteria are in `docs/kpi-tree.md` and `docs/hypotheses.md`, and they remain provisional until a stakeholder approves them.
