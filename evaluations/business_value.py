"""The business-value numbers (spec E.7; BIZ-01; LGF-05). Observed, estimated, assumed and unmeasured are kept apart.

Case success, points and model cost are observed on synthetic held-out cases. Money comes from the discovery
assumptions in `evaluations/financial_model.py`. **Everything in dollars is an estimate, never a saving anyone
achieved.** Scripted timing isn't employee time, so handling time per case stays an assumption until the timing protocol
runs with real people.

    uv run python -m evaluations.business_value
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from statistics import mean
from typing import Any

from evaluations.compare import HEADER, _table
from evaluations.decide import Runs
from evaluations.final_report import OUT, driver_of, weights
from evaluations.financial_model import Assumptions, break_even_volume, history_estimate, load_history
from evaluations.run import DATASET, RESULTS, read_labels
from evaluations.scoring import Label, case_success, expected_points, false_approval, false_denial

Labels = Mapping[str, Label]


def _weight(case: str, labels: Labels, table: Mapping[str, float]) -> float:
    driver = driver_of(labels[case], table)
    return table[driver] if driver else 0.0


def _weighted_mean(values: Mapping[str, float], labels: Labels, table: Mapping[str, float]) -> float:
    total = sum(_weight(case, labels, table) for case in values)
    return sum(_weight(case, labels, table) * value for case, value in values.items()) / total if total else 0.0


def over_points(runs: Runs, case: str, labels: Labels) -> float:
    rows = runs.by_case[case]
    expected = expected_points(labels[case])
    per_run = [
        sum(max(0, r.final_points.get(s, 0) - expected.get(s, 0)) for s in set(expected) | set(r.final_points))
        for r in rows
    ]
    return mean(per_run)


def under_points(runs: Runs, case: str, labels: Labels) -> float:
    rows = runs.by_case[case]
    expected = expected_points(labels[case])
    per_run = [sum(max(0, expected[s] - r.final_points.get(s, 0)) for s in expected) for r in rows]
    return mean(per_run)


def handed_to_a_person(runs: Runs, case: str, labels: Labels) -> float:
    """A person has to read it, though the label says the system could have settled it."""
    rows = runs.by_case[case]
    return mean(
        1.0 if r.outcome == "escalated" and labels[case]["expected_outcome"] != "escalated" else 0.0 for r in rows
    )


def per_arm(runs: Runs, labels: Labels, table: Mapping[str, float]) -> dict[str, float]:
    cases = sorted(runs.by_case)
    return {
        "success": _weighted_mean({c: float(runs.holds(c, case_success)) for c in cases}, labels, table),
        "false_approval": _weighted_mean({c: float(runs.holds(c, false_approval)) for c in cases}, labels, table),
        "false_denial": _weighted_mean({c: float(runs.holds(c, false_denial)) for c in cases}, labels, table),
        "over_points": _weighted_mean({c: over_points(runs, c, labels) for c in cases}, labels, table),
        "under_points": _weighted_mean({c: under_points(runs, c, labels) for c in cases}, labels, table),
        "to_a_person": _weighted_mean({c: handed_to_a_person(runs, c, labels) for c in cases}, labels, table),
        "contacts": _weighted_mean({c: mean(r.contacts for r in runs.by_case[c]) for c in cases}, labels, table),
        "cost": _weighted_mean({c: mean(r.cost_usd for r in runs.by_case[c]) for c in cases}, labels, table),
    }


def monthly(values: Mapping[str, float], a: Assumptions, handling_per_case: float) -> dict[str, float]:
    """Estimates at the assumed volume. Under-credit is shown as member harm, not as a saving to the business."""
    return {
        "leakage": values["over_points"] * a.point_value_usd * a.monthly_volume,
        "under_credit": values["under_points"] * a.point_value_usd * a.monthly_volume,
        "person_time": values["to_a_person"] * handling_per_case * a.monthly_volume,
        "model": values["cost"] * a.monthly_volume,
    }


def report(arms: Mapping[str, Runs], labels: Labels, a: Assumptions, history: dict[str, Any]) -> str:
    table = weights()
    values = {name: per_arm(runs, labels, table) for name, runs in arms.items()}
    handling = float(history["handling_cost_per_case_usd"])
    money = {name: monthly(v, a, handling) for name, v in values.items()}
    maintenance = a.maintenance_hours_per_month * a.agent_cost_per_hour_usd

    def pp(metric: str, x: str, y: str) -> str:
        change = (values[y][metric] - values[x][metric]) * 100
        relative = change / (values[x][metric] * 100) * 100 if values[x][metric] else 0.0
        return f"{change:+.1f} pp ({relative:+.0f}% relative)"

    def saving_per_case(x: str, y: str) -> float:
        before, after = money[x], money[y]
        return (
            (before["leakage"] + before["person_time"]) - (after["leakage"] + after["person_time"] + after["model"])
        ) / a.monthly_volume

    saving_ab, saving_bc = saving_per_case("A", "B"), saving_per_case("B", "C")
    breakeven_bc = break_even_volume(maintenance, saving_bc)
    rows = [
        ["Case success", *(f"{values[n]['success'] * 100:.1f}%" for n in arms), "Observed, re-weighted"],
        ["False approvals", *(f"{values[n]['false_approval'] * 100:.1f}%" for n in arms), "Observed, re-weighted"],
        [
            "False denials (nobody works an escalation)",
            *(f"{values[n]['false_denial'] * 100:.1f}%" for n in arms),
            "Observed, re-weighted",
        ],
        [
            "Handed to a person when it could have been settled",
            *(f"{values[n]['to_a_person'] * 100:.1f}%" for n in arms),
            "Observed, re-weighted",
        ],
        ["Over-credited points per case", *(f"{values[n]['over_points']:.0f}" for n in arms), "Observed, re-weighted"],
        [
            "Under-credited points per case",
            *(f"{values[n]['under_points']:.0f}" for n in arms),
            "Observed, re-weighted",
        ],
        ["Simulated contacts per case", *(f"{values[n]['contacts']:.2f}" for n in arms), "Simulated"],
        ["Model cost per case", *(f"${values[n]['cost']:.5f}" for n in arms), "Observed, at list price"],
    ]
    money_rows = [
        ["Points leakage per month", *(f"${money[n]['leakage']:.2f}" for n in arms), "Estimate"],
        [
            "Value under-credited to members per month",
            *(f"${money[n]['under_credit']:.2f}" for n in arms),
            "Estimate; member harm",
        ],
        ["Person time on avoidable handoffs per month", *(f"${money[n]['person_time']:.2f}" for n in arms), "Estimate"],
        ["Model cost per month", *(f"${money[n]['model']:.2f}" for n in arms), "Estimate from observed cost"],
    ]
    return "\n".join(
        [
            "# Business value: the numbers",
            "",
            HEADER,
            "",
            "**Everything in dollars is an estimate under stated assumptions. Nobody saved this money.** Rates are "
            "held-out, re-weighted to the synthetic history's defect frequencies. Conclusions: "
            "`docs/business-value-report.md`.",
            "",
            "## Assumed",
            "",
            *_table(
                ["Assumption", "Value", "Source"],
                [
                    ["Monthly volume", str(a.monthly_volume), "Discovery assumption A1"],
                    ["Agent cost per hour", f"${a.agent_cost_per_hour_usd:.2f}", "A3"],
                    ["Value per point", f"${a.point_value_usd}", "A4"],
                    ["Handling cost per case", f"${handling:.2f}", "Synthetic history's assumed handling times"],
                    [
                        "Maintenance per month",
                        f"{a.maintenance_hours_per_month} hours, ${maintenance:.2f}",
                        "Assumption",
                    ],
                ],
            ),
            "",
            "## Observed on synthetic held-out cases",
            "",
            *_table(["Measure", *arms, "Kind"], rows),
            "",
            "## Estimated per month, at the assumed volume",
            "",
            *_table(["Item", *arms, "Kind"], money_rows),
            "",
            "## Changes",
            "",
            f"- **A to B, case success:** {pp('success', 'A', 'B')}. False approvals {pp('false_approval', 'A', 'B')}.",
            f"- **B to C, case success:** {pp('success', 'B', 'C')}. Avoidable handoffs {pp('to_a_person', 'B', 'C')}.",
            f"- **Incremental AI cost:** ${money['C']['model']:.2f} a month at list price (from observed cost).",
            f"- **Estimated saving per case:** A to B ${saving_ab:.3f}; B to C ${saving_bc:.3f}, net of the model.",
            "- **Break-even for C over B on maintenance alone:** "
            + (f"{breakeven_bc} cases a month" if breakeven_bc else "no saving per case, so none")
            + f", against an assumed {a.monthly_volume}. Estimate.",
            "",
            "## Unmeasured",
            "",
            "- **Human handling time:** scripted timing isn't employee time. H7 is not tested.",
            "- **Infrastructure:** Milestone 12 measures it, so it's left out of the break-even above.",
            "- **Real satisfaction:** the proxy is modelled. Synthetic cases can't establish it.",
            "- **Review, support and integration effort,** and overrides by real reviewers.",
            "- **Whether real messages behave like these.** One generator wrote them.",
            "",
        ]
    )


def main() -> int:
    from evaluations.compare import load_run

    labels = read_labels("heldout", DATASET)
    deterministic, live = RESULTS / "deterministic", RESULTS / "live"
    arms = {
        "A": Runs(load_run(deterministic / "a-heldout").results, labels),
        "B": Runs(load_run(deterministic / "b-heldout").results, labels),
        "C": Runs([r for n in (1, 2, 3) for r in load_run(live / f"c-heldout-r{n}").results], labels),
    }
    a = Assumptions()
    history = history_estimate(load_history(), a)
    text = report(arms, labels, a, history)
    (OUT / "business-value.md").write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
