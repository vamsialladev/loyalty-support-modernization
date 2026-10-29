"""Financial model (Appendix F4). Every output is an **estimate under stated assumptions**, never a measurement.

Inputs are the discovery assumptions (docs/customer-discovery.md §6). Model cost per case and hosting cost are
`None` until Milestones 10 and 12 measure them; any output that needs them says "not measured yet".

    python -m evaluations.financial_model          # prints the baseline estimate and the sensitivity table
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

LABEL = "estimate under stated assumptions"
ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Assumptions:
    agent_cost_per_hour_usd: float = 32.0  # A3
    point_value_usd: float = 0.008  # A4: points-liability value per point
    monthly_volume: int = 320  # A1
    model_cost_per_case_usd: float | None = None  # not measured yet (Milestone 10)
    infrastructure_per_month_usd: float | None = None  # not measured yet (Milestone 12)
    maintenance_hours_per_month: float = 4.0  # assumption


def history_estimate(cases: list[dict[str, Any]], a: Assumptions) -> dict[str, Any]:
    """Costs of the legacy history under the assumptions. Points over- and under-credited, handling cost, rework."""
    n = len(cases)
    correct = sum(1 for c in cases if c["outcome"] in ("correct", "escalated_correctly"))
    over = sum(max(0, c["points_credited"] - c["points_due"]) for c in cases)
    under = sum(max(0, c["points_due"] - c["points_credited"]) for c in cases)
    minutes = sum(c["handling_minutes"] for c in cases)
    rework_cases = [c for c in cases if c["contacts"] > 1 or c["reopened"]]
    handling = minutes / 60 * a.agent_cost_per_hour_usd
    return {
        "label": LABEL,
        "cases": n,
        "correct_cases": correct,
        "over_credit_points": over,
        "over_credit_leakage_usd": round(over * a.point_value_usd, 2),
        "under_credit_points_member_harm_proxy": under,
        "under_credit_value_usd": round(under * a.point_value_usd, 2),
        "handling_cost_usd": round(handling, 2),
        "handling_cost_per_case_usd": round(handling / n, 2) if n else 0.0,
        "cost_per_correctly_resolved_case_usd": round((handling + over * a.point_value_usd) / correct, 2)
        if correct
        else None,
        "rework_cases": len(rework_cases),
        "incremental_ai_cost": "not measured yet"
        if a.model_cost_per_case_usd is None
        else round(a.model_cost_per_case_usd * n, 2),
    }


def break_even_volume(fixed_monthly_usd: float, saving_per_case_usd: float) -> float | None:
    """Monthly cases needed for savings to cover fixed costs. None when there is no saving per case."""
    if saving_per_case_usd <= 0:
        return None
    return round(fixed_monthly_usd / saving_per_case_usd, 1)


def sensitivity(cases: list[dict[str, Any]], base: Assumptions) -> list[dict[str, Any]]:
    """Over-credit leakage and handling cost when each key assumption moves by -50% / +50%."""
    rows = []
    for name in ("point_value_usd", "agent_cost_per_hour_usd"):
        for factor in (0.5, 1.0, 1.5):
            a = replace(base, **{name: getattr(base, name) * factor})
            est = history_estimate(cases, a)
            rows.append(
                {
                    "assumption": name,
                    "factor": factor,
                    "value": getattr(a, name),
                    "over_credit_leakage_usd": est["over_credit_leakage_usd"],
                    "handling_cost_usd": est["handling_cost_usd"],
                    "label": LABEL,
                }
            )
    return rows


def load_history(root: Path = ROOT) -> list[dict[str, Any]]:
    path = root / "seed_data" / "v1" / "history" / "cases.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> int:
    cases = load_history()
    base = Assumptions()
    print(
        json.dumps(
            {
                "assumptions": asdict(base),
                "estimate": history_estimate(cases, base),
                "sensitivity": sensitivity(cases, base),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
