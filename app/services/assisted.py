"""Arm C: arm B, plus a model that reads what rules can't (spec B.8; ARMC-01, AI-06, ELIG-02; RFC-0002).

Arm B's investigation always runs first and stays the fallback. If the model finishes with a valid reading, this
service acts on the only three things it may influence, each checked by code: which of the member's real stays the
message means, that a person needn't read a multi-issue or non-English message first, and the text shown to staff.
Then the engine reads again.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.mock_model import MOCK_MODEL_ID
from app.ai.config import ai_config
from app.ai.context import ContextInput, build
from app.ai.harness import AiRuntime, SpendCaps, add_spend, remaining_microusd, run_loop
from app.ai.loop import ACCEPTED, LoopResult
from app.ai.tools import Proposal, ToolContext
from app.arms.conventional.extraction import document_text
from app.arms.conventional.investigation import member_stays
from app.clock import utc_now
from app.domain.case_states import CaseState
from app.domain.roles import Identity
from app.persistence.models import AiRun, Case, CaseEvidence, CaseNote, Recommendation
from app.ports.customer_systems import CustomerSystems
from app.ports.model_provider import ProviderRejected, ProviderUnavailable
from app.services import conventional, jobs, policies
from app.services.cases import CaseNotFound, read_time, requests_of
from app.services.customer_config import customer_config
from app.services.instrumentation import record
from app.settings import AppSettings

log = logging.getLogger(__name__)
SCOPE_GATES = ("multi_issue", "non_english")


def mock_runtime() -> AiRuntime:
    from app.adapters.mock_model import RulesMockModel

    return AiRuntime(RulesMockModel())


def runtime_from_settings(settings: AppSettings) -> AiRuntime:
    """Live only when it's asked for and set up. Anything half-set falls back to arm B's result rather than failing."""
    caps = SpendCaps(settings.ai_budget_per_run_usd, settings.ai_budget_daily_usd, settings.ai_budget_total_usd)
    if settings.ai_provider == "mock":
        return AiRuntime(mock_runtime().provider, caps)
    if settings.ai_provider != "anthropic":
        return AiRuntime(None, caps, f"provider {settings.ai_provider} isn't implemented")
    if not settings.feature_live_ai:
        return AiRuntime(None, caps, "FEATURE_LIVE_AI is off")
    if not settings.anthropic_model or not os.environ.get("ANTHROPIC_API_KEY"):
        return AiRuntime(None, caps, "the model or the key isn't set")
    from app.adapters.anthropic_model import AnthropicModel
    from app.adapters.circuit import GuardedModel, breaker_for

    model = GuardedModel(AnthropicModel(settings.anthropic_model), breaker_for("model:anthropic"))  # ADR-0081
    return AiRuntime(model, caps)  # GuardedModel has the provider's interface


def mode_label(settings: AppSettings) -> str:
    """For the banner. The web process has no key, by design: only the worker calls the model."""
    if settings.ai_provider == "mock":
        return f"MOCK {MOCK_MODEL_ID}"
    if settings.ai_provider == "anthropic" and settings.feature_live_ai and settings.anthropic_model:
        return f"LIVE {settings.anthropic_model}"
    return "unavailable, showing the rules result"


def _tool_context(s: Session, who: Identity, case: Case, systems: CustomerSystems, rec: Recommendation) -> ToolContext:
    """Only what this case may reach, decided by code before the model is involved (POL-07)."""
    member = systems.get_member(rec.member_number) if rec.member_number else None
    stays = member_stays(systems, member) if member else ()

    def search(query: str, day: date) -> list[Any]:
        return conventional.search_policy(s, case.customer_id, query, day)

    return ToolContext(
        who=who,
        systems=systems,
        member=member,
        stays=stays,
        received_at_utc=case.received_at_utc,
        as_of_utc=read_time(case),
        stated_channel=conventional.member_answers(s, case).get("booking_channel"),
        customer=customer_config(case.customer_id).rules,
        policies=policies.published_versions(s, case.customer_id),
        search=search,
        result_chars=ai_config(case.customer_id).limits.tool_result_chars,
    )


def tool_context_for(s: Session, who: Identity, case: Case, systems: CustomerSystems) -> ToolContext:
    """The same reach arm C's model gets for this case, for another reader of the same tools (the MCP server, M11).
    Without an investigation yet, there is no confirmed member, and the tools say so."""
    rec = conventional.latest_recommendation(s, case)
    if rec is None:
        rec = Recommendation(member_number=None)
    return _tool_context(s, who, case, systems, rec)


def _ai_text(proposal: Proposal) -> dict[str, Any]:
    return {
        "summary": proposal.summary,
        "observed_facts": proposal.observed_facts,
        "explanation": proposal.explanation,
        "missing_information": proposal.missing_information,
        "draft_reply": proposal.draft_reply,
        "out_of_scope_items": proposal.out_of_scope_items,
        "request_language": proposal.request_language,
        "citations": [asdict_citation(c) for c in proposal.citations],
        "escalation_reason": proposal.escalation_reason,
        "recommended_action": proposal.recommended_action,
    }


def asdict_citation(citation: Any) -> dict[str, Any]:
    return dict(citation.model_dump())


def _apply_reading(s: Session, who: Identity, case: Case, rec: Recommendation, proposal: Proposal) -> bool:
    """Returns whether the engine must read again. Every stay here already passed `problems_with`, so it's really this
    member's. The engine, the identity rule and the approval all still apply."""
    changed = False
    chosen = list(dict.fromkeys(proposal.stay_ids))
    if chosen and conventional.claimed_stay(s, case) is None and (rec.stay_id != chosen[0] or len(chosen) > 1):
        first, others = chosen[0], tuple(chosen[1:])
        if others:
            conventional.split_group(s, who, case, first, others)
        else:
            conventional.claim_stay(s, who, case, first)
        changed = True
    if rec.detail in SCOPE_GATES and chosen:
        s.add(
            CaseEvidence(
                case_id=case.id,
                kind=conventional.ANSWER_EVIDENCE,
                source_ref="ai",
                snapshot={"scope_cleared": True},
                attached_by=who.username,
                attached_at_utc=utc_now(),
                sim_time_utc=case.received_at_utc,
            )
        )
        changed = True
    if proposal.out_of_scope_items:
        items = "; ".join(proposal.out_of_scope_items)
        body = f"For a person: the message also raises something outside points (AI-read): {items}"
        s.add(CaseNote(case_id=case.id, author=jobs.SYSTEM.username, body=body[:2000], created_at_utc=utc_now()))
        record(s, case, jobs.SYSTEM, "out_of_scope_routed", items=len(proposal.out_of_scope_items))
    s.commit()
    return changed


