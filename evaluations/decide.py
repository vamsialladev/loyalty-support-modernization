"""From scored cases to verdicts: the pre-registered rules, applied by code (docs/hypotheses.md sections 2 and 3).

Mock results never decide H2 to H5. Without live runs those hypotheses are **not tested (NOT RUN)**, whatever a mock
says (spec E.5). Statistical difference and practical value are reported separately. No other significance claims.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import mean

from evaluations.scoring import (
    CaseResult,
    Label,
    carries_unstructured_input,
    case_success,
    clarification_found,
    correct_action,
    false_approval,
    false_denial,
    unnecessary_request,
)

RESAMPLES = 10_000
SEED = 9
INTERVAL = 95
C_RUNS_NEEDED = 2  # a case counts for C when it holds in at least 2 of 3 live runs


CaseTest = Callable[[CaseResult, Label], bool]


class Verdict(StrEnum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not supported"
    INCONCLUSIVE = "inconclusive"
    NOT_TESTED = "not tested (NOT RUN)"


@dataclass(frozen=True)
class Difference:
    """A paired difference in percentage points, with its interval and its counts."""

    points: float
    low: float
    high: float
    numerator_a: int
    numerator_b: int
    denominator: int


@dataclass(frozen=True)
class Decision:
    hypothesis: str
    verdict: Verdict
    why: str
    difference: Difference | None = None


def paired_interval(
    a: Sequence[float], b: Sequence[float], resamples: int = RESAMPLES, seed: int = SEED
) -> tuple[float, float]:
    """95% percentile interval, by paired bootstrap over cases, for mean(b) - mean(a), in percentage points."""
    if len(a) != len(b):
        raise ValueError("a paired comparison needs the same cases on both sides")
    if not a:
        raise ValueError("no cases to compare")
    rng = random.Random(seed)  # noqa: S311 - a fixed, pre-registered seed for an interval; not security
    pairs = [y - x for x, y in zip(a, b, strict=True)]
    size = len(pairs)
    means = sorted(sum(rng.choices(pairs, k=size)) / size * 100 for _ in range(resamples))
    tail = (100 - INTERVAL) / 200
    return means[int(tail * resamples)], means[min(int((1 - tail) * resamples), resamples - 1)]


def difference(a: Sequence[bool], b: Sequence[bool]) -> Difference:
    """b minus a, over the same cases."""
    x, y = [float(v) for v in a], [float(v) for v in b]
    low, high = paired_interval(x, y)
    return Difference((mean(y) - mean(x)) * 100, low, high, sum(a), sum(b), len(a))


def section_two_rule(observed: Difference, threshold: float) -> Verdict:
    """Supported, not supported or inconclusive (docs/hypotheses.md section 2)."""
    if observed.points >= threshold and observed.low > 0:
        return Verdict.SUPPORTED
    if observed.high < threshold or observed.points <= 0:
        return Verdict.NOT_SUPPORTED
    return Verdict.INCONCLUSIVE


class Runs:
    """One arm's scored results on the decision split, by case and run."""

    def __init__(self, results: Sequence[CaseResult], labels: Mapping[str, Label]) -> None:
        self.results, self.labels = results, labels
        kinds = {r.kind for r in results}
        if len(kinds) > 1:
            raise ValueError(f"mock and live results can't be mixed: {sorted(kinds)}")
        self.kind = kinds.pop() if kinds else "none"
        self.run_ids = sorted({r.run for r in results})
        self.by_case: dict[str, list[CaseResult]] = {}
        for result in results:
            self.by_case.setdefault(result.case_id, []).append(result)

    @property
    def complete(self) -> bool:
        return bool(self.results) and not any(r.interrupted for r in self.results)

    def holds(self, case_id: str, test: CaseTest) -> bool:
        """A deterministic arm's single answer; for several runs, whether it holds in enough of them."""
        rows = self.by_case[case_id]
        hits = sum(1 for r in rows if test(r, self.labels[case_id]))
        return hits >= (C_RUNS_NEEDED if len(rows) >= C_RUNS_NEEDED else 1)

    def values(self, case_ids: Sequence[str], test: CaseTest) -> list[bool]:
        return [self.holds(case, test) for case in case_ids]

    def mean_count_per_run(self, test: CaseTest) -> float:
        per_run = [
            sum(1 for r in self.results if r.run == run and test(r, self.labels[r.case_id])) for run in self.run_ids
        ]
        return mean(per_run) if per_run else 0.0


def _live_problem(c: Runs) -> str | None:
    if c.kind != "live":
        return f"arm C has only {c.kind} results; mock results never decide this"
    if not c.complete:
        return "the live runs were interrupted; an interrupted run is never extrapolated"
    return None


def _common_cases(a: Runs, b: Runs) -> list[str]:
    if set(a.by_case) != set(b.by_case):
        raise ValueError("the arms didn't run the same cases, so this isn't a paired comparison")
    return sorted(a.by_case)


def h1(a: Runs, b: Runs, threshold: float) -> Decision:
    cases = _common_cases(a, b)
    observed = difference(a.values(cases, case_success), b.values(cases, case_success))
    return Decision("H1", section_two_rule(observed, threshold), "B minus A on case success", observed)


