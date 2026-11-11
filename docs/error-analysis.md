# Error analysis (LEG-01; BENCH-12; spec E.2, E.6)

> **SYNTHETIC data, simulated engagement.** Held-out split, 80 cases, frozen at `50b69f6`, run at `dd7ecb7`. Arm C is the live model, 3 runs. Reports: `benchmarks/reports/heldout/`. No real customer, member or reviewer is involved.

## Every failure, on the primary metric

| Arm | Failed | Which | Class (spec E.6) |
|---|---|---|---|
| **C** | 2/80, all 3 runs | D11 ×2 | Business logic in the script: the re-check rightly stops the credit, the ledger is right, and the case stays open. The same 2 for every arm (RFC-0003) |
| **B** | 9/80 | D11 ×2 | As above |
| | | D20 ×3, D23 ×3 | UX and process, **as the catalog predicts:** arm B hands the whole message to a person. The simulation has no person to finish it, so it counts as un-credited |
| | | D19 ×1 | Context: arm B asks which stay, the member answers in free text, and arm B can't read it. The catalog predicts "asks" |
| **A** | 39/80 | 33 fixed by B, 4 only by C, 2 by neither (D11) | Mostly data, integration, rules and search: `docs/root-cause-analysis.md` |

Arm A's 8 false approvals: D25 ×3, D07 ×2, D15 ×2, D06 ×1. Its 24 false denials are mostly "not found" and channel rules. **Arms B and C had no false approvals, in any run.**

## What the numbers rest on

**1. Escalations aren't worked in this simulation. This matters most.** The pre-registered definition counts a case as a false denial if the ledger is short at settlement, and nobody works an escalated case here. The verdicts use that definition and stand. But:

| If a person works every escalation correctly | Result |
|---|---|
| H3: B minus C, false denials | +4.5 pp (1 vs 0 of 22; interval 0.0 to +13.6). By the same rule: **not supported** |
| C minus B, case success | +1.2 pp (77 vs 78 of 80; interval 0.0 to +3.8) |
| B minus A, case success | +45.0 pp (41 vs 77 of 80; interval +33.8 to +56.2) |

So arm C's gain over arm B is mostly **6 fewer handoffs to a person out of 80**, plus reading replies arm B can't. It isn't a better final answer. Whether that's worth having depends on what a handoff costs, which is an assumption here.

**2. Case success doesn't check that a complaint reached anyone.** Arm A scores 3/3 on D20 in held-out by crediting the points and ignoring the complaint. A separate check, on 4 dev and validation cases (`benchmarks/results/live/out-of-scope-check.json`):

| Arm | What happened to the complaint |
|---|---|
| A | Ignored on 2. On the other 2 the whole message went to the billing queue, and the points claim was lost |
| B | All 4 went to a person, whole |
| C | All 4 credited, with the complaint noted for a person |

**3. H4 had 2 clarification cases.** Both arms found both, so its first part can't separate them, and the rule says not supported. That's a weakness in the held-out set. Parts (b) and (c) favour C: 0 unnecessary requests against 2, and 1.09 contacts against 1.30.

**4. One generator wrote every message,** dev and held-out alike, in the same phrasing. Arm C's 80/80 first actions won't survive real messages unchanged, and this benchmark can't say by how much.

**5. Zero run-to-run change** in action, outcome or points, over 3 runs of 80 cases, and 6 runs of the 10 cases chosen at the freeze. Costs did differ between runs, so these were real calls. This is mostly the design: the model can only influence a little, and rules decide the rest. It says nothing about the variation in the text it writes, which isn't scored.

**6. The labels aren't independently reviewed.** The owner reviewed 30 of 280 (human review, AI-assisted, 2026-11-10): 2 disagreed, 1 unsure, none confirmed wrong on investigation. **H2 rests on one of the disputed cases, HO-062:** read without the member's planted reply, arm C's credit becomes a false approval in 3 of 3 runs and H2 is not supported (`benchmarks/reports/heldout/label-review-sensitivity.md`). The same author wrote the scenarios, the arms and the scoring.

## Where arms lost to simpler ones

- **Arm C on held-out:** no slice where A or B beats it, on any of 5 measures: `benchmarks/reports/heldout/a-or-b-beats-c.md`. Don't over-read this: see 4 and 6.
- **Arm C on stress:** 27/30, the same in 3 runs. It misses both D16+D20+D23 cases, the combination of several stays, a complaint and another language. So do A and B.
- **Arm A beats arm B:** on D20, and on the slices it dominates: see the same report. On dev, also B01, where arm B keeps asking a non-member and arm A denies. Held-out has no B01.
- **Fairness pairs, same action, outcome and points:** A 15/20, B 15/20, C 19/20. All the differences are language pairs. A asks for English, and B hands it to a person, which means **a non-English speaker gets a slower or worse route on arms A and B**. C differs on one: PAIR-08, English denied, French sent to a person, with the same 0 points.

## The improvement loop (spec E.6)

Observe, classify, reproduce, fix the responsible component, re-run, review, release. On this benchmark, every bug found was in the measurement. RFC-0003 lists them, from "What the dev pass changed". The one that mattered: arm C's first action was read from arm B's row, which would have understated H2.

**Failing cases join the regression suite.** Arms A and B's held-out results are checked case for case on real Postgres in CI (`tests/test_benchmark_postgres.py`), and scenario mechanics in `tests/test_runner.py`. No automatic prompt changes or retraining come from any of this.

**What could be fixed next, each a new experiment on a new held-out set:**

| Finding | Fix | Who it's for |
|---|---|---|
| D11 stays open after the re-check stops a credit | Reopen it for a person, or close it automatically with the reason | Every arm |
| D19: arm B can't read a free-text answer | Parse an explicit checkout date in a reply | Arm B, which then also serves arm C |
| B01: arm B keeps asking a non-member | Close after one unanswered request, with the reason | Arm B |
| D16+D20+D23: arm C misses the combination | Look at it in the error log first. No evidence yet of what fails | Arm C |
| H4's denominator | At least 10 clarification cases in the next held-out set | The benchmark |
