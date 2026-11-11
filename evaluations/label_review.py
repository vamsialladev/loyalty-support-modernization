"""The owner's label review: would any held-out result change under the reviewer's readings? (EVAL-04)

    uv run python -m evaluations.label_review

Re-scores the stored held-out runs. Nothing is re-run, and no label file changes: each reading is applied to an
in-memory copy of the labels. On investigation, neither disagreement is a label error (the label follows the written
policy and the pre-registered simulated member), so the labels stay as they are, and these readings are a
sensitivity check. They are not a new experiment. Writes `benchmarks/reports/heldout/label-review-sensitivity.md`
and `.json`. **SYNTHETIC data.**
"""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluations.compare import HEADER, Labels, _table, load_run
from evaluations.decide import Runs
from evaluations.final_report import OUT, decisions
from evaluations.run import DATASET, RESULTS, read_labels
from evaluations.scoring import (
    CaseResult,
    Label,
    case_success,
    correct_action,
    false_approval,
    first_failed_link,
    ledger_correct,
)

Editable = dict[str, dict[str, Any]]  # an in-memory copy of the labels; the files never change
Reading = Callable[[Editable], None]
CASES = ("HO-062", "HO-078")


def ho078_as_pending_posting(labels: Editable) -> None:
    """The reviewer's correction: the queued posting read as a pending posting (v2's section 5.1 rule)."""
    label = labels["HO-078"]
    label["next_action"], label["next_action_detail"] = "no_adjustment_pending", "2026-07-18"
    label["eligibility"] = "eligible"
    label["required_evidence"] = sorted(set(label["required_evidence"]) | {"posting_queue"})
    label["stays"][0]["existing_credit"] = "pending_posting"


def ho062_without_the_reply(labels: Editable) -> None:
    """The final outcome without presuming which stay the member meant: nothing owed until they say."""
    label = labels["HO-062"]
    label["expected_outcome"] = "no_adjustment"
    for stay in label["stays"]:
        stay["expected_final_points"] = 0


def waiting_period_as_eligible(labels: Editable) -> None:
    """The reviewer's unsure item: a claim inside the waiting period called eligible (not yet) instead of ineligible."""
    for label in labels.values():
        if label["next_action"] == "wait_until":
            label["eligibility"] = "eligible"


READINGS: Sequence[tuple[str, Sequence[Reading]]] = (
    ("As labelled (the published results)", ()),
    ("HO-078 as a pending posting", (ho078_as_pending_posting,)),
    ("HO-062 without the member's reply", (ho062_without_the_reply,)),
    ("Waiting-period cases called eligible", (waiting_period_as_eligible,)),
    (
        "All three together",
        (ho078_as_pending_posting, ho062_without_the_reply, waiting_period_as_eligible),
    ),
)


def apply(labels: Labels, readings: Sequence[Reading]) -> Editable:
    changed = {case: copy.deepcopy(dict(label)) for case, label in labels.items()}
    for reading in readings:
        reading(changed)
    return changed


def _count(runs: Runs, test: Callable[[CaseResult, Label], bool]) -> str:
    cases = sorted(runs.by_case)
    return f"{sum(runs.values(cases, test))}/{len(cases)}"


def _held_links(runs: Runs) -> str:
    cases = sorted(runs.by_case)
    return f"{sum(runs.values(cases, lambda r, label: first_failed_link(r, label) is None))}/{len(cases)}"


def score(
    a: Sequence[CaseResult],
    b: Sequence[CaseResult],
    c: Sequence[CaseResult],
    gate: Sequence[CaseResult],
    labels: Labels,
) -> dict[str, Any]:
    arms = {"A": Runs(a, labels), "B": Runs(b, labels), "C": Runs(c, labels)}
    ds = decisions(arms["A"], arms["B"], arms["C"], gate)
    return {
        "verdicts": {d.hypothesis: d.verdict.value for d in ds},
        "why": {d.hypothesis: d.why for d in ds},
        "arms": {
            arm: {
                "case_success": _count(runs, case_success),
                "correct_action": _count(runs, correct_action),
                "ledger_correct": _count(runs, ledger_correct),
                "false_approvals_per_run": round(runs.mean_count_per_run(false_approval), 2),
                "every_link_held": _held_links(runs),
            }
            for arm, runs in arms.items()
        },
    }


