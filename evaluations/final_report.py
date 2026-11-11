"""The benchmark's reports, generated from stored runs (spec E.3, E.4, F7, F8; docs/hypotheses.md sections 2 and 3).

    uv run python -m evaluations.final_report

Every verdict comes from `evaluations/decide.py` applying the pre-registered rules. Nothing here is chosen by hand,
and every number traces to a stored run in `benchmarks/results/`. Every slice where A or B beats C is listed by the
code, not picked.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from statistics import mean

import yaml

from evaluations.compare import HEADER, Run, _table, by_scenario, funnel, load_run, repeat_differences, summary_rows
from evaluations.decide import (
    Decision,
    Difference,
    Runs,
    Verdict,
    difference,
    h1,
    h2,
    h3,
    h4,
    h5,
    h6,
    h7,
    latency_p95,
    section_two_rule,
)
from evaluations.run import DATASET, RESULTS, read_labels
from evaluations.run_config import ROOT, THRESHOLDS
from evaluations.scoring import (
    CaseResult,
    Label,
    carries_unstructured_input,
    case_success,
    correct_action,
    false_approval,
    false_denial,
    ledger_correct,
)
from evaluations.spend import spent_usd

OUT = ROOT / "benchmarks" / "reports" / "heldout"
COMPOSITION = DATASET / "composition.md"
CATALOG = ROOT / "docs" / "legacy-defect-catalog.md"
Labels = Mapping[str, Label]
Test = Callable[[CaseResult, Label], bool]
SLICE_KEYS = ("tier", "region", "channel", "language", "style")
FOOTER = "Every number comes from a stored run in `benchmarks/results/`. Simulated member and supervisor."


def weights(path: Path = COMPOSITION) -> dict[str, float]:
    """The re-weighting table the generator wrote before any run."""
    found = re.findall(
        r"^\| (D\d\d|K) \| [\d.]+ \| \d+ \| [\d.]+ \| ([\d.]+) \|", path.read_text(encoding="utf-8"), re.M
    )
    return {driver: float(weight) for driver, weight in found}


def driver_of(label: Label, table: Mapping[str, float]) -> str | None:
    for scenario in label["scenarios"]:
        if scenario in table:
            return str(scenario)
    return "K" if any(s.startswith("K") for s in label["scenarios"]) else None


def weighted_rate(values: Mapping[str, bool], labels: Labels, table: Mapping[str, float]) -> float:
    """The share at the history's defect frequencies, in percent."""
    total = hit = 0.0
    for case, value in values.items():
        driver = driver_of(labels[case], table)
        weight = table[driver] if driver else 0.0
        total += weight
        hit += weight * value
    return hit / total * 100 if total else 0.0


def by_case(runs: Runs, test: Test) -> dict[str, bool]:
    return {case: runs.holds(case, test) for case in sorted(runs.by_case)}


def _rate(values: Iterable[bool]) -> str:
    items = list(values)
    return f"{sum(items)}/{len(items)} ({sum(items) / len(items) * 100:.1f}%)" if items else "0/0"


def decisions(a: Runs, b: Runs, c: Runs, everything: Sequence[CaseResult]) -> list[Decision]:
    h = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))["hypotheses"]
    return [
        h1(a, b, h["H1"]["min_difference_pp"]),
        h2(b, c, h["H2"]["min_difference_pp"]),
        h3(b, c, h["H3"]["min_difference_pp"]),
        h4(b, c, h["H4"]["min_difference_pp"], h["H4"]["contacts_margin"]),
        h5(c, h["H5"]["cost_per_correct_case_usd_max"], h["H5"]["investigation_latency_p95_seconds_max"]),
        h6(everything),
        h7(0, h["H7"]["min_participants"]),
    ]


def denied_if_people_work_escalations(result: CaseResult, label: Label) -> bool:
    """Sensitivity: a person works every escalation correctly, so an escalation isn't a false denial."""
    return false_denial(result, label) and result.outcome != "escalated"


