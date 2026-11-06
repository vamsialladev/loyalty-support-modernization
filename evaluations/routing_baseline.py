"""The request-routing baseline: rules vs TF-IDF + logistic regression, on the same grouped splits (Appendix I; ML-01
to ML-03).

    uv run python -m evaluations.routing_baseline            # train, select, write the report and the artifact

Labels come from scenario facts, never from a model. Dev trains, validation selects by the rule committed first in
`config/routing/thresholds.yaml`, and the stress split is only a drift check. Held-out reporting is Milestone 10.
Nothing in `app/` imports this: if the classifier ever wins, shipping it is its own decision.

**The dataset has gaps:** it has no out-of-scope-only or complaint-only requests, and only the stress split has
injection attempts, so those classes can't be trained or selected here. The report says so rather than quoting
numbers for them. LLM zero-shot and few-shot need a live model, so they are NOT RUN. Embeddings and small-model
tuning are blocked (ML-05).
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, recall_score
from sklearn.pipeline import Pipeline, make_pipeline

from app.arms.conventional import signals

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evaluations" / "routing"
CLASSES = ("missing_points", "multi_issue", "non_english", "suspected_injection")
INJECTION_SCENARIOS = {"S01", "S02"}
NOT_IN_DATASET = ("out_of_scope", "complaint_only")
BINS = 5


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def label_class(label: dict[str, Any]) -> str:
    """From scenario facts only."""
    scenarios = set(label["scenarios"])
    if scenarios & INJECTION_SCENARIOS:
        return "suspected_injection"
    if "D23" in scenarios:
        return "non_english"
    if "D20" in scenarios or label.get("out_of_scope_items"):
        return "multi_issue"
    return "missing_points"


def load_split(root: Path, split: str) -> tuple[list[str], list[str]]:
    data = root / "benchmarks" / "datasets" / "v1"
    labels = {row["case_id"]: row for row in read_jsonl(data / "labels" / f"{split}.jsonl")}
    texts, classes = [], []
    for row in read_jsonl(data / f"{split}.jsonl"):
        texts.append("\n".join(r["text"] for r in row["requests"]))
        classes.append(label_class(labels[row["case_id"]]))
    return texts, classes


def rules_predict(text: str) -> str:
    """Today's rules: the ones arm B uses."""
    if signals.detect_language(text) is not None:
        return "non_english"
    return "multi_issue" if signals.out_of_scope_topics(text) else "missing_points"


def train(texts: list[str], classes: list[str], seed: int) -> Pipeline:
    model = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, sublinear_tf=True),
        LogisticRegression(class_weight="balanced", max_iter=2000, random_state=seed),
    )
    model.fit(texts, classes)
    return model


def scores(truth: list[str], predicted: list[str]) -> dict[str, Any]:
    present = sorted(set(truth))
    recalls = recall_score(truth, predicted, labels=present, average=None, zero_division=0)
    return {
        "cases": len(truth),
        "macro_f1": round(float(f1_score(truth, predicted, labels=present, average="macro", zero_division=0)), 3),
        "recall": {c: round(float(r), 3) for c, r in zip(present, recalls, strict=True)},
        "support": dict(Counter(truth)),
        "labels": present,
        "confusion_matrix": confusion_matrix(truth, predicted, labels=present).tolist(),
    }


def reliability(model: Pipeline, texts: list[str], truth: list[str]) -> list[dict[str, Any]]:
    """Top-class probability against what actually happened. With this few cases it's only a sketch, so no
    probability is shown anywhere (Appendix I3 allows that only once calibration is measured on held-out data)."""
    probabilities = model.predict_proba(texts)
    top = probabilities.max(axis=1)
    hits = np.array([model.classes_[i] == t for i, t in zip(probabilities.argmax(axis=1), truth, strict=True)])
    out = []
    for low in np.linspace(0, 1, BINS, endpoint=False):
        high = low + 1 / BINS
        chosen = (top >= low) & (top < high if high < 1 else top <= 1)
        if chosen.any():
            out.append(
                {
                    "from": round(float(low), 2),
                    "to": round(float(high), 2),
                    "cases": int(chosen.sum()),
                    "mean_probability": round(float(top[chosen].mean()), 3),
                    "correct_share": round(float(hits[chosen].mean()), 3),
                }
            )
    return out


def p95_ms(model: Pipeline, texts: list[str]) -> float:
    timings = []
    for text in texts:
        started = time.perf_counter()
        model.predict([text])
        timings.append((time.perf_counter() - started) * 1000)
    return round(float(np.percentile(timings, 95)), 2)


def decide(rules: dict[str, Any], classifier: dict[str, Any], limits: dict[str, Any], p95: float) -> dict[str, Any]:
    """The rule from the thresholds file, applied mechanically."""
    gain = round(classifier["macro_f1"] - rules["macro_f1"], 3)
    reasons = []
    if gain < limits["minimum_gain_over_rules"]:
        reasons.append(f"gain {gain} is under {limits['minimum_gain_over_rules']}")
    for name, floor in limits["minimum_recall"].items():
        got = classifier["recall"].get(name)
        if got is not None and got < floor:
            reasons.append(f"{name} recall {got} is under {floor}")
    if p95 > limits["maximum_p95_ms_per_request"]:
        reasons.append(f"p95 {p95} ms is over {limits['maximum_p95_ms_per_request']} ms")
    return {"chosen": "rules" if reasons else "tfidf_logistic_regression", "gain": gain, "reasons_against": reasons}


def run(root: Path) -> dict[str, Any]:
    limits = yaml.safe_load((ROOT / "config/routing/thresholds.yaml").read_text(encoding="utf-8"))
    train_texts, train_classes = load_split(root, "dev")
    valid_texts, valid_classes = load_split(root, limits["selection_split"])
    stress_texts, stress_classes = load_split(root, "stress")
    model = train(train_texts, train_classes, limits["seed"])
    rules = scores(valid_classes, [rules_predict(t) for t in valid_texts])
    classifier = scores(valid_classes, list(model.predict(valid_texts)))
    p95 = p95_ms(model, valid_texts)
    report = {
        "synthetic": True,
        "seed": limits["seed"],
        "train_split": "dev",
        "train_support": dict(Counter(train_classes)),
        "selection_split": limits["selection_split"],
        "rules": rules,
        "classifier": classifier,
        "classifier_p95_ms": p95,
        "api_cost_per_1000_usd": 0.0,
        "decision": decide(rules, classifier, limits, p95),
        "reliability_on_validation": reliability(model, valid_texts, valid_classes),
        "drift_check_on_stress": {
            "rules": scores(stress_classes, [rules_predict(t) for t in stress_texts]),
            "classifier": scores(stress_classes, list(model.predict(stress_texts))),
        },
        "classes_not_in_the_dataset": list(NOT_IN_DATASET),
        "not_run": {
            "llm_zero_and_few_shot": "NOT RUN: needs a live model and the owner's go-ahead",
            "embeddings_or_small_model": "Blocked: needs a model download and a GPU budget decision (ML-05)",
        },
    }
    return report


def artifact_bytes(root: Path) -> bytes:
    limits = yaml.safe_load((ROOT / "config/routing/thresholds.yaml").read_text(encoding="utf-8"))
    texts, classes = load_split(root, "dev")
    return pickle.dumps(train(texts, classes, limits["seed"]), protocol=4)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = run(ROOT)
    blob = artifact_bytes(ROOT)
    report["artifact_sha256"] = hashlib.sha256(blob).hexdigest()
    (OUT / "report-v1.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report["decision"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