def h2(b: Runs, c: Runs, threshold: float) -> Decision:
    problem = _live_problem(c)
    if problem:
        return Decision("H2", Verdict.NOT_TESTED, problem)
    cases = _common_cases(b, c)
    observed = difference(b.values(cases, correct_action), c.values(cases, correct_action))
    more_false_approvals = c.mean_count_per_run(false_approval) > b.mean_count_per_run(false_approval)
    if more_false_approvals:
        return Decision("H2", Verdict.NOT_SUPPORTED, "C has more false approvals than B", observed)
    if sum(c.values(cases, case_success)) < sum(b.values(cases, case_success)):
        return Decision("H2", Verdict.NOT_SUPPORTED, "C's case success is below B's", observed)
    return Decision("H2", section_two_rule(observed, threshold), "C minus B on correct action", observed)


def h3(b: Runs, c: Runs, threshold: float) -> Decision:
    problem = _live_problem(c)
    if problem:
        return Decision("H3", Verdict.NOT_TESTED, problem)
    cases = [case for case in _common_cases(b, c) if carries_unstructured_input(c.labels[case])]
    if not cases:
        return Decision("H3", Verdict.NOT_TESTED, "no held-out case in the slice")
    observed = difference(c.values(cases, false_denial), b.values(cases, false_denial))  # B minus C
    return Decision("H3", section_two_rule(observed, threshold), "B minus C on false denials", observed)


def h4(b: Runs, c: Runs, threshold: float, contacts_margin: float) -> Decision:
    problem = _live_problem(c)
    if problem:
        return Decision("H4", Verdict.NOT_TESTED, problem)
    cases = _common_cases(b, c)
    needing = [case for case in cases if clarification_found(b.by_case[case][0], b.labels[case]) is not None]
    if not needing:
        return Decision("H4", Verdict.NOT_TESTED, "no held-out case needs clarification")

    def found(result: CaseResult, label: Label) -> bool:
        return bool(clarification_found(result, label))

    observed = difference(b.values(needing, found), c.values(needing, found))
    part_a = section_two_rule(observed, threshold)
    part_b = c.mean_count_per_run(unnecessary_request) <= b.mean_count_per_run(unnecessary_request)
    contacts_b = mean(r.contacts for r in b.results)
    contacts_c = mean(r.contacts for r in c.results)
    part_c = contacts_c <= contacts_b - contacts_margin
    why = f"(a) {part_a}; (b) {'holds' if part_b else 'fails'}; (c) {'holds' if part_c else 'fails'}"
    if part_a is Verdict.SUPPORTED and part_b and part_c:
        return Decision("H4", Verdict.SUPPORTED, why, observed)
    if part_a is Verdict.NOT_SUPPORTED or not part_b or not part_c:
        return Decision("H4", Verdict.NOT_SUPPORTED, why, observed)
    return Decision("H4", Verdict.INCONCLUSIVE, why, observed)


def latency_p95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[min(int(0.95 * len(ordered)), len(ordered) - 1)]


def h5(c: Runs, max_cost: float, max_latency: float) -> Decision:
    problem = _live_problem(c)
    if problem:
        return Decision("H5", Verdict.NOT_TESTED, problem)
    correct = sum(1 for r in c.results if case_success(r, c.labels[r.case_id]))
    if not correct:
        return Decision("H5", Verdict.NOT_SUPPORTED, "no case was correctly resolved")
    cost = sum(r.cost_usd for r in c.results) / correct
    latencies = [r.latency_s for r in c.results if r.latency_s is not None]
    if not latencies:
        return Decision("H5", Verdict.NOT_TESTED, "no latency was recorded")
    p95 = latency_p95(latencies)
    verdict = Verdict.SUPPORTED if cost <= max_cost and p95 <= max_latency else Verdict.NOT_SUPPORTED
    return Decision("H5", verdict, f"${cost:.5f} per correct case; p95 {p95:.2f} s, over {correct} correct cases")


def h6(all_runs: Sequence[CaseResult]) -> Decision:
    """A hard gate. Zero observed doesn't prove zero risk."""
    if not all_runs:
        return Decision("H6", Verdict.NOT_TESTED, "nothing has run")
    unauthorized = sum(r.unauthorized_actions for r in all_runs)
    duplicates = sum(r.duplicate_credits for r in all_runs)
    held = unauthorized == 0 and duplicates == 0
    return Decision(
        "H6",
        Verdict.SUPPORTED if held else Verdict.NOT_SUPPORTED,
        f"{unauthorized} unauthorized, {duplicates} duplicates, over {len(all_runs)} case runs",
    )


def h7(participants: int, min_participants: int) -> Decision:
    """Only real participants count. Scripted timing never does."""
    if participants == 0:
        return Decision("H7", Verdict.NOT_TESTED, "no real participants")
    if participants < min_participants:
        return Decision("H7", Verdict.INCONCLUSIVE, f"{participants} participants: descriptive only")
    raise NotImplementedError("Milestone 18 measures this with real participants")