def changed_verdicts(results: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    base = next(iter(results.values()))["verdicts"]
    return {
        name: [f"{h}: {base[h]} to {v}" for h, v in row["verdicts"].items() if v != base[h]]
        for name, row in results.items()
    }


def report(results: Mapping[str, Mapping[str, Any]]) -> str:
    changes = changed_verdicts(results)
    hypotheses = list(next(iter(results.values()))["verdicts"])
    lines = [
        "# Label review: would any held-out result change?",
        "",
        HEADER,
        "",
        "The owner reviewed 30 of 280 labels (human review, AI-assisted; `evaluations/label-review/README.md`). This",
        "re-scores the **stored** held-out runs (A and B deterministic, C live, 3 runs) under the reviewer's readings.",
        "Nothing was re-run. No label file was changed: on investigation, neither disagreement is a label error, so",
        "these readings are a sensitivity check, not a new experiment. C counts a case when it holds in 2 of 3 runs.",
        "",
        "## Verdicts",
        "",
        *_table(["Reading", *hypotheses], [[name, *row["verdicts"].values()] for name, row in results.items()]),
        "",
        "## What each reading changes",
        "",
    ]
    for name, row in results.items():
        moved = changes[name]
        lines.append(f"- **{name}:** " + ("; ".join(moved) + "." if moved else "no verdict changes."))
        if moved:
            lines.extend(f"  - Why {h.split(':')[0]} moves: {row['why'][h.split(':')[0]]}." for h in moved)
    lines += ["", "## Per arm, held-out (80 cases)", ""]
    rows = []
    for name, row in results.items():
        for arm, values in row["arms"].items():
            rows.append([name, arm, *values.values()])
    lines += _table(
        [
            "Reading",
            "Arm",
            "Case success",
            "Correct first action",
            "Ledger correct",
            "False approvals per run",
            "Every proof link held",
        ],
        rows,
    )
    lines += [
        "",
        "## Reading the result",
        "",
        "- **HO-078 and the waiting-period wording move no verdict.** They change only correct-action and proof-chain",
        "  counts, by one or a few cases.",
        "- **HO-062 decides H2.** If its final outcome didn't presume the member's reply, arm C's credit after the",
        "  reply would count as a false approval in each of its 3 runs, and H2's rule (C may not have more false",
        "  approvals than B) would fail. So H2 rests on this one case.",
        "- **Why the label keeps the reply:** the pre-registered simulated member (`docs/hypotheses.md`, F6) answers",
        "  with what the scenario holds. HO-062's planted reply is the checkout date 2026-04-02, which only ML-8565",
        "  fits. All three arms asked which stay and got that reply. C then credited ML-8565 (3 of 3 runs, 2",
        "  contacts); A and B left the case unresolved after 4 contacts. The review sheet didn't show the reply,",
        "  which is the likely cause of the disagreement. The owner decides whether the label stands.",
    ]
    return "\n".join(lines) + "\n"


def _gate_runs() -> list[CaseResult]:
    gate: list[CaseResult] = []
    for kind in ("deterministic", "live"):
        for folder in sorted((RESULTS / kind).iterdir()):
            if "as-is" in folder.name or "second-look" in folder.name or not (folder / "manifest.json").exists():
                continue
            gate.extend(load_run(folder).results)
    return gate


def main(out: Path = OUT) -> int:
    labels = read_labels("heldout", DATASET)
    a = load_run(RESULTS / "deterministic" / "a-heldout").results
    b = load_run(RESULTS / "deterministic" / "b-heldout").results
    c = [r for n in (1, 2, 3) for r in load_run(RESULTS / "live" / f"c-heldout-r{n}").results]
    gate = _gate_runs()
    results = {name: score(a, b, c, gate, apply(labels, readings)) for name, readings in READINGS}
    out.mkdir(parents=True, exist_ok=True)
    (out / "label-review-sensitivity.md").write_text(report(results), encoding="utf-8", newline="\n")
    (out / "label-review-sensitivity.json").write_text(
        json.dumps({"label": "SYNTHETIC. Simulated engagement.", "readings": results}, indent=1, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for name, moved in changed_verdicts(results).items():
        print(f"{name}: {'; '.join(moved) or 'no verdict changes'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
