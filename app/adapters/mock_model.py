"""Offline models, with no key and no cost. **Their results say nothing about any real model's quality** (BENCH-10).

- `ScriptedModel` replays fixed turns: how the tests reach each stop condition.
- `RulesMockModel` plays a model's part with plain rules, so arm C can be demonstrated and tested end to end without
an API. Every text it writes starts with `[MOCK]`, and every run records `is_mock`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from app.arms.conventional import signals
from app.domain.eligibility import ACTION_ORDER, NextAction
from app.ports.model_provider import (
    MODEL_DONE,
    MODEL_WANTS_TOOLS,
    AssistantMessage,
    Message,
    ModelTurn,
    ToolCall,
    ToolResults,
    ToolSpec,
    Usage,
    UserMessage,
)

MOCK_MODEL_ID = "mock-rules-v1"
_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_MENTION = re.compile(rf"\b({'|'.join(_MONTHS)})\b", re.IGNORECASE)
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")


class ScriptedModel:
    """Replays turns, or raises what a turn holds. When the script runs out it asks for nothing more."""

    name = "scripted"
    is_mock = True

    def __init__(
        self,
        turns: Sequence[ModelTurn | Exception],
        model_id: str = "scripted-test",
        image_fields: dict[str, str | None] | None = None,
    ) -> None:
        self.turns, self.model_id = list(turns), model_id
        self.image_fields = image_fields or {}
        self.calls = 0
        self.seen: list[tuple[str, list[Message]]] = []

    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec], max_tokens: int, timeout_seconds: float
    ) -> ModelTurn:
        self.calls += 1
        self.seen.append((system, list(messages)))
        turn = self.turns.pop(0) if self.turns else ModelTurn(MODEL_DONE, text="(the script ended)")
        if isinstance(turn, Exception):
            raise turn
        return turn

    def read_image(
        self, media_type: str, content: bytes, timeout_seconds: float
    ) -> tuple[dict[str, str | None], Usage]:
        """A labelled fixture, never a reading of the file."""
        return dict(self.image_fields), Usage(50, 10)


def call(call_id: str, name: str, **arguments: Any) -> ToolCall:
    return ToolCall(call_id, name, arguments)


def wants(*calls: ToolCall, input_tokens: int = 100, output_tokens: int = 20) -> ModelTurn:
    return ModelTurn(MODEL_WANTS_TOOLS, tool_calls=calls, usage=Usage(input_tokens, output_tokens))


def _results_by_tool(messages: list[Message]) -> dict[str, list[dict[str, Any]]]:
    """Tool name -> parsed results so far. The mock reads only what the loop gave it, like a real model."""
    names: dict[str, str] = {}
    out: dict[str, list[dict[str, Any]]] = {}
    for message in messages:
        if isinstance(message, AssistantMessage):
            names |= {c.call_id: c.name for c in message.turn.tool_calls}
        elif isinstance(message, ToolResults):
            for result in message.results:
                if not result.is_error:
                    out.setdefault(names.get(result.call_id, ""), []).append(json.loads(result.content))
    return out


def _request_text(messages: list[Message]) -> str:
    first = next((m for m in messages if isinstance(m, UserMessage)), None)
    if first is None:
        return ""
    found = re.search(r"<member_messages>(.*?)</member_messages>", first.text, re.DOTALL)
    return found.group(1) if found else first.text


def _named_stay(text: str) -> str | None:
    found = re.search(r"<engine_stay>(.*?)</engine_stay>", text, re.DOTALL)
    return found.group(1).strip() if found and found.group(1).strip() else None


def choose_stays(text: str, stays: list[dict[str, Any]], known: str | None) -> list[str]:
    """Stays this message means: the one the rules found, plus any month that fits exactly one other stay."""
    chosen = [known] if known else []
    months = {_MONTHS.index(m.lower()) + 1 for m in _MENTION.findall(text)}
    months |= {int(m) for m, _d in _NUMERIC_DATE.findall(text) if 1 <= int(m) <= 12}
    for month in sorted(months):
        fits = [s["stay_id"] for s in stays if int(s["arrival_date"][5:7]) == month and s["stay_id"] not in chosen]
        if len(fits) == 1:
            chosen.append(fits[0])
    return chosen


class RulesMockModel:
    """Asks for the member and the stays, chooses by month, asks the engine, looks up the policy, then submits."""

    name = "mock"
    is_mock = True
    model_id = MOCK_MODEL_ID

    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec], max_tokens: int, timeout_seconds: float
    ) -> ModelTurn:
        results = _results_by_tool(messages)
        first_user = next(m for m in messages if isinstance(m, UserMessage)).text
        usage = Usage(len(first_user) // 4, 40)
        if "get_stay" not in results:
            return ModelTurn(
                MODEL_WANTS_TOOLS,
                tool_calls=(ToolCall("m1", "get_member", {}), ToolCall("m2", "get_stay", {"stay_id": None})),
                usage=usage,
            )
        text = _request_text(messages)
        stays = results["get_stay"][0].get("stays", [])
        chosen = choose_stays(text, stays, _named_stay(first_user))
        evaluated = {r.get("stay_id"): r for r in results.get("evaluate_eligibility", [])}
        pending = [stay for stay in chosen if stay not in evaluated]
        if pending:
            calls = tuple(ToolCall(f"e{i}", "evaluate_eligibility", {"stay_id": s}) for i, s in enumerate(pending[:4]))
            return ModelTurn(MODEL_WANTS_TOOLS, tool_calls=calls, usage=usage)
        return ModelTurn(
            MODEL_WANTS_TOOLS,
            tool_calls=(ToolCall("s1", "submit_recommendation", self._proposal(text, chosen, evaluated)),),
            usage=usage,
        )

    def read_image(
        self, media_type: str, content: bytes, timeout_seconds: float
    ) -> tuple[dict[str, str | None], Usage]:
        """A mock can't see. It says so by returning nothing, and the case goes on without the image."""
        return {}, Usage()

    @staticmethod
    def _proposal(text: str, chosen: list[str], evaluated: dict[Any, dict[str, Any]]) -> dict[str, Any]:
        actions = [NextAction(r["action"]) for r in evaluated.values()]
        action = min(actions, key=ACTION_ORDER.index).value if actions else NextAction.REQUEST_INFO.value
        citations = [c for r in evaluated.values() for c in r.get("citations", [])]
        unique = list({(c["policy_id"], c["version"], c["section_id"]): c for c in citations}.values())
        out_of_scope = list(signals.out_of_scope_topics(text))
        missing = [] if chosen else ["Which stay is this about? Please send its confirmation number."]
        return {
            "summary": f"[MOCK] A points claim about {len(chosen)} stay(s).",
            "observed_facts": [f"[MOCK] Stay {stay}." for stay in chosen],
            "stay_ids": chosen,
            "recommended_action": action,
            "escalation_reason": "[MOCK] The engine's result." if action == NextAction.ESCALATE.value else None,
            "missing_information": missing,
            "citations": unique,
            "explanation": "[MOCK] This repeats the engine's result. A mock can't explain anything.",
            "draft_reply": "[MOCK] Thank you for your message. We are looking at your request.",
            "out_of_scope_items": out_of_scope,
            "request_language": signals.detect_language(text),
        }
