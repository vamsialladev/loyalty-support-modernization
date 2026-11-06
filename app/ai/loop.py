"""The agent loop, as an explicit state machine (spec B.9; AI-08, AI-09, AI-14; RFC-0002).

It never runs indefinitely, and it has no business effects: it reads through tools and returns text. Each stop
condition has a test (`tests/test_ai_loop.py`). Whatever ends the loop, the case still holds the engine's result, and
that's the fallback.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import ValidationError

from app.ai.config import Limits
from app.ai.tools import ALLOWLIST, PARALLEL_SAFE, SUBMIT, TOOL_SPECS, Proposal, ToolContext, ToolOutcome, run_tool
from app.ai.validation import problems_with
from app.domain.eligibility import NextAction
from app.ports.model_provider import (
    MODEL_REFUSED,
    MODEL_TRUNCATED,
    AssistantMessage,
    Message,
    ModelProvider,
    ModelTurn,
    ProviderRejected,
    ProviderUnavailable,
    ToolCall,
    ToolResult,
    ToolResults,
    UserMessage,
)


class Stop(StrEnum):
    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    MISSING_INFORMATION = "missing_information"
    UNAUTHORIZED_ACTION = "unauthorized_action"
    REPEATED_TOOL_CALLS = "repeated_tool_calls"
    UNRESOLVABLE_CONFLICT = "unresolvable_conflict"
    MAX_STEPS = "max_steps"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DEADLINE = "deadline"
    CANCELLED = "cancelled"
    PROVIDER_FAILURES = "provider_failures"
    PROVIDER_REJECTED = "provider_rejected"
    REFUSAL = "refusal"
    INVALID_RESULT = "invalid_result"


ACCEPTED = (Stop.SUFFICIENT_EVIDENCE, Stop.MISSING_INFORMATION)
SWITCH_TO_THE_TOOL = "End the run by calling submit_recommendation."


@dataclass(frozen=True)
class StepEvent:
    kind: str  # model | tool | validation
    name: str
    status: str
    arguments_hash: str | None = None
    result_chars: int = 0
    elapsed_ms: int = 0


@dataclass
class LoopResult:
    stop: Stop
    proposal: Proposal | None = None
    problems: list[str] = field(default_factory=list)
    turns: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_microusd: int = 0


@dataclass
class Budget:
    """`remaining_microusd` of None means no money is at stake (a mock). `priced` converts a turn's usage to cost."""

    remaining_microusd: int | None
    priced: Callable[[ModelTurn], int] = lambda _turn: 0

    def exhausted(self) -> bool:
        return self.remaining_microusd is not None and self.remaining_microusd <= 0

    def spend(self, cost: int) -> None:
        if self.remaining_microusd is not None:
            self.remaining_microusd -= cost