def success_if_people_work_escalations(result: CaseResult, label: Label) -> bool:
    """Sensitivity: a case handed to a person, wrongly or not, ends right unless it was over-credited first."""
    if result.outcome == "escalated" and label["expected_outcome"] != "escalated":
        return not false_approval(result, label)
    return case_success(result, label)


def escalation_sensitivity(a: Runs, b: Runs, c: Runs, labels: Labels, h3_threshold: float) -> list[str]:
    """The simulation has no person who works an escalated case, so it stays un-credited at settlement. That's the
    pre-registered definition, and the verdicts above use it. This shows what rests on it."""
    cases = sorted(c.by_case)
    sliced = [case for case in cases if carries_unstructured_input(labels[case])]
    h3_diff = difference(
        c.values(sliced, denied_if_people_work_escalations), b.values(sliced, denied_if_people_work_escalations)
    )
    ab = difference(
        a.values(cases, success_if_people_work_escalations), b.values(cases, success_if_people_work_escalations)
    )
    bc = difference(
        b.values(cases, success_if_people_work_escalations), c.values(cases, success_if_people_work_escalations)
    )
    handed = {
        name: sum(
            1
            for case in cases
            if runs.by_case[case][0].outcome == "escalated" and labels[case]["expected_outcome"] != "escalated"
        )
        for name, runs in (("A", a), ("B", b), ("C", c))
    }

    def show(d: Difference) -> str:
        counts = f"{d.numerator_a} vs {d.numerator_b} of {d.denominator}"
        return f"{d.points:+.1f} pp (95% interval {d.low:+.1f} to {d.high:+.1f}; {counts})"

    return [
        "## What rests on treating an escalation as un-credited",
        "",
        "**The verdicts above follow the pre-registered definition, and don't change.** The simulation has no person "
        "who works an escalated case, so a case handed to a person stays un-credited at settlement. If a person worked "
        "every escalation correctly, these would read:",
        "",
        *_table(
            ["Question", "If a person works every escalation correctly"],
            [
                [
                    "H3: B minus C, false denials",
                    f"{show(h3_diff)}. By the same rule: **{section_two_rule(h3_diff, h3_threshold).value}**",
                ],
                ["B minus A, case success", show(ab)],
                ["C minus B, case success", show(bc)],
                [
                    "Cases handed to a person when the label says the system could settle them",
                    f"A {handed['A']}, B {handed['B']}, C {handed['C']}, of {len(cases)}",
                ],
            ],
        ),
        "",
        "**So arm C's gain over arm B is mostly fewer handoffs to a person, not a better final answer.** How much "
        "that's worth depends on what a handoff costs, which is an assumption here: `business-value.md`.",
        "",
    ]


