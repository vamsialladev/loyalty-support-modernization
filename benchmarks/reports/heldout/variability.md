# Run-to-run variability, live model

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed: the owner reviewed 30 of 280 (human review, AI-assisted), and no label error was confirmed (`evaluations/label-review/`).

Over 3 runs of 80 cases, 0 cases changed action, outcome or points: none.

## The 10 cases chosen before any held-out run, 6 runs each

| Case | Scenario | Runs | Successes | Distinct results |
|---|---|---|---|---|
| HO-001 | D20 | 6 | 6 | 1 |
| HO-018 | D20 | 6 | 6 | 1 |
| HO-024 | K01 | 6 | 6 | 1 |
| HO-035 | D19 | 6 | 6 | 1 |
| HO-044 | K01 | 6 | 6 | 1 |
| HO-048 | D07 | 6 | 6 | 1 |
| HO-060 | K01 | 6 | 6 | 1 |
| HO-065 | K02 | 6 | 6 | 1 |
| HO-079 | D07 | 6 | 6 | 1 |
| HO-080 | D11 | 6 | 0 | 1 |

Cost per case: mean $0.00170, max $0.00409. Worst investigation per case: p50 7.75 s, p95 11.58 s. Benchmark environment.

Every number comes from a stored run in `benchmarks/results/`. Simulated member and supervisor.