def arguments_hash(call: ToolCall) -> str:
    """Enough to spot a repeat and to audit, without keeping what was asked."""
    text = json.dumps({"name": call.name, "arguments": call.arguments}, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


class Loop:
    def __init__(
        self,
        provider: ModelProvider,
        system: str,
        limits: Limits,
        ctx: ToolContext,
        budget: Budget,
        *,
        cancelled: Callable[[], bool] = lambda: False,
        on_step: Callable[[StepEvent], None] = lambda _event: None,
        on_turn: Callable[[ModelTurn, int], None] = lambda _turn, _cost: None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.provider, self.system, self.limits, self.ctx, self.budget = provider, system, limits, ctx, budget
        self.cancelled, self.on_step, self.on_turn, self.clock = cancelled, on_step, on_turn, clock
        self.seen: Counter[str] = Counter()
        self.repairs = 0
        self.failures = 0

    def run(self, opening: UserMessage) -> LoopResult:
        result = LoopResult(Stop.MAX_STEPS)
        messages: list[Message] = [opening]
        deadline = self.clock() + self.limits.deadline_seconds
        while result.turns < self.limits.max_turns:
            stop = self._before_call(deadline)
            if stop is not None:
                result.stop = stop
                return result
            turn = self._call_model(messages, deadline, result)
            if isinstance(turn, Stop):
                result.stop = turn
                return result
            if turn is None:
                continue  # a transient failure, within the limit
            messages.append(AssistantMessage(turn))
            ended = self._after_turn(turn, messages, result)
            if ended is not None:
                result.stop = ended
                return result
        result.stop = Stop.MAX_STEPS
        return result

    # ---------- the steps ----------

    def _before_call(self, deadline: float) -> Stop | None:
        if self.cancelled():
            return Stop.CANCELLED
        if self.clock() >= deadline:
            return Stop.DEADLINE
        if self.budget.exhausted():
            return Stop.BUDGET_EXHAUSTED
        return None

    def _call_model(self, messages: list[Message], deadline: float, result: LoopResult) -> ModelTurn | Stop | None:
        started = self.clock()
        timeout = min(self.limits.call_timeout_seconds, max(deadline - started, 0.1))
        try:
            turn = self.provider.complete(
                self.system, messages, list(TOOL_SPECS), self.limits.max_output_tokens, timeout
            )
        except ProviderUnavailable as exc:
            self.failures += 1
            self.on_step(StepEvent("model", "complete", f"unavailable:{exc}"[:24]))
            return Stop.PROVIDER_FAILURES if self.failures >= self.limits.max_provider_failures else None
        except ProviderRejected as exc:
            self.on_step(StepEvent("model", "complete", f"rejected:{exc}"[:24]))
            return Stop.PROVIDER_REJECTED
        result.turns += 1
        result.input_tokens += turn.usage.input_tokens
        result.output_tokens += turn.usage.output_tokens
        cost = self.budget.priced(turn)
        result.cost_microusd += cost
        self.budget.spend(cost)
        self.on_turn(turn, cost)
        self.on_step(StepEvent("model", "complete", turn.stop_reason[:24], elapsed_ms=self._since(started)))
        if turn.stop_reason == MODEL_REFUSED:
            return Stop.REFUSAL
        return turn

    def _after_turn(self, turn: ModelTurn, messages: list[Message], result: LoopResult) -> Stop | None:
        calls = list(turn.tool_calls)
        if turn.stop_reason == MODEL_TRUNCATED and not calls:
            return self._repair(messages, result, ["truncated: keep it shorter"], None)
        if not calls:
            return self._repair(messages, result, ["no_result: " + SWITCH_TO_THE_TOOL], None)
        if len(calls) > self.limits.max_tool_calls_per_turn:
            calls = calls[: self.limits.max_tool_calls_per_turn]
        for call in turn.tool_calls:
            if call.name not in ALLOWLIST:
                self.on_step(StepEvent("tool", call.name[:48], "unauthorized", arguments_hash(call)))
                return Stop.UNAUTHORIZED_ACTION
        submitted = next((c for c in calls if c.name == SUBMIT), None)
        if submitted is not None:
            return self._validate(submitted, turn, messages, result)
        return self._run_tools(turn, calls, messages, result)

    def _run_tools(
        self, turn: ModelTurn, calls: list[ToolCall], messages: list[Message], result: LoopResult
    ) -> Stop | None:
        fresh = [c for c in calls if self.seen[arguments_hash(c)] + 1 < self.limits.max_identical_calls]
        repeated = len(calls) - len(fresh)
        for call in calls:
            self.seen[arguments_hash(call)] += 1
        if repeated and not fresh:
            for call in calls:
                self.on_step(StepEvent("tool", call.name, "repeated", arguments_hash(call)))
            return Stop.REPEATED_TOOL_CALLS
        outcomes = self._execute(calls)
        result.tool_calls += len(calls)
        results: list[ToolResult] = []
        conflict = False
        for call, (outcome, elapsed) in zip(calls, outcomes, strict=True):
            self.on_step(
                StepEvent("tool", call.name, outcome.status, arguments_hash(call), len(outcome.content), elapsed)
            )
            results.append(ToolResult(call.call_id, outcome.content, outcome.is_error))
            conflict = conflict or outcome.conflict
        # Every tool_use needs a result, even for calls past the per-turn limit.
        ran = {c.call_id for c in calls}
        for call in turn.tool_calls:
            if call.call_id not in ran:
                results.append(ToolResult(call.call_id, json.dumps({"error": "too_many_calls"}), True))
        messages.append(ToolResults(tuple(results)))
        return Stop.UNRESOLVABLE_CONFLICT if conflict else None

    def _execute(self, calls: list[ToolCall]) -> list[tuple[ToolOutcome, int]]:
        """Read-only tools run side by side, up to the limit. Results keep the order of the calls."""

        def timed(call: ToolCall) -> tuple[ToolOutcome, int]:
            started = self.clock()
            outcome = run_tool(call.name, call.arguments, self.ctx)
            return outcome, self._since(started)

        together = [c for c in calls if c.name in PARALLEL_SAFE]
        done: dict[str, tuple[ToolOutcome, int]] = {}
        if len(together) > 1:
            with ThreadPoolExecutor(max_workers=self.limits.parallel_reads) as pool:
                done = dict(zip((c.call_id for c in together), pool.map(timed, together), strict=True))
        return [done[c.call_id] if c.call_id in done else timed(c) for c in calls]

    def _validate(
        self, submitted: ToolCall, turn: ModelTurn, messages: list[Message], result: LoopResult
    ) -> Stop | None:
        try:
            proposal = Proposal.model_validate(submitted.arguments)
        except ValidationError as exc:
            fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
            problems = [f"invalid_fields: {', '.join(fields)}"]
            self.on_step(StepEvent("validation", SUBMIT, "invalid_schema", arguments_hash(submitted)))
            return self._repair(messages, result, problems, turn)
        problems = problems_with(
            proposal, member_stays=self.ctx.stay_ids(), evaluated=self.ctx.evaluated, retrieved=self.ctx.retrieved
        )
        status = "valid" if not problems else "invalid"
        self.on_step(StepEvent("validation", SUBMIT, status, arguments_hash(submitted)))
        if problems:
            return self._repair(messages, result, problems, turn)
        result.proposal = proposal
        result.problems = []
        needs_more = proposal.recommended_action == NextAction.REQUEST_INFO.value
        return Stop.MISSING_INFORMATION if needs_more else Stop.SUFFICIENT_EVIDENCE

    def _repair(
        self, messages: list[Message], result: LoopResult, problems: list[str], turn: ModelTurn | None
    ) -> Stop | None:
        """One repair. After that the engine's result stands (spec B.9)."""
        result.problems = problems
        if self.repairs >= self.limits.max_repairs:
            return Stop.INVALID_RESULT
        self.repairs += 1
        note = "That can't be accepted: " + "; ".join(problems) + ". " + SWITCH_TO_THE_TOOL
        if turn is not None and turn.tool_calls:
            payload = json.dumps({"error": "validation_failed", "detail": note})
            messages.append(ToolResults(tuple(ToolResult(c.call_id, payload, True) for c in turn.tool_calls)))
        else:
            messages.append(UserMessage(note))
        return None

    def _since(self, started: float) -> int:
        return int((self.clock() - started) * 1000)
