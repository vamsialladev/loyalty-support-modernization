"""What each MCP tool does, without the SDK: plain functions over the app's own services (spec G.3; REUSE-06).

Every tool takes a case ID and reads only what arm C's model may read for that case (`app/ai/tools.py`): the case's
confirmed member, that member's stays, their ledger, the policy in force, the engine's result. So an MCP client sees
exactly what our own model sees, and nothing wider. Another customer's case is "not found", as in REST and stage 7.

Call order, from stage 7: rate limit, then permission, then the work, then the audit record. Denied and failed calls
are audited too. Nothing here can write: the read list below is explicit, and a test checks no write function is
reachable from this module.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app import correlation
from app.ai.tools import TOOL_SPECS, run_tool
from app.domain.roles import Identity, NotPermitted
from app.services import conventional
from app.services.assisted import tool_context_for
from app.services.cases import CaseNotFound, evidence_rows, get_case, read_time
from app.services.rate_limit import RateLimited
from app.services.systems import SystemsFactory
from protocols.common.calls import arguments_hash, audit, limit

READ = "loyalty.read"
CASE_READ = "loyalty.case.read"
CASE_TOOL = "get_case_evidence"
# Arm C's five read tools, by name; never `submit_recommendation`, which isn't a read.
ENGINE_TOOLS = ("get_member", "get_stay", "get_points_ledger", "search_policy", "evaluate_eligibility")
TOOL_SCOPES = {**dict.fromkeys(ENGINE_TOOLS, READ), CASE_TOOL: CASE_READ}
DESCRIPTIONS = {spec.name: spec.description for spec in TOOL_SPECS}
DESCRIPTIONS[CASE_TOOL] = (
    "One case's status, the engine's latest result with its citations, and the evidence attached, as references "
    "only. No member contact details."
)


class ToolFailed(Exception):
    """A structured tool error the client can read: `not_found`, `not_permitted`, `invalid_arguments`, ..."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass
class McpReader:
    sessions: sessionmaker[Session]
    systems_for: SystemsFactory
    per_minute: int = 120

    def call(self, who: Identity, scopes: frozenset[str], tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Runs one tool for one caller. Raises `ToolFailed`; never returns a partial result."""
        with correlation.correlated(correlation.new_id()), self.sessions() as s:
            fingerprint = arguments_hash(arguments)
            try:
                limit(s, who, self.per_minute)
            except RateLimited:
                audit(s, who, "mcp", tool, "rate_limited", arguments_hash=fingerprint)
                s.commit()
                raise ToolFailed("rate_limited", "try again in a minute") from None
            try:
                result = self._run(s, who, scopes, tool, dict(arguments))
            except ToolFailed as failure:
                audit(s, who, "mcp", tool, failure.code, arguments_hash=fingerprint)
                s.commit()
                raise
            audit(s, who, "mcp", tool, "ok", arguments_hash=fingerprint, case_id=arguments.get("case_id"))
            s.commit()
            return result

    def _run(
        self, s: Session, who: Identity, scopes: frozenset[str], tool: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool not in TOOL_SCOPES:
            raise ToolFailed("unknown_tool")
        if TOOL_SCOPES[tool] not in scopes:
            raise ToolFailed("insufficient_scope", TOOL_SCOPES[tool])
        case_id = arguments.pop("case_id", None)
        if not isinstance(case_id, int) or isinstance(case_id, bool) or case_id < 1:
            raise ToolFailed("invalid_arguments", "case_id")
        try:
            case = get_case(s, who, case_id)  # customer scope: another customer's case doesn't exist here
        except (CaseNotFound, NotPermitted):
            raise ToolFailed("not_found") from None
        if tool == CASE_TOOL:
            if arguments:
                raise ToolFailed("invalid_arguments", ", ".join(sorted(arguments)))
            return case_evidence(s, case)
        ctx = tool_context_for(s, who, case, self.systems_for(read_time(case)))
        outcome = run_tool(tool, arguments, ctx)
        payload: dict[str, Any] = json.loads(outcome.content)
        if outcome.is_error:
            raise ToolFailed(str(payload.get("error", "error")), str(payload.get("detail", "")))
        return payload


def case_evidence(s: Session, case: Any) -> dict[str, Any]:
    """References and the engine's own result only: no snapshots, no member names, no request text."""
    rec = conventional.latest_recommendation(s, case)
    return {
        "case_id": case.id,
        "reference": case.reference,
        "status": case.status,
        "arm": case.arm,
        "received_at_utc": case.received_at_utc,
        "engine_result": None
        if rec is None
        else {
            "author": rec.author,
            "status": rec.status,
            "action": rec.action,
            "detail": rec.detail,
            "stay_id": rec.stay_id,
            "points_owed": rec.points_owed,
            "citations": rec.citations,
            "at_utc": rec.created_at_utc,
        },
        "evidence": [
            {"kind": row.kind, "source_ref": row.source_ref, "attached_at_utc": row.attached_at_utc}
            for row in evidence_rows(s, case)
        ][:100],
    }


Reader = Callable[[Identity, frozenset[str], str, dict[str, Any]], dict[str, Any]]
