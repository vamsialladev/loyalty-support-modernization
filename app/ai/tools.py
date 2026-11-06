"""The model's read-only tools (spec B.9; AI-04, AI-05, AI-07; POL-07, ENT-23).

Narrow on purpose. Each runs as the person who asked, with validated arguments, bounded output and structured errors.
None can be pointed at an arbitrary record: they only reach the case's confirmed member and that member's stays, and
anything else comes back as `not_found`, the same as a stay that doesn't exist. There's no tool that writes, and a
test walks this registry.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.arms.conventional.investigation import read_claim
from app.domain.business_time import business_date
from app.domain.customer_records import Member, StayRecord
from app.domain.eligibility import CustomerRules, EligibilityResult, NextAction, evaluate_stay
from app.domain.policy import PolicyRef, PolicyVersion
from app.domain.roles import Identity, NotPermitted, require_case_reader
from app.ports.customer_systems import CustomerSystemError, CustomerSystems, RecordNotFound
from app.ports.model_provider import ToolSpec

SUBMIT = "submit_recommendation"
MAX_LEDGER_ENTRIES = 50
MAX_EXCERPT_CHARS = 700
PolicySearch = Callable[[str, date], list[Any]]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetMemberArgs(_Strict):
    pass


class GetStayArgs(_Strict):
    stay_id: str | None = None


class StayArgs(_Strict):
    stay_id: str


class SearchPolicyArgs(_Strict):
    query: str
    stay_id: str


class CitationRef(_Strict):
    policy_id: str
    version: int
    section_id: str


class Proposal(_Strict):
    """What the model hands back. There's no amount field, and no way to name an approval, a role or a status."""

    summary: str
    observed_facts: list[str]
    stay_ids: list[str]
    recommended_action: Literal[
        "adjust",
        "no_adjustment_credited",
        "no_adjustment_pending",
        "wait_until",
        "not_checked_out",
        "deny",
        "request_info",
        "refresh_evidence",
        "escalate",
    ]
    escalation_reason: str | None
    missing_information: list[str]
    citations: list[CitationRef]
    explanation: str
    draft_reply: str
    out_of_scope_items: list[str]
    request_language: str | None


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


_TEXT = {"type": "string"}
_TEXTS = {"type": "array", "items": _TEXT}
_ACTIONS = list(Proposal.model_fields["recommended_action"].annotation.__args__)  # type: ignore[union-attr]

TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec("get_member", "The member this case is about, once their identity is confirmed.", _schema({})),
    ToolSpec(
        "get_stay",
        "This member's stays as a list, or one stay by its ID. Stays on any other profile come back as not found.",
        _schema({"stay_id": {"type": ["string", "null"]}}),
    ),
    ToolSpec("get_points_ledger", "Ledger entries for one of this member's stays.", _schema({"stay_id": _TEXT})),
    ToolSpec(
        "search_policy",
        "Search the policy version in force on this stay's checkout date. Returns short excerpts you can cite.",
        _schema({"query": _TEXT, "stay_id": _TEXT}),
    ),
    ToolSpec(
        "evaluate_eligibility",
        "Run the rules engine for one of this member's stays. Its result is final, including the number of points.",
        _schema({"stay_id": _TEXT}),
    ),
    ToolSpec(
        SUBMIT,
        "End the run with your reading of the case. A person reviews it, and the engine's result stands.",
        _schema(
            {
                "summary": _TEXT,
                "observed_facts": _TEXTS,
                "stay_ids": _TEXTS,
                "recommended_action": {"type": "string", "enum": _ACTIONS},
                "escalation_reason": {"type": ["string", "null"]},
                "missing_information": _TEXTS,
                "citations": {
                    "type": "array",
                    "items": _schema(
                        {"policy_id": _TEXT, "version": {"type": "integer"}, "section_id": _TEXT},
                    ),
                },
                "explanation": _TEXT,
                "draft_reply": _TEXT,
                "out_of_scope_items": _TEXTS,
                "request_language": {"type": ["string", "null"]},
            }
        ),
    ),
)
READ_TOOLS = ("get_member", "get_stay", "get_points_ledger", "search_policy", "evaluate_eligibility")
ALLOWLIST = frozenset((*READ_TOOLS, SUBMIT))
# These only touch the customer systems and the loaded policies, so they can run side by side. search_policy uses the
# database session, which isn't safe to share, so it runs alone.
PARALLEL_SAFE = frozenset({"get_member", "get_stay", "get_points_ledger", "evaluate_eligibility"})