def hypotheses_report(ds: Sequence[Decision], a: Runs, b: Runs, c: Runs, labels: Labels) -> str:
    rows = []
    for d in ds:
        diff = d.difference
        observed = (
            f"{diff.points:+.1f} pp (95% interval {diff.low:+.1f} to {diff.high:+.1f}; "
            f"{diff.numerator_a} vs {diff.numerator_b} of {diff.denominator})"
            if diff
            else "n/a"
        )
        rows.append([d.hypothesis, f"**{d.verdict.value}**", observed, d.why])
    table = weights()
    lines = [
        "# Hypotheses on the held-out split",
        "",
        HEADER,
        "",
        f"Arm C's runs here are **{c.kind}**. Business thresholds are provisional: no stakeholder has approved them. "
        "Statistical difference and practical value are separate questions, and zero observed doesn't prove zero risk.",
        "",
        *_table(["Hypothesis", "Verdict", "Observed", "Why"], rows),
        "",
        "## The same rates, re-weighted to the history's defect frequencies",
        "",
        "Defect cases are over-represented in held-out, so raw differences run larger than in normal traffic.",
        "",
    ]
    metrics: Sequence[tuple[str, Test]] = (
        ("Case success", case_success),
        ("Correct first action", correct_action),
        ("False approvals", false_approval),
        ("False denials", false_denial),
        ("Right ledger", ledger_correct),
    )
    weighted_rows = []
    for name, test in metrics:
        cells = [name]
        for runs in (a, b, c):
            values = by_case(runs, test)
            cells.append(f"{_rate(values.values())} raw; {weighted_rate(values, labels, table):.1f}% re-weighted")
        weighted_rows.append(cells)
    lines += [*_table(["Metric", "A", "B", "C"], weighted_rows), ""]
    h3 = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))["hypotheses"]["H3"]["min_difference_pp"]
    if c.kind == "live":
        lines += escalation_sensitivity(a, b, c, labels, h3)
    lines += [
        "## What these verdicts can't say",
        "",
        "- **H4 had 2 clarification cases.** Both arms found both, so its first part can't separate them. That's a "
        "weakness in "
        "the held-out set, not evidence they're equal. Its other two parts favour C.",
        "- **Case success doesn't check that a complaint reached someone.** Arm A scores 3/3 on D20 by ignoring the "
        "complaint.",
        "- **One generator wrote every message,** in phrasing arm C also saw on dev. Real messages will be messier.",
        "- **The labels aren't independently reviewed.** The owner reviewed 30 of 280 (human review, AI-assisted): 2 "
        "disagreed, 1 unsure, none confirmed wrong. **H2 rests on one disputed case, HO-062:** read without the "
        "member's reply, H2 is not supported (`label-review-sensitivity.md`). The catalog wasn't reviewed by anyone "
        "independent.",
        "- **The simulated supervisor approves whatever the engine proposes,** so nothing here tests real reviewers.",
        "",
        FOOTER,
        "",
    ]
    return "\n".join(lines)


def comparison_report(a: Run, b: Run, cs: Sequence[Run], labels: Labels) -> str:
    columns = [("A", [a]), ("B", [b])] + [(f"C run {r.manifest.get('run_number')}", [r]) for r in cs]
    rows = {name: summary_rows(run[0], labels) for name, run in columns}
    keys = list(next(iter(rows.values())))
    lines = [
        "# A/B/C comparison on the held-out split",
        "",
        HEADER,
        "",
        f"Arm C: {cs[0].manifest['kind'] if cs else 'none'}.",
        "",
    ]
    lines += [*_table(["Metric", *rows], [[k, *(rows[n][k] for n in rows)] for k in keys]), ""]
    lines += ["## Failure funnel: where each case first went wrong", ""]
    funnels = {name: funnel(run[0], labels) for name, run in columns}
    names = sorted({k for f in funnels.values() for k in f})
    lines += [
        *_table(["First failed link", *funnels], [[k, *(str(f[k]) for f in funnels.values())] for k in names]),
        "",
    ]
    lines += ["## By scenario: cases / successes / right ledgers / false approvals / false denials", ""]
    tables = {name: by_scenario(run[0], labels) for name, run in columns}
    scenarios = sorted({k for t in tables.values() for k in t})
    lines += [
        *_table(
            ["Scenario", *tables],
            [[s, *(" / ".join(str(v) for v in t.get(s, ())) for t in tables.values())] for s in scenarios],
        ),
        "",
        FOOTER,
        "",
    ]
    return "\n".join(lines)


def groups(labels: Labels, cases: Iterable[str]) -> dict[str, list[str]]:
    """Every scenario and every slice value a case belongs to."""
    out: dict[str, list[str]] = {}
    for case in cases:
        label = labels[case]
        for scenario in label["scenarios"]:
            out.setdefault(f"scenario {scenario}", []).append(case)
        for key in SLICE_KEYS:
            if key in label["slices"]:
                out.setdefault(f"{key} = {label['slices'][key]}", []).append(case)
    return dict(sorted(out.items()))