def _store(s: Session, case: Case, run: AiRun | None, result: LoopResult) -> Recommendation:
    rec = conventional.latest_recommendation(s, case)
    assert rec is not None
    rec.ai_run_id = run.id if run else None
    if result.proposal is not None and result.stop in ACCEPTED:
        rec.ai = _ai_text(result.proposal) | {"mock": run.is_mock if run else True}
        rec.flags = [*rec.flags, "ai_read"]
    else:
        reason = run.stop_reason if run else result.problems[0]
        rec.ai = {"fallback": reason, "mock": run.is_mock if run else True}
        rec.flags = [*rec.flags, "ai_fallback"]
    s.commit()
    return rec


def _read_images(
    s: Session, who: Identity, case: Case, systems: CustomerSystems, runtime: AiRuntime, rec: Recommendation
) -> Recommendation:
    """D22's noisy photos. A number read from an image only counts if it's one of this member's own stays, which is the
    check against the record (Appendix H). Anything else is noted for a person, and the case goes on without it."""
    provider = runtime.provider
    images = [a for a in conventional.attachments_of(s, case) if a.media_type.startswith("image/")]
    if provider is None or not images or rec.stay_id is not None or rec.member_number is None:
        return rec
    if not provider.is_mock and remaining_microusd(s, runtime.caps) <= 0:
        return rec
    member = systems.get_member(rec.member_number)
    own = {r.stay_id for r in member_stays(systems, member)}
    price = ai_config(case.customer_id).models.get(provider.model_id)
    timeout = ai_config(case.customer_id).limits.call_timeout_seconds
    for image in images:
        try:
            fields, usage = provider.read_image(image.media_type, image.content, timeout)
        except (ProviderUnavailable, ProviderRejected) as exc:
            record(s, case, jobs.SYSTEM, "document_read", method="vision", result=type(exc).__name__)
            s.commit()
            return rec
        if not provider.is_mock and price is not None:
            add_spend(s, price.cost_microusd(usage.input_tokens, usage.output_tokens))
        found = fields.get("confirmation")
        matched = found in own
        record(s, case, jobs.SYSTEM, "document_read", method="vision", result="matched" if matched else "no_match")
        s.commit()
        if matched and found:
            conventional.claim_stay(s, who, case, found)
            s.commit()
            return conventional.investigate_case(s, jobs.SYSTEM, case, systems)
    return rec


def investigate_case(
    s: Session, who: Identity, case: Case, systems: CustomerSystems, runtime: AiRuntime
) -> Recommendation:
    rec = conventional.investigate_case(s, jobs.SYSTEM, case, systems)
    if case.group_ref and case.group_ref != case.reference:
        return rec  # a linked case: the model already read this message on the first one
    rec = _read_images(s, who, case, systems, runtime, rec)
    requests = [r.text for r in requests_of(s, case)]
    ctx = _tool_context(s, who, case, systems, rec)
    papers = tuple(document_text(a.filename, a.content) for a in conventional.attachments_of(s, case))
    opening = build(
        ContextInput(
            tuple(requests),
            rec.action,
            rec.detail,
            rec.stay_id,
            tuple(rec.flags),
            rec.member_number is not None,
            read_time(case),
            documents=tuple(p for p in papers if p),
        ),
        ai_config(case.customer_id).limits.context_chars,
    )
    versions = [str(p.ref()) for p in ctx.policies]
    run, result = run_loop(s, who, case, runtime, ctx, opening, versions)
    s.refresh(case)
    if CaseState(case.status) is not CaseState.INVESTIGATING:
        return rec  # the case moved on during the run: the text is no longer about what's on the page
    accepted = result.proposal is not None and result.stop in ACCEPTED
    if accepted and _apply_reading(s, who, case, rec, result.proposal):  # type: ignore[arg-type]
        conventional.investigate_case(s, jobs.SYSTEM, case, systems)
    return _store(s, case, run, result)


def run_investigation_job(
    s: Session, case_id: int, who: Identity, systems: CustomerSystems, runtime: AiRuntime
) -> None:
    case = s.get(Case, case_id)
    if case is None:
        raise CaseNotFound(case_id)
    if CaseState(case.status) is CaseState.INVESTIGATING:
        investigate_case(s, who, case, systems, runtime)