@dataclass
class ToolContext:
    """Everything a tool may reach, gathered by code before the loop starts. The model can't widen any of it."""

    who: Identity
    systems: CustomerSystems
    member: Member | None
    stays: tuple[StayRecord, ...]
    received_at_utc: str
    as_of_utc: str
    stated_channel: str | None
    customer: CustomerRules
    policies: tuple[PolicyVersion, ...]
    search: PolicySearch
    result_chars: int = 4000
    retrieved: set[str] = field(default_factory=set)
    evaluated: dict[str, EligibilityResult] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def stay_ids(self) -> set[str]:
        return {r.stay_id for r in self.stays}


@dataclass(frozen=True)
class ToolOutcome:
    content: str
    is_error: bool = False
    status: str = "ok"
    conflict: bool = False


def _error(code: str, detail: str = "") -> ToolOutcome:
    return ToolOutcome(json.dumps({"error": code, "detail": detail}), True, code)


def bound(payload: dict[str, Any], limit: int) -> str:
    """Never more than `limit` characters. Lists shrink first, and the result says it was cut, with how many it held."""
    text = json.dumps(payload, sort_keys=True, default=str)
    if len(text) <= limit:
        return text
    lists = [k for k, v in payload.items() if isinstance(v, list)]
    trimmed = dict(payload)
    for key in lists:
        total = len(trimmed[key])
        while len(json.dumps(trimmed, sort_keys=True, default=str)) > limit - 80 and trimmed[key]:
            trimmed[key] = trimmed[key][:-1]
        trimmed[f"{key}_total"] = total
    trimmed["truncated"] = True
    text = json.dumps(trimmed, sort_keys=True, default=str)
    return text if len(text) <= limit else json.dumps({"truncated": True, "error": "too_large"})


def _stay_summary(record: StayRecord) -> dict[str, Any]:
    return {
        "stay_id": record.stay_id,
        "property": record.property,
        "arrival_date": record.arrival_date,
        "nights": record.nights,
        "status": record.status,
    }


def _get_member(ctx: ToolContext, _args: GetMemberArgs) -> dict[str, Any]:
    if ctx.member is None:
        return {"confirmed": False, "note": "Identity isn't confirmed: two identifiers must match."}
    m = ctx.member
    return {
        "confirmed": True,
        "member_number": m.member_number,
        "first_name": m.first_name,
        "last_name": m.last_name,
        "tier": m.tier,
        "status": m.status,
    }


def _get_stay(ctx: ToolContext, args: GetStayArgs) -> dict[str, Any]:
    if args.stay_id is None:
        seen: dict[str, dict[str, Any]] = {}
        for record in ctx.stays:
            seen.setdefault(record.stay_id, _stay_summary(record))
        return {"stays": sorted(seen.values(), key=lambda row: row["arrival_date"])}
    if args.stay_id not in ctx.stay_ids():
        raise RecordNotFound("not on this member's profiles", code="not_found")
    records = [r for r in ctx.stays if r.stay_id == args.stay_id]
    return {"stays": [_stay_summary(records[0])], "records": len(records)}


def _require_stay(ctx: ToolContext, stay_id: str) -> None:
    if stay_id not in ctx.stay_ids():
        raise RecordNotFound("not on this member's profiles", code="not_found")


def _read_for_stay(ctx: ToolContext, stay_id: str) -> Any:
    assert ctx.member is not None
    return read_claim(
        ctx.systems,
        ctx.member,
        tuple(ctx.systems.get_stay_records(stay_id)),
        stay_id,
        received_at_utc=ctx.received_at_utc,
        as_of_utc=ctx.as_of_utc,
        stated_channel=ctx.stated_channel,
    )


