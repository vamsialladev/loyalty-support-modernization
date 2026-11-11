# A as-is against A: what the shared write path prevents

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed: the owner reviewed 30 of 280 (human review, AI-assisted), and no label error was confirmed (`evaluations/label-review/`).

Descriptive, with no verdict. **A as-is is unsafe by design,** runs only on a disposable database, and is excluded from H1 to H6. Prediction, written before data: duplicate credits on every D10 and lost-response case, a wrong amount on most D11 cases for A as-is; zero of each for A.

| Group | Right ledger | Duplicate credits | Over-credits |
|---|---|---|---|
| A, all held-out | 48/80 (60.0%) | 0 | 8/80 |
| A as-is, all held-out | 44/80 (55.0%) | 2 | 12/80 |
| A, D10 | 2/2 (100.0%) | 0 | 0/2 |
| A as-is, D10 | 0/2 (0.0%) | 2 | 2/2 |
| A, D11 | 2/2 (100.0%) | 0 | 0/2 |
| A as-is, D11 | 0/2 (0.0%) | 0 | 2/2 |

## The lost-response pass: the platform completes the first attempt and drops the reply

| Group | Right ledger | Duplicate credits | Over-credits |
|---|---|---|---|
| A, cases where a credit was attempted | 30/41 (73.2%) | 0 | 8/41 |
| A as-is, cases where a credit was attempted | 0/41 (0.0%) | 45 | 41/41 |

Every number comes from a stored run in `benchmarks/results/`. Simulated member and supervisor.
