"""Drift signals with configurable alert thresholds (spec E5; ENT-19).

Seven signals, each computed from what the app already stores, for one window of cases (by when they were received):
escalation rate, override rate, validation-failure rate, citation-failure rate, tool-error rate, tokens per case, and
the request-category mix (the queue a case was routed to). A signal **drifts** when it moves more than its threshold
from a baseline window. Thresholds live in the customer's configuration (`monitoring.drift`), because what counts as
a worrying change is the customer's call; the shipped numbers are assumptions, not measurements.

Observed rates only, never a score: nothing here knows the right answer (same rule as `app/services/metrics.py`).
Scripted benchmark cases are left out, so a benchmark run can't look like drift in real work.

    python -m app.services.drift --baseline 2026-10-01:2026-10-31 --current 2026-11-01:2026-11-30
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import AiRun, AiStep, Case, CaseEvent

ESCALATION, OVERRIDE, VALIDATION, CITATION, TOOL_ERROR, TOKENS, MIX = (
    "escalation_rate",
    "override_rate",
    "validation_failure_rate",
    "citation_failure_rate",
    "tool_error_rate",
    "tokens_per_case",
    "category_mix_distance",
)
VALIDATION_STOPS = frozenset({"invalid_result"})
CITATION_PROBLEM = "unsupported_citation"
TOOL_OK = "ok"


@dataclass(frozen=True)
class Window:
    start: str  # YYYY-MM-DD, inclusive
    end: str  # YYYY-MM-DD, inclusive

    @classmethod
    def parse(cls, text: str) -> Window:
        start, end = text.split(":", 1)
        return cls(start, end)

    def contains(self, utc: str) -> bool:
        return self.start <= utc[:10] <= self.end


@dataclass
class Signals:
    window: Window
    cases: int = 0
    values: dict[str, float | None] = field(default_factory=dict)
    category_mix: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class DriftAlert:
    signal: str
    baseline: float | None
    current: float | None
    change: float
    threshold: float
    runbook: str = "docs/runbooks/ai-quality-drift.md"


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 4)


def compute(s: Session, customer_id: str, window: Window) -> Signals:
    cases = [
        c for c in s.scalars(select(Case).where(Case.customer_id == customer_id)) if window.contains(c.received_at_utc)
    ]
    ids = {c.id for c in cases}
    events: dict[int, list[CaseEvent]] = {}
    if ids:
        for e in s.scalars(select(CaseEvent).where(CaseEvent.case_id.in_(ids))):
            events.setdefault(e.case_id, []).append(e)
    people = [c for c in cases if not any(e.actor_kind == "scripted" for e in events.get(c.id, []))]
    keep = {c.id for c in people}
    escalated = sum(any(e.action == "case_escalated" for e in events.get(i, [])) for i in keep)
    closed = [e for i in keep for e in events.get(i, []) if e.action == "case_closed"]
    overrides = sum(bool(e.detail.get("override")) for e in closed)
    runs = list(s.scalars(select(AiRun).where(AiRun.case_id.in_(keep)))) if keep else []
    run_ids = [r.id for r in runs]
    tools = list(s.scalars(select(AiStep).where(AiStep.run_id.in_(run_ids), AiStep.kind == "tool"))) if run_ids else []
    invalid = sum(r.stop_reason in VALIDATION_STOPS for r in runs)
    citation = sum(any(str(p).startswith(CITATION_PROBLEM) for p in (r.problems or [])) for r in runs)
    tool_errors = sum(t.status != TOOL_OK for t in tools)
    ai_cases = {r.case_id for r in runs}
    tokens = sum(r.input_tokens + r.output_tokens for r in runs)
    mix = Counter(c.queue for c in people)
    total = sum(mix.values())
    return Signals(
        window,
        len(people),
        {
            ESCALATION: _rate(escalated, len(people)),
            OVERRIDE: _rate(overrides, len(closed)),
            VALIDATION: _rate(invalid, len(runs)),
            CITATION: _rate(citation, len(runs)),
            TOOL_ERROR: _rate(tool_errors, len(tools)),
            TOKENS: None if not ai_cases else round(tokens / len(ai_cases), 1),
        },
        {k: round(v / total, 4) for k, v in sorted(mix.items())} if total else {},
    )


def mix_distance(a: dict[str, float], b: dict[str, float]) -> float | None:
    """Total variation distance between two category mixes: 0 = the same, 1 = nothing in common."""
    if not a or not b:
        return None
    return round(sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b)) / 2, 4)


def compare(baseline: Signals, current: Signals, thresholds: dict[str, float], min_cases: int = 30) -> list[DriftAlert]:
    """A signal drifts when its change exceeds its threshold. Rates compare in absolute points, tokens per case as a
    fraction of the baseline. Too few cases in either window means no alert at all, rather than a noisy one."""
    if baseline.cases < min_cases or current.cases < min_cases:
        return []
    alerts: list[DriftAlert] = []
    for name, limit in thresholds.items():
        if name == MIX:
            distance = mix_distance(baseline.category_mix, current.category_mix)
            if distance is not None and distance > limit:
                alerts.append(DriftAlert(name, 0.0, distance, distance, limit))
            continue
        before, after = baseline.values.get(name), current.values.get(name)
        if before is None or after is None:
            continue
        change = (after - before) / before if name == TOKENS and before else after - before
        if abs(change) > limit:
            alerts.append(DriftAlert(name, before, after, round(change, 4), limit))
    return alerts


def report(baseline: Signals, current: Signals, alerts: list[DriftAlert]) -> dict[str, Any]:
    return {
        "note": "Observed rates from synthetic cases; thresholds are assumptions in the customer configuration.",
        "baseline": asdict(baseline),
        "current": asdict(current),
        "alerts": [asdict(a) for a in alerts],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.services.drift")
    parser.add_argument("--baseline", required=True, type=Window.parse, help="YYYY-MM-DD:YYYY-MM-DD")
    parser.add_argument("--current", required=True, type=Window.parse, help="YYYY-MM-DD:YYYY-MM-DD")
    args = parser.parse_args(argv)

    from app.persistence.database import make_engine, make_sessions
    from app.services.customer_config import customer_config
    from app.settings import AppSettings

    settings = AppSettings.from_env()
    config = customer_config(settings.customer_id)
    with make_sessions(make_engine(settings.database_url))() as s:
        before = compute(s, settings.customer_id, args.baseline)
        after = compute(s, settings.customer_id, args.current)
    alerts = compare(before, after, config.drift_thresholds, config.drift_min_cases)
    print(json.dumps(report(before, after, alerts), indent=2))
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