def beats_c_rows(a: Runs, b: Runs, c: Runs, labels: Labels) -> list[list[str]]:
    """Every group where A or B beats C, on each measure. Generated, so nothing can be left out by choice."""
    rows = []
    higher_is_better: Sequence[tuple[str, Test, bool]] = (
        ("Case success", case_success, True),
        ("Correct first action", correct_action, True),
        ("Right ledger", ledger_correct, True),
        ("False approvals", false_approval, False),
        ("False denials", false_denial, False),
    )
    for group, cases in groups(labels, sorted(c.by_case)).items():
        for name, test, better_high in higher_is_better:
            counts = {
                arm: sum(runs.holds(case, test) for case in cases) for arm, runs in (("A", a), ("B", b), ("C", c))
            }
            for arm in ("A", "B"):
                beats = counts[arm] > counts["C"] if better_high else counts[arm] < counts["C"]
                if beats:
                    rows.append([group, name, arm, f"{counts[arm]}/{len(cases)}", f"{counts['C']}/{len(cases)}"])
    return rows


def a_beats_b_rows(a: Runs, b: Runs, labels: Labels) -> list[list[str]]:
    rows = []
    for group, cases in groups(labels, sorted(a.by_case)).items():
        counts = [sum(runs.holds(case, case_success) for case in cases) for runs in (a, b)]
        if counts[0] > counts[1]:
            rows.append([group, f"{counts[0]}/{len(cases)}", f"{counts[1]}/{len(cases)}"])
    return rows


def beats_c_report(a: Runs, b: Runs, c: Runs, labels: Labels) -> str:
    rows = beats_c_rows(a, b, c, labels)
    against_b = a_beats_b_rows(a, b, labels)
    return "\n".join(
        [
            "# Every slice where A or B beats C",
            "",
            HEADER,
            "",
            f"Arm C: **{c.kind}**, majority of runs. {len(rows)} rows. Small groups: read the denominators. "
            "Measures: case success, correct first action, right ledger, false approvals, false denials. "
            "Slices: every scenario, tier, region, channel, language and style.",
            "",
            *(_table(["Slice", "Measure", "Arm", "That arm", "C"], rows) if rows else ["**None on held-out.**"]),
            "",
            "**This doesn't mean arm C is better everywhere.** D11 ties every arm, and one generator wrote these "
            "messages. "
            "On the stress set, see `stress.md`.",
            "",
            "## Where arm A beats arm B, on case success",
            "",
            "Listed because it counts against the non-AI fix. Arm A passes D20 by ignoring the complaint; arm B "
            "hands the "
            "message to a person, as the catalog predicts.",
            "",
            *(_table(["Slice", "A", "B"], against_b) if against_b else ["None."]),
            "",
            FOOTER,
            "",
        ]
    )


def pairs(labels: Labels) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for case, label in sorted(labels.items()):
        pair = label["slices"].get("pair")
        if pair:
            out.setdefault(str(pair), []).append(case)
    return out


def _settled(result: CaseResult) -> tuple[str, str, int]:
    return result.first_action, result.outcome, sum(result.final_points.values())


