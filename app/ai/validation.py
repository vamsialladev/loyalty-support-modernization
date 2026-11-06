"""The final check on what a model hands back (spec B.9; AI-14, AI-16, AI-17, ELIG-02, POL-06). Pure.

The model's text can be wrong in ways code can't see, and a person reviews it. What code can check, it checks: the
action matches the engine, citations were really retrieved, no stay was invented, no amount or percentage was made
up, and missing things are disclosed. Self-review isn't proof, so nothing here asks the model whether it's right.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from app.ai.tools import Proposal
from app.domain.eligibility import EligibilityResult, NextAction, combine

_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%|\bpercent\b|\bconfidence\b", re.IGNORECASE)
_POINTS = re.compile(r"(\d[\d,. ]*\d|\d)\s*(?:points?|puntos|pontos|punkte)\b", re.IGNORECASE)
NO_STAY_ACTIONS = (NextAction.REQUEST_INFO.value, NextAction.ESCALATE.value)


def stated_points(text: str) -> set[int]:
    return {int(re.sub(r"[,. ]", "", m)) for m in _POINTS.findall(text)}


def problems_with(
    proposal: Proposal,
    *,
    member_stays: set[str],
    evaluated: Mapping[str, EligibilityResult],
    retrieved: set[str],
) -> list[str]:
    """What's wrong, in words the model can act on for its one repair. Empty means it passes."""
    problems = []
    unknown = sorted(set(proposal.stay_ids) - member_stays)
    if unknown:
        problems.append(f"unknown_stay: {', '.join(unknown)} didn't come from get_stay")
    known = [s for s in proposal.stay_ids if s in member_stays]
    missing_results = [s for s in known if s not in evaluated]
    if missing_results:
        problems.append(f"not_evaluated: call evaluate_eligibility for {', '.join(missing_results)}")
    results = [evaluated[s] for s in known if s in evaluated]
    allowed_points: set[int] = set()
    if results:
        verdict = combine(results)
        allowed_points = {r.points_owed for r in results} | {r.earned_points for r in results}
        allowed_points |= {r.credited_points for r in results} | {verdict.points_owed}
        if proposal.recommended_action != verdict.action.value:
            problems.append(f"action_mismatch: the engine's action is {verdict.action.value}")
    elif not known and proposal.recommended_action not in NO_STAY_ACTIONS:
        problems.append("action_without_stay: with no stay identified, use request_info or escalate")
    for citation in proposal.citations:
        ref = f"{citation.policy_id}@{citation.version}#{citation.section_id}"
        if ref not in retrieved:
            problems.append(f"unsupported_citation: {ref} wasn't returned by a tool in this run")
    if proposal.recommended_action == NextAction.REQUEST_INFO.value and not proposal.missing_information:
        problems.append("missing_information: say what's needed")
    if proposal.recommended_action == NextAction.ESCALATE.value and not (proposal.escalation_reason or "").strip():
        problems.append("escalation_reason: say why")
    if not proposal.summary.strip():
        problems.append("summary: required")
    written = " ".join((proposal.summary, proposal.explanation, proposal.draft_reply, *proposal.observed_facts))
    if _PERCENT.search(written):
        problems.append("confidence: remove percentages and confidence wording")
    invented = sorted(stated_points(written) - allowed_points)
    if invented:
        problems.append(f"amount_not_from_engine: {invented}; only state numbers the engine gave you")
    if proposal.recommended_action != NextAction.ADJUST.value and re.search(
        r"\b(?:we (?:will|have)|you will (?:receive|get)) .{0,30}\bpoints?\b", proposal.draft_reply, re.IGNORECASE
    ):
        problems.append("unsupported_promise: the draft promises points the engine doesn't allow")
    return problems
