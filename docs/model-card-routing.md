# Model card: request-routing baseline (ML-01 to ML-03; Appendix I)

**SYNTHETIC.** Numbers are from `evaluations/routing/report-v1.json`, produced by `uv run python -m evaluations.routing_baseline`. **Not chosen, and not shipped.**

## The decision
The rule was committed before any training (`config/routing/thresholds.yaml`, commit `455fd0b`): rules stay unless a classifier beats them by at least 0.05 macro-F1 on validation. **Rules stay**: the gain was 0.0. Nothing in `app/` imports scikit-learn.

## What was compared
| Method | Status |
|---|---|
| Rules and keywords, the ones arm B uses | Run |
| TF-IDF character n-grams + logistic regression, balanced class weights, seed 20261106 | Run |
| LLM zero-shot and few-shot | **NOT RUN:** needs a live model and the owner's go-ahead |
| Embeddings or a small tuned model | **Blocked (ML-05):** needs a model download and a compute budget decision |

## Results, and why they don't prove much
| Split | Cases | Multi-issue | Non-English | Rules macro-F1 | Classifier macro-F1 |
|---|---|---|---|---|---|
| Validation (selection) | 30 | 1 | 1 | 1.0 | 1.0 |

**Don't read 1.0 as "routing is solved".** Validation has one case in each minority class. The word lists were chosen on dev, and dev and validation come from one generator's phrase bank. A perfect score here can't tell the methods apart, and says little about real messages. Held-out reporting is Milestone 10, and real-world wording would need the pilot.

| Drift check on stress (not used for selection) | Recall: missing points (18) | multi-issue (2) | non-English (2) | injection (8) |
|---|---|---|---|---|
| Rules | 1.0 | 1.0 | 1.0 | 0.0 |
| Classifier | 1.0 | 1.0 | 0.5 | 0.0 |

**Finding:** neither method recognises an injection attempt, which is no surprise, since dev has no examples to train on. Safety doesn't rest on spotting them: an instruction in a message has nothing to act on (`tests/test_arm_c.py`, S01 on arm B in `tests/test_arm_b_console.py`). The classifier also missed one of the two non-English stress cases.

## Practice notes (Appendix I3)
- **Labels:** from scenario facts only (`label_class`), never from a model.
- **Splits:** the existing grouped splits. Dev trains (94 / 3 / 3), which is heavily imbalanced, so classes are weighted.
- **Dataset gaps:** the dataset has no out-of-scope-only or complaint-only requests, so those Appendix I classes **can't be measured here**. Adding them would change the pre-registered composition, so that's a question for Milestone 10's design.
- **Calibration:** a reliability table is in the report, but on 30 cases it's only a sketch. No probability is shown anywhere.
- **Cost and latency:** no API cost; p95 is in the report, measured on this overloaded machine.
- **Artifact:** not stored, because the classifier wasn't chosen. The seed and the script rebuild it; the report records its hash for this run.
