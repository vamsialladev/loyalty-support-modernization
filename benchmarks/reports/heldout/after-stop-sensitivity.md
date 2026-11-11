# After a stopped credit: sensitivity on the heldout split

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed: the owner reviewed 30 of 280 (human review, AI-assisted), and no label error was confirmed (`evaluations/label-review/`).

See `docs/rfcs/RFC-0003-benchmark.md`, the decision on what happens after the re-check stops a credit.

| Variant | A case success | B case success | A right ledgers | B right ledgers | B minus A |
|---|---|---|---|---|---|
| 1. Both as written **(main analysis)** | 41/80 (51.2%) | 71/80 (88.8%) | 48/80 (60.0%) | 73/80 (91.2%) | +37.5 pp (95% interval +25.0 to +50.0; 41 vs 71 of 80) |
| 2. Both with a second look | 43/80 (53.8%) | 73/80 (91.2%) | 48/80 (60.0%) | 73/80 (91.2%) | +37.5 pp (95% interval +25.0 to +50.0; 43 vs 73 of 80) |
| 3. A as written, B with a second look **(biased, for comparison only)** | 41/80 (51.2%) | 73/80 (91.2%) | 48/80 (60.0%) | 73/80 (91.2%) | +40.0 pp (95% interval +27.5 to +52.5; 41 vs 73 of 80) |

## What the second look changed

- Arm A: HO-058, HO-080.
- Arm B: HO-058, HO-080.
- Left unresolved: A 8/80 (10.0%) as written, 6/80 (7.5%) with a second look.

## Does the choice touch arm A's predicted over-credits?

| Scenario | A as written | A with a second look |
|---|---|---|
| D06 | 1/3 | 1/3 |
| D07 | 2/2 | 2/2 |
| D15 | 2/2 | 2/2 |