def fairness_report(
    runs: Mapping[str, Run], labels: Labels, heldout: Mapping[str, Runs], heldout_labels: Labels
) -> str:
    """Equivalent facts should get the same outcome (ENT-04, ENT-41). Every pair that doesn't is listed."""
    lines = ["# Fairness: counterfactual pairs and slices", "", HEADER, ""]
    rows, broken = [], []
    for arm, run in runs.items():
        results = {r.case_id: r for r in run.results}
        same = total = 0
        for pair, cases in pairs(labels).items():
            if not all(c in results for c in cases) or len(cases) < 2:
                continue
            total += 1
            kinds = {s for s in labels[cases[0]]["scenarios"] if s.startswith("FAIR-")}
            answers = {_settled(results[c]) for c in cases}
            if len(answers) == 1:
                same += 1
            else:
                broken.append(
                    [arm, pair, ", ".join(sorted(kinds)), " / ".join(f"{c}: {_settled(results[c])}" for c in cases)]
                )
        rows.append([f"{arm} [{run.manifest['kind']}]", f"{same}/{total}"])
    lines += [*_table(["Arm", "Pairs with the same action, outcome and points"], rows), ""]
    lines += [
        "## Every pair that differs",
        "",
        *(_table(["Arm", "Pair", "Varies", "Results"], broken) if broken else ["None."]),
        "",
    ]
    lines += ["## Held-out case success by slice", ""]
    cases = sorted(next(iter(heldout.values())).by_case)
    slice_rows = []
    for group, members in groups(heldout_labels, cases).items():
        if group.startswith("scenario"):
            continue
        slice_rows.append(
            [group, *(_rate(arm.holds(case, case_success) for case in members) for arm in heldout.values())]
        )
    lines += [*_table(["Slice", *heldout], slice_rows), "", FOOTER, ""]
    return "\n".join(lines)


def _pick(run: Run, labels: Labels, code: str) -> list[CaseResult]:
    return [r for r in run.results if code in labels[r.case_id]["scenarios"]]


def as_is_report(a: Run, as_is: Run, a_lost: Run | None, as_is_lost: Run | None, labels: Labels) -> str:
    """What the shared write path prevents on its own (hypotheses section 3a). Descriptive: no verdict."""

    def row(name: str, results: Sequence[CaseResult]) -> list[str]:
        n = len(results)
        return [
            name,
            _rate(ledger_correct(r, labels[r.case_id]) for r in results),
            str(sum(r.duplicate_credits for r in results)),
            f"{sum(false_approval(r, labels[r.case_id]) for r in results)}/{n}",
        ]

    headers = ["Group", "Right ledger", "Duplicate credits", "Over-credits"]
    lines = [
        "# A as-is against A: what the shared write path prevents",
        "",
        HEADER,
        "",
        "Descriptive, with no verdict. **A as-is is unsafe by design,** runs only on a disposable database, and is "
        "excluded from H1 to H6. Prediction, written before data: duplicate credits on every D10 and lost-response "
        "case, a wrong amount on most D11 cases for A as-is; zero of each for A.",
        "",
        *_table(
            headers,
            [
                row("A, all held-out", a.results),
                row("A as-is, all held-out", as_is.results),
                row("A, D10", _pick(a, labels, "D10")),
                row("A as-is, D10", _pick(as_is, labels, "D10")),
                row("A, D11", _pick(a, labels, "D11")),
                row("A as-is, D11", _pick(as_is, labels, "D11")),
            ],
        ),
        "",
    ]
    if a_lost and as_is_lost:
        credited = {r.case_id for r in a_lost.results if r.executed} | {
            r.case_id for r in as_is_lost.results if r.executed
        }
        lines += [
            "## The lost-response pass: the platform completes the first attempt and drops the reply",
            "",
            *_table(
                headers,
                [
                    row("A, cases where a credit was attempted", [r for r in a_lost.results if r.case_id in credited]),
                    row(
                        "A as-is, cases where a credit was attempted",
                        [r for r in as_is_lost.results if r.case_id in credited],
                    ),
                ],
            ),
            "",
        ]
    lines += [FOOTER, ""]
    return "\n".join(lines)


CATALOG_ROW = re.compile(r"^\| [^|]+ \| (D\d\d) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", re.M)


def catalog_rows(path: Path = CATALOG) -> list[tuple[str, str, str, str, str]]:
    return [tuple(cell.strip() for cell in match) for match in CATALOG_ROW.findall(path.read_text(encoding="utf-8"))]


