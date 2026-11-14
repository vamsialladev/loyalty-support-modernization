"""Feedback to dataset, only through labeling review (spec E5; ENT-21; ADR-0082). **Never automatic.**

Production disagreements become *candidates* for the regression dataset: online QA reviews whose outcome was `wrong`
or `unsure`, or whose explanation was `misleading`, and staff feedback marked "not helpful". This writes them to a
review sheet with codes only: the case reference, where the disagreement came from, and its codes. A free-text
comment, the member's request and every personal detail stay out. A person fills in the label and the decision.
Only rows with a reviewer, a label and `decision=add` can be promoted, and promotion appends them to the input for
the next dataset version. It never edits the frozen v1 dataset or its labels.

    uv run python -m evaluations.feedback_candidates --collect            # from the app database (DATABASE_URL)
    uv run python -m evaluations.feedback_candidates --promote sheet.csv  # reviewed rows only

Synthetic data in this project: the "production" disagreements come from synthetic cases.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from evaluations.run_config import ROOT

OUT = ROOT / "evaluations" / "feedback-candidates"
PROMOTED = OUT / "promoted-for-next-dataset-version.jsonl"
COLUMNS = ("case_reference", "arm", "source", "codes", "label", "reviewer", "decision")
DISAGREEING_QA = {("outcome", "wrong"), ("outcome", "unsure"), ("explanation", "misleading")}
LABELS = ("adjust", "deny", "request_info", "escalate")


@dataclass(frozen=True)
class Candidate:
    case_reference: str
    arm: str
    source: str  # qa | feedback
    codes: str  # rubric answers or a feedback reason code; never free text


def collect(s: Session) -> list[Candidate]:
    from app.persistence.models import Case, Feedback, QaSample

    found: list[Candidate] = []
    for sample, case in s.execute(select(QaSample, Case).join(Case, Case.id == QaSample.case_id)):
        answers = sample.answers or {}
        hits = sorted(f"{k}={v}" for k, v in answers.items() if (k, v) in DISAGREEING_QA)
        if hits:
            found.append(Candidate(case.reference, case.arm, "qa", ";".join(hits)))
    for item, case in s.execute(select(Feedback, Case).join(Case, Case.id == Feedback.case_id)):
        if item.rating == "not_helpful":
            found.append(Candidate(case.reference, case.arm, "feedback", f"not_helpful={item.reason_code or 'none'}"))
    return sorted(set(found), key=lambda c: (c.case_reference, c.source, c.codes))


def sheet(candidates: Iterable[Candidate]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for c in candidates:
        writer.writerow({**c.__dict__, "label": "", "reviewer": "", "decision": ""})
    return buffer.getvalue()


class NotReviewed(ValueError):
    pass


def promotable(text: str) -> list[dict[str, str]]:
    """The reviewed rows to add. Anything half-filled is an error, so a sheet can't be promoted by accident."""
    rows = list(csv.DictReader(io.StringIO(text)))
    chosen: list[dict[str, str]] = []
    problems: list[str] = []
    for n, row in enumerate(rows, start=2):
        decision = (row.get("decision") or "").strip()
        if decision not in ("add", "skip", ""):
            problems.append(f"line {n}: decision must be add, skip or empty")
        if decision != "add":
            continue
        if not (row.get("reviewer") or "").strip():
            problems.append(f"line {n}: no reviewer")
        if (row.get("label") or "").strip() not in LABELS:
            problems.append(f"line {n}: label must be one of {', '.join(LABELS)}")
        chosen.append({k: (row.get(k) or "").strip() for k in COLUMNS})
    if problems:
        raise NotReviewed("; ".join(problems))
    return chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.feedback_candidates")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--collect", action="store_true")
    group.add_argument("--promote", type=Path, metavar="SHEET")
    args = parser.parse_args(argv)
    if args.collect:
        from app.persistence.database import make_engine, make_sessions

        with make_sessions(make_engine(os.environ["DATABASE_URL"]))() as s:
            found = collect(s)
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"candidates-{datetime.now(UTC):%Y-%m-%d}.csv"
        path.write_text(sheet(found), encoding="utf-8")
        print(f"{len(found)} candidates in {path.relative_to(ROOT)}; a person labels them before anything is promoted")
        return 0
    try:
        rows = promotable(args.promote.read_text(encoding="utf-8"))
    except NotReviewed as exc:
        print(f"not promoted: {exc}", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    with PROMOTED.open("a", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps({**row, "promoted_at_utc": stamp}, sort_keys=True) + "\n")
    print(f"{len(rows)} reviewed rows added to {PROMOTED.relative_to(ROOT)} (input for the next dataset version)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
