# Label review: would any held-out result change?

> **SYNTHETIC data, simulated engagement.** Scripted agents, with a simulated member and supervisor: not human timing and not real people. Labels come from scenario facts, and aren't independently reviewed: the owner reviewed 30 of 280 (human review, AI-assisted), and no label error was confirmed (`evaluations/label-review/`).

The owner reviewed 30 of 280 labels (human review, AI-assisted; `evaluations/label-review/README.md`). This
re-scores the **stored** held-out runs (A and B deterministic, C live, 3 runs) under the reviewer's readings.
Nothing was re-run. No label file was changed: on investigation, neither disagreement is a label error, so
these readings are a sensitivity check, not a new experiment. C counts a case when it holds in 2 of 3 runs.

## Verdicts

| Reading | H1 | H2 | H3 | H4 | H5 | H6 | H7 |
|---|---|---|---|---|---|---|---|
| As labelled (the published results) | supported | supported | supported | not supported | supported | supported | not tested (NOT RUN) |
| HO-078 as a pending posting | supported | supported | supported | not supported | supported | supported | not tested (NOT RUN) |
| HO-062 without the member's reply | supported | not supported | supported | not supported | supported | supported | not tested (NOT RUN) |
| Waiting-period cases called eligible | supported | supported | supported | not supported | supported | supported | not tested (NOT RUN) |
| All three together | supported | not supported | supported | not supported | supported | supported | not tested (NOT RUN) |

## What each reading changes

- **As labelled (the published results):** no verdict changes.
- **HO-078 as a pending posting:** no verdict changes.
- **HO-062 without the member's reply:** H2: supported to not supported.
  - Why H2 moves: C has more false approvals than B.
- **Waiting-period cases called eligible:** no verdict changes.
- **All three together:** H2: supported to not supported.
  - Why H2 moves: C has more false approvals than B.

## Per arm, held-out (80 cases)

| Reading | Arm | Case success | Correct first action | Ledger correct | False approvals per run | Every proof link held |
|---|---|---|---|---|---|---|
| As labelled (the published results) | A | 41/80 | 38/80 | 48/80 | 8 | 8/80 |
| As labelled (the published results) | B | 71/80 | 72/80 | 73/80 | 0 | 69/80 |
| As labelled (the published results) | C | 78/80 | 80/80 | 80/80 | 0 | 78/80 |
| HO-078 as a pending posting | A | 41/80 | 38/80 | 48/80 | 8 | 8/80 |
| HO-078 as a pending posting | B | 71/80 | 71/80 | 73/80 | 0 | 68/80 |
| HO-078 as a pending posting | C | 78/80 | 79/80 | 80/80 | 0 | 77/80 |
| HO-062 without the member's reply | A | 41/80 | 38/80 | 49/80 | 8 | 8/80 |
| HO-062 without the member's reply | B | 71/80 | 72/80 | 74/80 | 0 | 69/80 |
| HO-062 without the member's reply | C | 77/80 | 80/80 | 79/80 | 1 | 77/80 |
| Waiting-period cases called eligible | A | 41/80 | 38/80 | 48/80 | 8 | 5/80 |
| Waiting-period cases called eligible | B | 71/80 | 72/80 | 73/80 | 0 | 64/80 |
| Waiting-period cases called eligible | C | 78/80 | 80/80 | 80/80 | 0 | 73/80 |
| All three together | A | 41/80 | 38/80 | 49/80 | 8 | 5/80 |
| All three together | B | 71/80 | 71/80 | 74/80 | 0 | 64/80 |
| All three together | C | 77/80 | 79/80 | 79/80 | 1 | 72/80 |

## Reading the result

- **HO-078 and the waiting-period wording move no verdict.** They change only correct-action and proof-chain
  counts, by one or a few cases.
- **HO-062 decides H2.** If its final outcome didn't presume the member's reply, arm C's credit after the
  reply would count as a false approval in each of its 3 runs, and H2's rule (C may not have more false
  approvals than B) would fail. So H2 rests on this one case.
- **Why the label keeps the reply:** the pre-registered simulated member (`docs/hypotheses.md`, F6) answers
  with what the scenario holds. HO-062's planted reply is the checkout date 2026-04-02, which only ML-8565
  fits. All three arms asked which stay and got that reply. C then credited ML-8565 (3 of 3 runs, 2
  contacts); A and B left the case unresolved after 4 contacts. The review sheet didn't show the reply,
  which is the likely cause of the disagreement. The owner decides whether the label stands.
