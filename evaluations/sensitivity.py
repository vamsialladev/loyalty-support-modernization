"""What the "after a stopped credit" choice is worth, so it stays visible (RFC-0003).

    uv run python -m evaluations.sensitivity A_RUN B_RUN A_SECOND_LOOK_RUN B_SECOND_LOOK_RUN --out REPORT

Three variants. The first is the main analysis. The third is reported to show the bias it would bring, never to be used.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from evaluations.compare import HEADER, Labels, Run, _table, load_run, paired, summary_rows
from evaluations.run import DATASET, read_labels
from evaluations.scoring import case_success, false_approval

SUCCESS = "Case success (final ledger, outcome, no duplicate)"
LEDGER = "Final ledger correct"
UNRESOLVED = "Left unresolved"


def changed_cases(plain: Run, looked: Run) -> list[str]:
    """Cases the second look changed. It should only ever touch a stopped credit."""
    other = {r.case_id: r for r in looked.results}
    return sorted(
        r.case_id
        for r in plain.results
        if (r.outcome, dict(r.final_points), r.first_action)
        != (other[r.case_id].outcome, dict(other[r.case_id].final_points), other[r.case_id].first_action)
    )


def over_credits_in(run: Run, labels: Labels, scenario: str) -> str:
    cases = [r for r in run.results if scenario in labels[r.case_id]["scenarios"]]
    return f"{sum(false_approval(r, labels[r.case_id]) for r in cases)}/{len(cases)}"


def report(a: Run, b: Run, a_look: Run, b_look: Run, labels: Labels, split: str) -> str:
    variants: Sequence[tuple[str, Run, Run]] = (
        ("1. Both as written **(main analysis)**", a, b),
        ("2. Both with a second look", a_look, b_look),
        ("3. A as written, B with a second look **(biased, for comparison only)**", a, b_look),
    )
    rows = []
    for name, first, second in variants:
        first_rows, second_rows = summary_rows(first, labels), summary_rows(second, labels)
        rows.append(
            [
                name,
                first_rows[SUCCESS],
                second_rows[SUCCESS],
                first_rows[LEDGER],
                second_rows[LEDGER],
                paired(first, second, labels, case_success),
            ]
        )
    lines = [
        f"# After a stopped credit: sensitivity on the {split} split",
        "",
        HEADER,
        "",
        "See `docs/rfcs/RFC-0003-benchmark.md`, the decision on what happens after the re-check stops a credit.",
        "",
        *_table(
            ["Variant", "A case success", "B case success", "A right ledgers", "B right ledgers", "B minus A"],
            rows,
        ),
        "",
        "## What the second look changed",
        "",
        f"- Arm A: {', '.join(changed_cases(a, a_look)) or 'nothing'}.",
        f"- Arm B: {', '.join(changed_cases(b, b_look)) or 'nothing'}.",
        f"- Left unresolved: A {summary_rows(a, labels)[UNRESOLVED]} as written, "
        f"{summary_rows(a_look, labels)[UNRESOLVED]} with a second look.",
        "",
        "## Does the choice touch arm A's predicted over-credits?",
        "",
        *_table(
            ["Scenario", "A as written", "A with a second look"],
            [
                [code, over_credits_in(a, labels, code), over_credits_in(a_look, labels, code)]
                for code in ("D06", "D07", "D15")
            ],
        ),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.sensitivity")
    parser.add_argument("runs", nargs=4, type=Path, metavar="RUN")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    a, b, a_look, b_look = (load_run(folder) for folder in args.runs)
    split = a.manifest["split"]
    text = report(a, b, a_look, b_look, read_labels(split, DATASET), split)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