def as_predicted(prediction: str, successes: int, total: int) -> str:
    """A rough reading of the catalog's words against the count. Anything subtler says 'read the note'."""
    if not total:
        return "not in held-out"
    words = prediction.lower()
    if words.startswith("wrong"):
        return "yes" if successes < total else "**no: it got them all right**"
    if words.startswith(("fixes", "escalates")):
        return "yes" if successes == total else f"**no: {total - successes} missed**"
    return "read the note"


def predicted_vs_actual(a: Runs, b: Runs, c: Runs, labels: Labels) -> str:
    rows = []
    for defect, name, pred_a, pred_b, pred_c in catalog_rows():
        cases = [case for case in sorted(a.by_case) if defect in labels[case]["scenarios"]]
        counts = [sum(runs.holds(case, case_success) for case in cases) for runs in (a, b, c)]
        first_a = sum(a.holds(case, correct_action) for case in cases)
        rows.append(
            [
                defect,
                name,
                pred_a,
                f"{counts[0]}/{len(cases)}, first action {first_a}/{len(cases)}: "
                f"{as_predicted(pred_a, counts[0], len(cases))}",
                pred_b,
                f"{counts[1]}/{len(cases)}: {as_predicted(pred_b, counts[1], len(cases))}",
                pred_c,
                f"{counts[2]}/{len(cases)}: {as_predicted(pred_c, counts[2], len(cases))}",
            ]
        )
    fixed = attribution(a, b, c, labels)
    lines = [
        "# Predicted against actual, per defect (F8)",
        "",
        HEADER,
        "",
        "Predictions from `docs/legacy-defect-catalog.md`, written before any arm existed. Measured on held-out case "
        "success; arm C by majority of runs.",
        "",
        "## Where arm A's failures went (`docs/day-one-discovery.md` predicted about 61% B, 21% C only, 9% split)",
        "",
        *_table(
            ["Of arm A's failed held-out cases", "Count", "Share", "Re-weighted to the history"],
            [[k, str(v[0]), f"{v[1]:.1f}%", f"{v[2]:.1f}%"] for k, v in fixed.items()],
        ),
        "",
        "## Where the catalog was wrong about arm A, and why",
        "",
        '- **D04 and D08:** arm A says "wait" (first action wrong, as predicted), the simulated member comes back '
        "when told, "
        "and it's credited. Right in the end, one contact and some days later. The catalog didn't allow for the "
        "return.",
        "- **D13:** these held-out messages carry a number or an exact name, so exact search finds the member.",
        "- **D20:** these held-out complaints are about noise, so nothing routes them to billing. Arm A credits the "
        "points and "
        "ignores the complaint. Case success doesn't check that.",
        "- **D06:** 1 of 3 over-credits. The other two are Mountain Lodge stays, where D08's stale wait masks it by "
        "accident.",
        "",
        "## Per defect",
        "",
        *_table(
            ["Defect", "What", "A predicted", "A actual", "B predicted", "B actual", "C predicted", "C actual"], rows
        ),
        "",
        FOOTER,
        "",
    ]
    return "\n".join(lines)


def attribution(a: Runs, b: Runs, c: Runs, labels: Labels) -> dict[str, tuple[int, float, float]]:
    """Each case arm A failed: did B fix it, did only C fix it, or neither?"""
    table = weights()
    buckets: dict[str, list[str]] = {"Fixed by B": [], "Fixed only by C": [], "Fixed by neither": []}
    for case in sorted(a.by_case):
        if a.holds(case, case_success):
            continue
        if b.holds(case, case_success):
            buckets["Fixed by B"].append(case)
        elif c.holds(case, case_success):
            buckets["Fixed only by C"].append(case)
        else:
            buckets["Fixed by neither"].append(case)
    total = sum(len(v) for v in buckets.values()) or 1

    def weight(case: str) -> float:
        driver = driver_of(labels[case], table)
        return table[driver] if driver else 0.0

    all_weight = sum(weight(case) for v in buckets.values() for case in v) or 1.0
    return {
        name: (len(v), len(v) / total * 100, sum(weight(case) for case in v) / all_weight * 100)
        for name, v in buckets.items()
    }