def _get_points_ledger(ctx: ToolContext, args: StayArgs) -> dict[str, Any]:
    _require_stay(ctx, args.stay_id)
    _claim, evidence, _facts = _read_for_stay(ctx, args.stay_id)
    rows = [
        {"kind": e.kind, "points": e.points, "posted_at_utc": e.posted_at_utc, "stay_id": e.stay_id}
        for e in evidence.ledger[:MAX_LEDGER_ENTRIES]
    ]
    return {
        "entries": rows,
        "net_points": sum(e.points for e in evidence.ledger),
        "pending_postings": len(evidence.postings),
    }


def _cited(ref: PolicyRef) -> dict[str, Any] | None:
    if ref.section is None:
        return None
    return {"policy_id": ref.policy_id, "version": ref.version, "section_id": ref.section}


def _remember(ctx: ToolContext, refs: list[dict[str, Any]]) -> None:
    with ctx.lock:
        ctx.retrieved |= {f"{c['policy_id']}@{c['version']}#{c['section_id']}" for c in refs}


def _search_policy(ctx: ToolContext, args: SearchPolicyArgs) -> dict[str, Any]:
    _require_stay(ctx, args.stay_id)
    record = next(r for r in ctx.stays if r.stay_id == args.stay_id)
    timezone = ctx.customer.property_timezones.get(record.property)
    if timezone is None:
        return {"results": [], "note": "No time zone is configured for this property."}
    day = business_date(record.checkout_at_utc, timezone)
    hits = ctx.search(args.query, day)
    rows = [
        {
            "policy_id": h.ref.policy_id,
            "version": h.ref.version,
            "section_id": h.ref.section,
            "heading": h.heading,
            "excerpt": h.text[:MAX_EXCERPT_CHARS],
        }
        for h in hits
        if h.ref.section
    ]
    _remember(ctx, rows)
    return {"results": rows, "checkout_day": day.isoformat()}


def _evaluate(ctx: ToolContext, args: StayArgs) -> dict[str, Any]:
    _require_stay(ctx, args.stay_id)
    claim, _evidence, _facts = _read_for_stay(ctx, args.stay_id)
    result = evaluate_stay(claim, ctx.policies, ctx.customer)
    with ctx.lock:
        ctx.evaluated[args.stay_id] = result
    refs = [c for c in (_cited(r) for r in result.policy_refs) if c]
    refs += [c for c in (_cited(r.policy_ref) for r in result.reasons if r.policy_ref) if c]
    unique = list({(c["policy_id"], c["version"], c["section_id"]): c for c in refs}.values())
    _remember(ctx, unique)
    return {
        "stay_id": args.stay_id,
        "status": result.status.value,
        "action": result.action.value,
        "detail": result.detail,
        "points_owed": result.points_owed,
        "earned_points": result.earned_points,
        "credited_points": result.credited_points,
        "reasons": [r.text for r in result.reasons],
        "citations": unique,
    }


_HANDLERS: dict[str, tuple[type[_Strict], Callable[[ToolContext, Any], dict[str, Any]]]] = {
    "get_member": (GetMemberArgs, _get_member),
    "get_stay": (GetStayArgs, _get_stay),
    "get_points_ledger": (StayArgs, _get_points_ledger),
    "search_policy": (SearchPolicyArgs, _search_policy),
    "evaluate_eligibility": (StayArgs, _evaluate),
}
CONFLICT_DETAILS = ("conflicting_records", "conflicting_policies")


def run_tool(name: str, arguments: dict[str, Any], ctx: ToolContext) -> ToolOutcome:
    """Every failure comes back as a structured result the model can read. Nothing here raises to the loop."""
    if name not in _HANDLERS:
        return _error("unknown_tool")
    model, handler = _HANDLERS[name]
    try:
        require_case_reader(ctx.who)  # as the person who asked: the agent can't read what they can't (ENT-23)
    except NotPermitted:
        return _error("not_permitted")
    try:
        args = model.model_validate(arguments)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
        return _error("invalid_arguments", ", ".join(fields))
    try:
        payload = handler(ctx, args)
    except RecordNotFound:
        return _error("not_found")
    except CustomerSystemError as exc:
        code = "unavailable" if exc.retryable else "system_error"
        return _error(code, exc.code or type(exc).__name__)
    conflict = payload.get("detail") in CONFLICT_DETAILS and payload.get("action") == NextAction.ESCALATE.value
    return ToolOutcome(bound(payload, ctx.result_chars), conflict=conflict)
