# After a stopped credit: sensitivity on the dev split

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed: the owner reviewed 30 of 280 (human review, AI-assisted), and no label error was confirmed (`evaluations/label-review/`).

See `docs/rfcs/RFC-0003-benchmark.md`, the decision on what happens after the re-check stops a credit.

| Variant | A case success | B case success | A right ledgers | B right ledgers | B minus A |
|---|---|---|---|---|---|
| 1. Both as written **(main analysis)** | 61/100 (61.0%) | 89/100 (89.0%) | 67/100 (67.0%) | 93/100 (93.0%) | +28.0 pp (95% interval +18.0 to +38.0; 61 vs 89 of 100) |
| 2. Both with a second look | 63/100 (63.0%) | 91/100 (91.0%) | 67/100 (67.0%) | 93/100 (93.0%) | +28.0 pp (95% interval +18.0 to +38.0; 63 vs 91 of 100) |
| 3. A as written, B with a second look **(biased, for comparison only)** | 61/100 (61.0%) | 91/100 (91.0%) | 67/100 (67.0%) | 93/100 (93.0%) | +30.0 pp (95% interval +20.0 to +40.0; 61 vs 91 of 100) |

## What the second look changed

- Arm A: DV-031, DV-089.
- Arm B: DV-031, DV-089.
- Left unresolved: A 11/100 (11.0%) as written, 9/100 (9.0%) with a second look.

## Does the choice touch arm A's predicted over-credits?

| Scenario | A as written | A with a second look |
|---|---|---|
| D06 | 1/3 | 1/3 |
| D07 | 2/2 | 2/2 |
| D15 | 2/2 | 2/2 |
