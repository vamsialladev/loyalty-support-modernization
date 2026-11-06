"""Day-one discovery analysis on the synthetic legacy history (Appendix F8).

    python -m evaluations.discovery_analysis     # writes docs/day-one-discovery.md, docs/problem-statement.md,
                                                 # docs/images/day-one/*.png and the executive-brief block

Plain caveat, repeated in every output: the history is generated from the assumptions in
`seed_data/generator/config/scenario_mix.yaml`, so these numbers restate those assumptions. The analysis shows how
an FDE would read a real export on day one; it is not a finding about any real operation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evaluations.financial_model import Assumptions, history_estimate, sensitivity

ROOT = Path(__file__).resolve().parent.parent
CAVEAT = (
    "SYNTHETIC history generated from documented assumptions; the numbers demonstrate the analysis method "
    "and restate those assumptions. They are not findings about a real operation."
)
FAILURES = ("false_denial", "false_approval", "duplicate_credit")
EFFORT = {
    "Data fix": "M",
    "Configuration fix": "S",
    "Integration fix": "M",
    "UI fix": "M",
    "Training/process": "S",
    "AI-assisted": "L",
    "None possible": "-",
}


def load(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    h = root / "seed_data" / "v1" / "history"
    cases = [json.loads(x) for x in (h / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    events = [json.loads(x) for x in (h / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return cases, events


def catalog_predictions(root: Path) -> dict[str, dict[str, str]]:
    """Primary class and predicted fixing arm per defect, read from the pre-registered catalog §2a."""
    text = (root / "docs" / "legacy-defect-catalog.md").read_text(encoding="utf-8")
    section = text.split("## 2a.", 1)[1].split("## 2b.", 1)[0]
    # §11 says which defects only C fixes ("C only | D16, D19, D20, D23; the rest of D18 and D22") and which are split.
    c_row = next(line for line in text.split("## 11.", 1)[1].splitlines() if line.startswith("| C only |"))
    explicit, _, split = c_row.split("|")[2].partition(";")
    c_only = set(re.findall(r"D\d\d", explicit))
    split_bc = set(re.findall(r"D\d\d", split))
    out: dict[str, dict[str, str]] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"D\d\d", cells[1]):
            klass, did, name = cells[0], cells[1], re.sub(r"\s*\[.*?\]", "", cells[2])
            if klass == "None possible":
                arm = "none (escalate)"
            elif klass == "Training/process":
                arm = "platform (all arms)"
            elif did in c_only:
                arm = "C"
            elif did in split_bc:
                arm = "B partly, C rest"
            else:
                arm = "B"
            out[did] = {"class": klass, "name": name, "arm": arm}
    return out


def analyse(cases: list[dict[str, Any]], events: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    a = Assumptions()
    n = len(cases)
    outcomes = Counter(c["outcome"] for c in cases)
    failures = [c for c in cases if c["outcome"] in FAILURES]
    by_driver: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cases:
        by_driver[c["driver"]].append(c)
    preds = catalog_predictions(ROOT)  # the pre-registered catalog in this repository is the single source

    control = {"class": "control", "name": "Control cases", "arm": "A (already correct)"}
    pareto = []
    for driver, group in by_driver.items():
        fails = [c for c in group if c["outcome"] in FAILURES]
        over = sum(max(0, c["points_credited"] - c["points_due"]) for c in group)
        under = sum(max(0, c["points_due"] - c["points_credited"]) for c in group)
        rework_min = sum(max(0, c["contacts"] - 1) * 6 for c in group)
        cost = over * a.point_value_usd + rework_min / 60 * a.agent_cost_per_hour_usd
        pareto.append(
            {
                "driver": driver,
                "cases": len(group),
                "failures": len(fails),
                "failure_rate": len(fails) / len(group),
                "over_points": over,
                "under_points": under,
                "cost_usd": cost,
                "minutes": sum(c["handling_minutes"] for c in group),
                **preds.get(driver, control),
            }
        )
    pareto.sort(key=lambda row: -row["failures"])
    cum, total_fail = 0, len(failures)
    for row in pareto:
        cum += row["failures"]
        row["cumulative_share"] = cum / total_fail if total_fail else 0.0

    weekly: dict[str, dict[str, float]] = defaultdict(lambda: {"opened": 0, "sla_met": 0})
    for c in cases:
        weekly[c["week"]]["opened"] += 1
        weekly[c["week"]]["sla_met"] += c["sla_met"]
    weeks = sorted(weekly)
    resolved_week = [(c["week"], _week(c["resolved_at_utc"])) for c in cases]
    open_at_end = [sum(1 for opened, closed in resolved_week if opened <= w < closed) for w in weeks]

    event_counts = Counter(e["kind"] for e in events)
    satisfaction = defaultdict(list)
    for c in cases:
        if c["satisfaction_proxy"] is not None:
            satisfaction[c["outcome"]].append(c["satisfaction_proxy"])

    fail_by_arm: Counter[str] = Counter()
    for row in pareto:
        fail_by_arm[row["arm"]] += row["failures"]
    predicted_b = fail_by_arm.get("B", 0)
    predicted_split = fail_by_arm.get("B partly, C rest", 0)
    predicted_c_only = fail_by_arm.get("C", 0)
    return {
        "n": n,
        "outcomes": outcomes,
        "failures": total_fail,
        "pareto": pareto,
        "weeks": weeks,
        "weekly": weekly,
        "open_at_end": open_at_end,
        "events": event_counts,
        "satisfaction": {k: sum(v) / len(v) for k, v in satisfaction.items() if v},
        "estimate": history_estimate(cases, a),
        "sensitivity": sensitivity(cases, a),
        "reopened": sum(c["reopened"] for c in cases),
        "repeat_contact_cases": sum(1 for c in cases if c["contacts"] > 1),
        "sla_rate": sum(c["sla_met"] for c in cases) / n,
        "median_minutes": sorted(c["handling_minutes"] for c in cases)[n // 2],
        "fail_by_arm": fail_by_arm,
        "predicted_b_share": predicted_b / total_fail if total_fail else 0.0,
        "predicted_c_only_share": predicted_c_only / total_fail if total_fail else 0.0,
        "predicted_split_share": predicted_split / total_fail if total_fail else 0.0,
        "first_week": weeks[0],
        "last_week": weeks[-1],
    }


def _week(ts: str) -> str:
    from datetime import date

    year, week, _ = date.fromisoformat(ts[:10]).isocalendar()
    return f"{year}-W{week:02d}"


def charts(r: dict[str, Any], out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    names = []
    top = [row for row in r["pareto"] if row["failures"] > 0][:12]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([row["driver"] for row in top], [row["failures"] for row in top], color="#1E4636")
    ax2 = ax.twinx()
    ax2.plot(
        [row["driver"] for row in top], [row["cumulative_share"] * 100 for row in top], color="#94702C", marker="o"
    )
    ax.set_ylabel("Failed cases (count)")
    ax2.set_ylabel("Cumulative share of failures (%)")
    ax.set_title("Pareto of failure drivers, 12-month synthetic history (SYNTHETIC)")
    names.append(_save(fig, out / "pareto.png"))

    fig, ax = plt.subplots(figsize=(9, 4))
    opened = [r["weekly"][w]["opened"] for w in r["weeks"]]
    sla = [100 * r["weekly"][w]["sla_met"] / max(1, r["weekly"][w]["opened"]) for w in r["weeks"]]
    ax.bar(range(len(opened)), opened, color="#8CC4A5", label="cases opened")
    ax2 = ax.twinx()
    ax2.plot(range(len(sla)), sla, color="#1E4636", label="SLA met (%)")
    ax.set_xticks(range(0, len(r["weeks"]), 6), [r["weeks"][i] for i in range(0, len(r["weeks"]), 6)], rotation=30)
    ax.set_ylabel("Cases per week")
    ax2.set_ylabel("Resolved within 5 business days (%)")
    ax.set_title("Weekly volume and SLA attainment (SYNTHETIC)")
    names.append(_save(fig, out / "weekly-volume-sla.png"))

    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(range(len(r["open_at_end"])), r["open_at_end"], color="#94702C")
    ax.set_xticks(range(0, len(r["weeks"]), 6), [r["weeks"][i] for i in range(0, len(r["weeks"]), 6)], rotation=30)
    ax.set_ylabel("Open cases at week end")
    ax.set_title("Backlog (SYNTHETIC)")
    names.append(_save(fig, out / "backlog.png"))

    by_minutes = sorted(r["pareto"], key=lambda row: -row["minutes"])[:10]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.barh(
        [row["driver"] for row in by_minutes][::-1], [row["minutes"] / 60 for row in by_minutes][::-1], color="#1E4636"
    )
    ax.set_xlabel("Agent hours over 12 months (assumed handling times)")
    ax.set_title("Where handling time goes (SYNTHETIC)")
    names.append(_save(fig, out / "handling-time.png"))
    return names


def _save(fig: Any, path: Path) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=110, metadata={"Software": None})
    plt.close(fig)
    return path.name


def report(r: dict[str, Any]) -> str:
    e = r["estimate"]
    o = r["outcomes"]
    top3 = [row for row in r["pareto"] if row["failures"] > 0][:3]
    share3 = top3[-1]["cumulative_share"] if top3 else 0.0
    lines = [
        "# Day-one discovery: what the legacy loyalty queue looks like",
        "",
        f"> **{CAVEAT}** Generated by `python -m evaluations.discovery_analysis` from `seed_data/v1/history/` "
        "(dataset v1, seed 20261102). Money figures are estimates under assumptions A3 and A4 "
        "(`docs/customer-discovery.md` §6).",
        "",
        "## What I'd say in the first meeting",
        "",
        f"Over 12 months ({r['first_week']} to {r['last_week']}) the queue handled **{r['n']:,} missing-points "
        f"requests**. **{r['failures']:,} ({r['failures'] / r['n']:.0%})** ended with the wrong points: "
        f"{o.get('false_denial', 0):,} under-credited, {o.get('false_approval', 0):,} over-credited and "
        f"{o.get('duplicate_credit', 0):,} credited twice. Three drivers ({', '.join(row['driver'] for row in top3)}) "
        f"account for {share3:.0%} of the failures. {r['repeat_contact_cases']:,} cases needed more than one contact "
        f"and {r['reopened']:,} were reopened. Only {r['sla_rate']:.0%} were resolved within 5 business days.",
        "",
        f"Under the stated assumptions, over-credits cost about **${e['over_credit_leakage_usd']:,.0f}** in points "
        f"liability, members were left **{e['under_credit_points_member_harm_proxy']:,} points** short "
        f"(about ${e['under_credit_value_usd']:,.0f}), and handling cost about **${e['handling_cost_usd']:,.0f}** "
        f"(${e['handling_cost_per_case_usd']:.2f} per case). These are estimates, not measurements.",
        "",
        f"The pre-registered catalog predicts that **about {r['predicted_b_share']:.0%} of these failures are "
        f"fixable without AI** (arm B), about {r['predicted_c_only_share']:.0%} need AI (arm C), and about "
        f"{r['predicted_split_share']:.0%} come from defects split between the two (nicknames, attached documents). "
        "The benchmark will test that prediction.",
        "",
        "## Pareto of failure drivers",
        "",
        "![Pareto of failure drivers](images/day-one/pareto.png)",
        "",
        "| Driver | Defect | Cases | Failed | Failure rate | Cumulative share | Primary fix | Predicted fixing arm |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in r["pareto"]:
        if row["failures"]:
            lines.append(
                f"| {row['driver']} | {row['name']} | {row['cases']} | {row['failures']} | "
                f"{row['failure_rate']:.0%} | {row['cumulative_share']:.0%} | {row['class']} | {row['arm']} |"
            )
    lines += [
        "",
        "## Modelled cost of failures (estimates under stated assumptions)",
        "",
        "| Driver | Over-credited points | Under-credited points | Rework + leakage cost (USD) |",
        "|---|---|---|---|",
    ]
    for row in sorted(r["pareto"], key=lambda x: -x["cost_usd"])[:10]:
        lines.append(f"| {row['driver']} | {row['over_points']:,} | {row['under_points']:,} | {row['cost_usd']:,.0f} |")
    lines += [
        "",
        "Sensitivity (each assumption moved -50% / +50%):",
        "",
        "| Assumption | Factor | Value | Over-credit leakage (USD) | Handling cost (USD) |",
        "|---|---|---|---|---|",
    ]
    for s in r["sensitivity"]:
        lines.append(
            f"| {s['assumption']} | {s['factor']} | {s['value']:.4g} | {s['over_credit_leakage_usd']:,.0f} | "
            f"{s['handling_cost_usd']:,.0f} |"
        )
    lines += [
        "",
        "## Where handling time goes",
        "",
        "![Handling time by driver](images/day-one/handling-time.png)",
        "",
        f"Median handling time {r['median_minutes']:.1f} minutes (assumed distribution, not measured). Every case "
        "also pays the four-screen lookup (D14), visible as at least four `searched` events per case.",
        "",
        "## Rework loops (from the event log)",
        "",
        "| Event | Count |",
        "|---|---|",
        *[f"| {k} | {v:,} |" for k, v in sorted(r["events"].items())],
        "",
        "Modelled satisfaction proxy by outcome (formula in the generator config; not real sentiment): "
        + ", ".join(f"{k} {v:.1f}" for k, v in sorted(r["satisfaction"].items()))
        + ".",
        "",
        "## SLA and backlog",
        "",
        "![Weekly volume and SLA attainment](images/day-one/weekly-volume-sla.png)",
        "",
        "![Backlog](images/day-one/backlog.png)",
        "",
        "January and July peaks lengthen resolution times, so SLA attainment drops when volume rises.",
        "",
        "## Opportunity sizing (impact vs effort, predicted per arm)",
        "",
        "| Driver | Failures (impact) | Cost (USD, estimate) | Effort | Predicted fixing arm |",
        "|---|---|---|---|---|",
    ]
    for row in sorted(r["pareto"], key=lambda x: -x["failures"]):
        if row["driver"] != "K" and row["failures"]:
            lines.append(
                f"| {row['driver']} {row['name']} | {row['failures']} | {row['cost_usd']:,.0f} | "
                f"{EFFORT.get(row['class'], '-')} | {row['arm']} |"
            )
    lines += [
        "",
        "Effort: S = configuration or process change, M = data, integration or UI work, L = an AI component with its "
        "own evaluation. **Predicted** improvement per arm (share of history failures whose driver the catalog "
        f"assigns to that arm): B about {r['predicted_b_share']:.0%}, C-only about {r['predicted_c_only_share']:.0%}, "
        f"split between B and C about {r['predicted_split_share']:.0%}; the rest is the write path (platform) or "
        "unfixable. Milestone 10 compares this prediction with the "
        "measured benchmark.",
        "",
    ]
    return "\n".join(lines)


def problem_statement(r: dict[str, Any]) -> str:
    e = r["estimate"]
    return "\n".join(
        [
            "# Problem statement (one page)",
            "",
            f"> {CAVEAT}",
            "",
            "**Who has the problem.** The loyalty operations manager (owner), six support agents and two supervisors "
            "(assumed), and the members who never see the tool but carry the cost of a wrong answer.",
            "",
            f"**What happens today.** {r['n']:,} missing-points requests in 12 months; "
            f"{r['failures'] / r['n']:.0%} end with the wrong points; {r['repeat_contact_cases'] / r['n']:.0%} need "
            f"more than one contact; {r['sla_rate']:.0%} are resolved within 5 business days.",
            "",
            f"**What it costs (estimates under stated assumptions).** About ${e['over_credit_leakage_usd']:,.0f} of "
            f"points liability over-credited, {e['under_credit_points_member_harm_proxy']:,} points members were owed "
            f"and didn't get, and about ${e['handling_cost_usd']:,.0f} of handling time.",
            "",
            "**Why.** Stale rule configuration, data defects (duplicate profiles, merged numbers, blank channels, UTC "
            "dates), exact-match search across four screens, unreadable free text, and approvals that bind to nothing.",
            "",
            f"**What we think fixes it (prediction, pre-registered).** About {r['predicted_b_share']:.0%} of "
            f"failures through better tools and corrected rules (no AI); about {r['predicted_c_only_share']:.0%} may "
            f"need AI for messy requests; about {r['predicted_split_share']:.0%} are split between the two. "
            "Duplicate credits are stopped by a safe write path for every option.",
            "",
            "**Success looks like.** Members end with exactly the points they earned, at the first answer where "
            "possible, with no duplicate credit and an audit trail; measured on held-out cases (`docs/hypotheses.md`).",
            "",
            "**Not in scope.** Refunds, messages to members, adjustments without a supervisor, the posting pipeline.",
            "",
        ]
    )


def executive_block(r: dict[str, Any]) -> str:
    e = r["estimate"]
    return "\n".join(
        [
            "<!-- day-one:start (generated by evaluations/discovery_analysis.py) -->",
            "## Phase 2: the data and the day-one picture (Milestone 3)",
            "",
            "**Outcome.** We built a realistic, fully synthetic copy of the loyalty queue and its systems, and read 12 "
            "months of simulated history the way we'd read a client's real export on day one.",
            "",
            "**Evidence (synthetic, from documented assumptions).**",
            f"- {r['n']:,} requests in a year; {r['failures'] / r['n']:.0%} ended with the wrong points.",
            f"- Estimated cost: about ${e['over_credit_leakage_usd']:,.0f} over-credited and "
            f"{e['under_credit_points_member_harm_proxy']:,} points members were owed but didn't get "
            f"(about ${e['under_credit_value_usd']:,.0f}).",
            f"- Our prediction: about {r['predicted_b_share']:.0%} of the failures can be fixed without AI, and "
            f"about {r['predicted_c_only_share']:.0%} need AI; the rest are split between the two or can't be fixed.",
            "",
            "**Risks.** These numbers restate our own assumptions; a real client's export would replace them. The "
            "person writing the test data also builds the solutions, so 30 labels go to an independent review "
            "(the owner).",
            "",
            "**Decisions needed now.** None. Next: review 30 labels (about 45 minutes).",
            "",
            "**Cost so far.** $0 in services. No AI usage.",
            "<!-- day-one:end -->",
        ]
    )


def write_all(root: Path = ROOT, docs: Path | None = None) -> dict[str, Any]:
    docs = docs or root / "docs"
    cases, events = load(root)
    r = analyse(cases, events, root)
    charts(r, docs / "images" / "day-one")
    (docs / "day-one-discovery.md").write_text(report(r), encoding="utf-8", newline="\n")
    (docs / "problem-statement.md").write_text(problem_statement(r), encoding="utf-8", newline="\n")
    brief = docs / "executive-brief.md"
    text = brief.read_text(encoding="utf-8")
    block = executive_block(r)
    if "<!-- day-one:start" in text:
        text = re.sub(r"<!-- day-one:start.*?<!-- day-one:end -->", block, text, flags=re.S)
    else:
        marker = "## Phase 1:"
        text = text.replace(marker, block + "\n\n" + marker, 1)
    brief.write_text(text, encoding="utf-8", newline="\n")
    return r


CONSOLE_CHARTS = (
    ("pareto.png", "Failure drivers", "Bar chart of failed cases per failure driver, most failures first."),
    ("weekly-volume-sla.png", "Weekly volume and SLA", "Requests opened each week, with the share resolved on time."),
    ("backlog.png", "Backlog", "Open cases at the end of each week."),
    ("handling-time.png", "Handling time", "Handling time per failure driver."),
)


def console_summary(r: dict[str, Any]) -> dict[str, Any]:
    """What the console's day-one page may show: totals per driver, never a case. The app can't import this module or
    read the history (ADR-0062), so these are exported into the app's own folder."""
    o = r["outcomes"]
    return {
        "note": CAVEAT,
        "period": f"{r['first_week']} to {r['last_week']}",
        "cases": r["n"],
        "failed": r["failures"],
        "failed_percent": round(100 * r["failures"] / r["n"]),
        "under_credited": o.get("false_denial", 0),
        "over_credited": o.get("false_approval", 0),
        "credited_twice": o.get("duplicate_credit", 0),
        "predicted_share_b": round(100 * r["predicted_b_share"]),
        "predicted_share_c": round(100 * r["predicted_c_only_share"]),
        "drivers": [
            {
                "driver": row["driver"],
                "name": row["name"],
                "cases": row["cases"],
                "failed": row["failures"],
                "predicted": row["arm"],
            }
            for row in r["pareto"]
            if row["failures"] > 0
        ],
    }


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[16:24]
    return int.from_bytes(head[:4], "big"), int.from_bytes(head[4:], "big")


def export_for_console(r: dict[str, Any], docs: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    charts_out = []
    for name, title, alt in CONSOLE_CHARTS:
        source = docs / "images" / "day-one" / name
        (out / name).write_bytes(source.read_bytes())
        width, height = _png_size(source)
        charts_out.append({"file": name, "title": title, "alt": alt, "width": width, "height": height})
    payload = {**console_summary(r), "charts": charts_out}
    (out / "summary.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.discovery_analysis")
    parser.add_argument("--console-only", action="store_true", help="only refresh the console's day-one export")
    args = parser.parse_args(argv)
    if args.console_only:
        cases, events = load(ROOT)
        r = analyse(cases, events, ROOT)
    else:
        r = write_all()
    export_for_console(r, ROOT / "docs", ROOT / "app" / "web" / "day_one")
    print(f"history cases {r['n']}, failures {r['failures']}, predicted non-AI share {r['predicted_b_share']:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