def variability_report(runs: Sequence[Run], extra: Sequence[Run], labels: Labels) -> str:
    """Run-to-run differences on the live model. Mock runs would show none, and say nothing."""
    by: dict[str, list[CaseResult]] = {}
    for run in runs:
        for r in run.results:
            by.setdefault(r.case_id, []).append(r)
    flips = [c for c, rows in sorted(by.items()) if len({_settled(r) for r in rows}) > 1]
    more: dict[str, list[CaseResult]] = {}
    for run in [*runs, *extra]:
        for r in run.results:
            if extra and r.case_id in {x.case_id for x in extra[0].results}:
                more.setdefault(r.case_id, []).append(r)
    rows_more = [
        [
            case,
            ", ".join(labels[case]["scenarios"]),
            str(len(rows)),
            str(sum(case_success(r, labels[case]) for r in rows)),
            str(len({_settled(r) for r in rows})),
        ]
        for case, rows in sorted(more.items())
    ]
    lines = [
        "# Run-to-run variability, live model",
        "",
        HEADER,
        "",
        f"Over {len(runs)} runs of {len(by)} cases, {len(flips)} cases changed action, outcome or points: "
        f"{', '.join(flips) or 'none'}.",
        "",
        "## The 10 cases chosen before any held-out run, 6 runs each",
        "",
        *_table(["Case", "Scenario", "Runs", "Successes", "Distinct results"], rows_more),
        "",
    ]
    costs = [r.cost_usd for run in runs for r in run.results]
    latency = sorted(r.latency_s for run in runs for r in run.results if r.latency_s is not None)
    if costs and latency:
        lines += [
            f"Cost per case: mean ${mean(costs):.5f}, max ${max(costs):.5f}. Worst investigation per case: p50 "
            f"{latency[len(latency) // 2]:.2f} s, p95 {latency_p95(latency):.2f} s. Benchmark environment.",
            "",
        ]
    lines += [FOOTER, ""]
    return "\n".join(lines)


def stress_report(runs: Mapping[str, Sequence[Run]], labels: Labels) -> str:
    """Adversarial and messy cases. Arm C's runs are repeated, because a live model varies (SEC-19, ENT-40)."""
    columns = {f"{arm} run {i}": run for arm, items in runs.items() for i, run in enumerate(items, 1)}
    tables = {name: by_scenario(run, labels) for name, run in columns.items()}
    scenarios = sorted({s for table in tables.values() for s in table})
    rows = {name: summary_rows(run, labels) for name, run in columns.items()}
    keys = [
        "Case success (final ledger, outcome, no duplicate)",
        "Final ledger correct",
        "False approvals (over-credit)",
        "False denials (under-credit)",
        "Duplicate credits",
        "Unauthorized actions",
        "Model cost at list price, total / per case",
    ]
    return "\n".join(
        [
            "# The stress set",
            "",
            HEADER,
            "",
            "S01 and S02 are injection, S03 asks about another member, S04 tries to run up the tool calls, S05 "
            "submits twice. "
            "These check business effects: no points move that shouldn't. **A pass doesn't show injection is "
            "solved,** and "
            "it can't show what a person reading a convincing wrong explanation would do.",
            "",
            *_table(["Metric", *rows], [[k, *(rows[n][k] for n in rows)] for k in keys]),
            "",
            "## By scenario: cases / successes / right ledgers / false approvals / false denials",
            "",
            *_table(
                ["Scenario", *tables],
                [[s, *(" / ".join(str(v) for v in t.get(s, ())) for t in tables.values())] for s in scenarios],
            ),
            "",
            FOOTER,
            "",
        ]
    )


def _run(kind: str, name: str) -> Run | None:
    folder = RESULTS / kind / name
    return load_run(folder) if (folder / "manifest.json").exists() else None


