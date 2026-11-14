"""A privacy-filtered daily export of operational metrics, for a BI tool or warehouse (spec E7; ENT-32).

One CSV row per day, arm and who worked the cases (people or scripted runs, never mixed). **Only counts, sums and
medians, from an allow-list of columns:** no free text, no names, emails, member or confirmation numbers, case
references, usernames or IDs. A test plants personal data in cases, notes and requests and checks none of it, nor any
identifier, reaches the file.

    python -m app.services.analytics_export --day 2026-11-13 --out exports/analytics-2026-11-13.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.case_states import CaseState
from app.persistence.models import AdjustmentRequestRow, AiRun, Case, CaseEvent

COLUMNS = (
    "day",
    "arm",
    "worked_by",
    "cases_received",
    "cases_resolved",
    "cases_escalated",
    "information_requests",
    "overrides",
    "adjustments_requested",
    "adjustments_executed",
    "points_executed",
    "ai_runs",
    "ai_tokens",
    "ai_cost_microusd",
    "median_steps",
)
NOTE = "# Synthetic data. Counts only: no free text, no personal data, no identifiers (ENT-32)."


@dataclass
class _Row:
    day: str
    arm: str
    worked_by: str
    cases_received: int = 0
    cases_resolved: int = 0
    cases_escalated: int = 0
    information_requests: int = 0
    overrides: int = 0
    adjustments_requested: int = 0
    adjustments_executed: int = 0
    points_executed: int = 0
    ai_runs: int = 0
    ai_tokens: int = 0
    ai_cost_microusd: int = 0
    median_steps: float | None = None


def rows_for_day(s: Session, customer_id: str, day: str) -> list[dict[str, object]]:
    cases = [c for c in s.scalars(select(Case).where(Case.customer_id == customer_id)) if c.received_at_utc[:10] == day]
    ids = [c.id for c in cases]
    if not ids:
        return []
    events: dict[int, list[CaseEvent]] = {}
    for e in s.scalars(select(CaseEvent).where(CaseEvent.case_id.in_(ids))):
        events.setdefault(e.case_id, []).append(e)
    adjustments: dict[int, list[AdjustmentRequestRow]] = {}
    for a in s.scalars(select(AdjustmentRequestRow).where(AdjustmentRequestRow.case_id.in_(ids))):
        adjustments.setdefault(a.case_id, []).append(a)
    runs: dict[int, list[AiRun]] = {}
    for r in s.scalars(select(AiRun).where(AiRun.case_id.in_(ids))):
        runs.setdefault(r.case_id, []).append(r)

    table: dict[tuple[str, str], _Row] = {}
    steps: dict[tuple[str, str], list[int]] = {}
    for case in cases:
        own = events.get(case.id, [])
        key = (case.arm, "scripted" if any(e.actor_kind == "scripted" for e in own) else "human")
        row = table.setdefault(key, _Row(day, *key))
        row.cases_received += 1
        row.cases_resolved += case.status == CaseState.RESOLVED.value
        actions = Counter(e.action for e in own)
        row.cases_escalated += actions["case_escalated"] > 0
        row.information_requests += actions["information_requested"]
        row.overrides += sum(bool(e.detail.get("override")) for e in own if e.action == "case_closed")
        for a in adjustments.get(case.id, []):
            row.adjustments_requested += 1
            if a.status == "executed":
                row.adjustments_executed += 1
                row.points_executed += a.points
        for r in runs.get(case.id, []):
            row.ai_runs += 1
            row.ai_tokens += r.input_tokens + r.output_tokens
            row.ai_cost_microusd += r.cost_microusd
        steps.setdefault(key, []).append(len(own))
    out: list[dict[str, object]] = []
    for key in sorted(table):
        row = table[key]
        row.median_steps = median(steps[key]) if steps[key] else None
        out.append({c: getattr(row, c) for c in COLUMNS})
    return out


def to_csv(rows: list[dict[str, object]]) -> str:
    buffer = io.StringIO()
    buffer.write(NOTE + "\n")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.services.analytics_export")
    parser.add_argument("--day", required=True, help="YYYY-MM-DD (by when cases were received)")
    parser.add_argument("--out", type=Path, help="file to write; default: standard output")
    args = parser.parse_args(argv)

    from app.persistence.database import make_engine, make_sessions
    from app.settings import AppSettings

    settings = AppSettings.from_env()
    with make_sessions(make_engine(settings.database_url))() as s:
        text = to_csv(rows_for_day(s, settings.customer_id, args.day))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