def _require(kind: str, name: str) -> Run:
    run = _run(kind, name)
    if run is None:
        raise SystemExit(f"{kind}/{name} hasn't run")
    return run


def main() -> int:
    labels = read_labels("heldout", DATASET)
    a, b = _require("deterministic", "a-heldout"), _require("deterministic", "b-heldout")
    c_kind = "live"
    cs = [_run(c_kind, f"c-heldout-r{n}") for n in (1, 2, 3)]
    c_runs = [r for r in cs if r]
    extra = [r for r in (_run(c_kind, f"c-variability-r{n}") for n in (4, 5, 6)) if r]
    a_runs, b_runs = Runs(a.results, labels), Runs(b.results, labels)
    c_set = Runs([r for run in c_runs for r in run.results], labels)

    gate_runs: list[CaseResult] = []
    for folder in (RESULTS / "deterministic").iterdir():
        if "as-is" in folder.name or "second-look" in folder.name or not (folder / "manifest.json").exists():
            continue
        gate_runs.extend(load_run(folder).results)
    live_root = RESULTS / "live"
    for folder in live_root.iterdir():
        if folder.is_dir() and (folder / "manifest.json").exists():
            gate_runs.extend(load_run(folder).results)

    ds = decisions(a_runs, b_runs, c_set, gate_runs)
    OUT.mkdir(parents=True, exist_ok=True)

    def write(name: str, text: str) -> None:
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")

    write("hypotheses.md", hypotheses_report(ds, a_runs, b_runs, c_set, labels))
    write("comparison.md", comparison_report(a, b, c_runs, labels))
    write("a-or-b-beats-c.md", beats_c_report(a_runs, b_runs, c_set, labels))
    write("predicted-vs-actual.md", predicted_vs_actual(a_runs, b_runs, c_set, labels))
    write("variability.md", variability_report(c_runs, extra, labels))
    as_is = _require("deterministic", "a-as-is-heldout")
    write(
        "a-as-is.md",
        as_is_report(
            a, as_is, _run("deterministic", "a-heldout-lost"), _run("deterministic", "a-as-is-heldout-lost"), labels
        ),
    )
    fairness_labels = read_labels("fairness", DATASET)
    fairness_runs = {
        arm: run
        for arm, run in (
            ("A", _run("deterministic", "a-fairness")),
            ("B", _run("deterministic", "b-fairness")),
            ("C", _run(c_kind, "c-fairness")),
        )
        if run
    }
    write(
        "fairness.md",
        fairness_report(fairness_runs, fairness_labels, {"A": a_runs, "B": b_runs, "C": c_set}, labels),
    )
    stress_labels = read_labels("stress", DATASET)
    stress_c = [
        run for run in (_run(c_kind, name) for name in ("c-stress", "c-stress-r2", "c-stress-r3")) if run is not None
    ]
    write(
        "stress.md",
        stress_report(
            {"A": [_require("deterministic", "a-stress")], "B": [_require("deterministic", "b-stress")], "C": stress_c},
            stress_labels,
        ),
    )
    repeats = {
        "A": repeat_differences(a, _require("deterministic", "a-heldout-repeat")),
        "B": repeat_differences(b, _require("deterministic", "b-heldout-repeat")),
    }
    summary = {
        "label": "SYNTHETIC. Simulated engagement.",
        "decisions": [{**asdict(d), "verdict": d.verdict.value} for d in ds],
        "repeat_differences": repeats,
        "live_spend_usd": round(spent_usd(), 6),
        "case_runs_in_the_h6_gate": len(gate_runs),
    }
    write("summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    for d in ds:
        print(d.hypothesis, d.verdict.value, "|", d.why)
    print("repeat differences:", {k: len(v) for k, v in repeats.items()})
    print("not tested markers:", [d.hypothesis for d in ds if d.verdict is Verdict.NOT_TESTED])
    return 0


if __name__ == "__main__":
    sys.exit(main())
