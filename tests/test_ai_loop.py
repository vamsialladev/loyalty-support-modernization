"""The agent loop's stop conditions, one test each, on scripted models (spec B.9, Appendix C M8; AI-08, AI-09, TEST-03).

Each test also checks the point of the stop: no result is accepted, so the case keeps the engine's result.
"""

from __future__ import annotations

import itertools
import threading
import time
from datetime import date
from typing import Any

import pytest

from app.adapters.mock_model import ScriptedModel, call, wants
from app.ai.config import Limits
from app.ai.loop import ACCEPTED, Budget, Loop, LoopResult, StepEvent, Stop
from app.ai.tools import SUBMIT, ToolContext
from app.domain.customer_records import LedgerEntry, Member, StayRecord
from app.domain.eligibility import CustomerRules
from app.domain.policy import PolicyVersion
from app.domain.roles import Identity, Role
from app.ports.customer_systems import RecordNotFound, TemporarilyUnavailable
from app.ports.model_provider import (
    MODEL_DONE,
    MODEL_REFUSED,
    ModelTurn,
    ProviderRejected,
    ProviderUnavailable,
    Usage,
    UserMessage,
)

WHO = Identity(1, "agent.ana", "Ana", Role.AGENT)
MEMBER = Member("GR-11111", "Ana", "Ruiz", "a@mail.test", "+1 201 555 0100", "gold", "active", "1980-01-01")
RULES = {
    "waiting_period_days": 14,
    "claim_window_months": 12,
    "eligible_channels": ["direct", "phone"],
    "ota_eligible_with_member_on_booking": True,
    "corporate_rate_prefix": "CORP",
    "supervisor_limit_points": 20000,
    "pending_posting_blocks_adjustment": True,
}
POLICIES = (
    PolicyVersion(
        "missing-points-requests",
        2,
        "Missing points",
        "hg-demo",
        date(2026, 7, 1),
        None,
        "published",
        ("3", "5"),
        RULES,
    ),
    PolicyVersion(
        "guest-rewards-earning",
        1,
        "Earning",
        "hg-demo",
        date(2025, 1, 1),
        None,
        "published",
        ("2",),
        {"points_per_usd_room_revenue": 10},
    ),
)
CUSTOMER = CustomerRules({"beach-resort": "America/New_York"}, {"DIR": "direct"})


def stay(stay_id: str = "BR-1000", record: str = "R-1", **over: Any) -> StayRecord:
    base = {
        "record_id": record,
        "stay_id": stay_id,
        "property": "beach-resort",
        "member_on_booking": True,
        "arrival_date": "2026-07-10",
        "nights": 2,
        "checkout_at_utc": "2026-07-12T15:00:00Z",
        "status": "checked_out",
        "source_code": "DIR",
        "rate_code": "BAR",
        "room_revenue_cents": 50000,
        "member_number": "GR-11111",
        "channel": "direct",
        "guest_name": "Ana Ruiz",
    }
    return StayRecord(**{**base, **over})


class Systems:
    """Only what the tools read. Any other call fails the test."""

    def __init__(self, stays: tuple[StayRecord, ...] = (stay(),), ledger: tuple[LedgerEntry, ...] = ()) -> None:
        self.stays, self.ledger = stays, ledger
        self.fail: Exception | None = None
        self.delay = 0.0
        self.running = 0
        self.peak = 0
        self.lock = threading.Lock()

    def _enter(self) -> None:
        with self.lock:
            self.running += 1
            self.peak = max(self.peak, self.running)
        if self.delay:
            time.sleep(self.delay)
        with self.lock:
            self.running -= 1
        if self.fail:
            raise self.fail

    def get_stay_records(self, stay_id: str) -> list[StayRecord]:
        self._enter()
        found = [r for r in self.stays if r.stay_id == stay_id]
        if not found:
            raise RecordNotFound("none", code="stay_not_found")
        return found

    def get_ledger(self, member: str) -> list[LedgerEntry]:
        self._enter()
        return list(self.ledger)

    def get_pending_postings(self, stay_id: str) -> list[Any]:
        return []

    def find_members(self, **_kw: Any) -> list[Member]:
        return [MEMBER]

    def get_member(self, number: str) -> Member:
        return MEMBER


def context(systems: Systems | None = None, who: Identity = WHO, member: Member | None = MEMBER) -> ToolContext:
    systems = systems or Systems()
    return ToolContext(
        who=who,
        systems=systems,  # type: ignore[arg-type]
        member=member,
        stays=systems.stays,
        received_at_utc="2026-08-20T12:00:00Z",
        as_of_utc="2026-08-20T12:00:00Z",
        stated_channel=None,
        customer=CUSTOMER,
        policies=POLICIES,
        search=lambda _q, _d: [],
    )


def proposal(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "A claim about one stay.",
        "observed_facts": ["The member stayed in July."],
        "stay_ids": ["BR-1000"],
        "recommended_action": "adjust",
        "escalation_reason": None,
        "missing_information": [],
        "citations": [],
        "explanation": "The ledger shows nothing for this stay.",
        "draft_reply": "We are checking your request.",
        "out_of_scope_items": [],
        "request_language": None,
    }
    return {**base, **over}


EVALUATE = call("e1", "evaluate_eligibility", stay_id="BR-1000")


def submit(**over: Any) -> ModelTurn:
    return wants(call("s1", SUBMIT, **proposal(**over)))


def run(
    turns: list[Any],
    ctx: ToolContext | None = None,
    limits: Limits | None = None,
    budget: Budget | None = None,
    **kw: Any,
) -> tuple[LoopResult, ScriptedModel, list[StepEvent]]:
    model = ScriptedModel(turns)
    events: list[StepEvent] = []
    loop = Loop(
        model,
        "system",
        limits or Limits(),
        ctx or context(),
        budget or Budget(None),
        on_step=events.append,
        **kw,
    )
    return loop.run(UserMessage("opening")), model, events


# ---------- the ten stop conditions (spec B.9) ----------


def test_stop_sufficient_evidence_and_a_valid_recommendation() -> None:
    result, _m, events = run([wants(EVALUATE), submit()])
    assert result.stop is Stop.SUFFICIENT_EVIDENCE and result.stop in ACCEPTED
    assert result.proposal is not None and result.proposal.recommended_action == "adjust"
    assert result.turns == 2 and result.tool_calls == 1
    assert [e.status for e in events if e.kind == "validation"] == ["valid"]


def test_stop_missing_information_needing_a_user_response() -> None:
    result, _m, _e = run([submit(stay_ids=[], recommended_action="request_info", missing_information=["Which stay?"])])
    assert result.stop is Stop.MISSING_INFORMATION and result.proposal is not None


@pytest.mark.parametrize(
    "tool", ["adjust_points", "submit_adjustment", "run_sql", "bash", "http_get", "approve_adjustment", "read_file"]
)
def test_stop_an_unauthorized_action_request(tool: str) -> None:
    result, model, events = run([wants(call("x", tool, points=50000)), submit()])
    assert result.stop is Stop.UNAUTHORIZED_ACTION and result.proposal is None
    assert model.calls == 1, "the loop stops at once and doesn't ask the model again"
    assert events[-1].status == "unauthorized"


def test_an_unauthorized_call_beside_a_good_one_still_stops_and_runs_neither() -> None:
    systems = Systems()
    result, _m, _e = run([wants(EVALUATE, call("x", "adjust_points", points=1))], context(systems))
    assert result.stop is Stop.UNAUTHORIZED_ACTION and result.tool_calls == 0


def test_stop_repeated_tool_calls_without_new_evidence() -> None:
    same = call("e", "evaluate_eligibility", stay_id="BR-1000")
    result, model, _e = run([wants(same), wants(call("e2", "evaluate_eligibility", stay_id="BR-1000")), submit()])
    assert result.stop is Stop.REPEATED_TOOL_CALLS and result.proposal is None and model.calls == 2


def test_stop_an_unresolvable_conflict() -> None:
    conflicting = Systems((stay(record="R-1"), stay(record="R-2", room_revenue_cents=99900)))
    result, model, _e = run([wants(EVALUATE), submit()], context(conflicting))
    assert result.stop is Stop.UNRESOLVABLE_CONFLICT and result.proposal is None and model.calls == 1


def test_stop_maximum_steps() -> None:
    turns = [wants(call(f"c{i}", "get_stay", stay_id=f"BR-{i}")) for i in range(10)]
    result, model, _e = run(turns, limits=Limits(max_turns=3))
    assert result.stop is Stop.MAX_STEPS and result.proposal is None and model.calls == 3


def test_stop_the_cost_budget() -> None:
    budget = Budget(100, lambda turn: turn.usage.input_tokens)
    turns = [wants(call(f"c{i}", "get_stay", stay_id=None), input_tokens=60) for i in range(5)]
    result, model, _e = run(turns, budget=budget, limits=Limits(max_identical_calls=99))
    assert result.stop is Stop.BUDGET_EXHAUSTED and model.calls == 2 and result.cost_microusd == 120


def test_nothing_is_called_when_the_budget_is_already_gone() -> None:
    result, model, _e = run([submit()], budget=Budget(0))
    assert result.stop is Stop.BUDGET_EXHAUSTED and model.calls == 0


def test_stop_the_wall_clock_deadline() -> None:
    ticks = itertools.count(0, 40)
    result, model, _e = run(
        [wants(call(f"c{i}", "get_stay", stay_id=None)) for i in range(5)],
        limits=Limits(deadline_seconds=100, max_identical_calls=99),
        clock=lambda: float(next(ticks)),
    )
    assert result.stop is Stop.DEADLINE and model.calls < 5


def test_stop_cancellation() -> None:
    answers = iter([False, True])
    result, model, _e = run([wants(EVALUATE), submit()], cancelled=lambda: next(answers))
    assert result.stop is Stop.CANCELLED and model.calls == 1 and result.proposal is None


def test_stop_repeated_provider_failures() -> None:
    result, model, events = run([ProviderUnavailable("overloaded"), ProviderUnavailable("overloaded"), submit()])
    assert result.stop is Stop.PROVIDER_FAILURES and model.calls == 2
    assert [e.status for e in events][:2] == ["unavailable:overloaded", "unavailable:overloaded"]


def test_stop_repeated_tool_failures_ends_without_a_result() -> None:
    """A tool that keeps failing gives the model nothing new: identical retries hit the repeat stop."""
    systems = Systems()
    systems.fail = TemporarilyUnavailable("down", code="unavailable")
    retry = call("e", "evaluate_eligibility", stay_id="BR-1000")
    result, _m, events = run([wants(retry), wants(retry), submit()], context(systems))
    assert result.stop is Stop.REPEATED_TOOL_CALLS and result.proposal is None
    assert any(e.status == "unavailable" for e in events)


# ---------- other ways out ----------


def test_one_transient_failure_is_retried_within_the_limit() -> None:
    result, _m, _e = run([ProviderUnavailable("blip"), wants(EVALUATE), submit()])
    assert result.stop is Stop.SUFFICIENT_EVIDENCE


def test_a_rejected_request_isnt_retried() -> None:
    result, model, _e = run([ProviderRejected("status_401"), submit()])
    assert result.stop is Stop.PROVIDER_REJECTED and model.calls == 1


def test_a_refusal_stops_the_run() -> None:
    result, model, _e = run([ModelTurn(MODEL_REFUSED), submit()])
    assert result.stop is Stop.REFUSAL and model.calls == 1 and result.proposal is None


# ---------- validation and the one repair (AI-14) ----------


def test_one_repair_then_acceptance() -> None:
    result, model, events = run([wants(EVALUATE), submit(recommended_action="deny"), submit()])
    assert result.stop is Stop.SUFFICIENT_EVIDENCE and model.calls == 3
    assert [e.status for e in events if e.kind == "validation"] == ["invalid", "valid"]


def test_a_second_invalid_result_ends_it_and_the_engine_stands() -> None:
    result, model, _e = run([wants(EVALUATE), submit(recommended_action="deny"), submit(recommended_action="deny")])
    assert result.stop is Stop.INVALID_RESULT and result.proposal is None and model.calls == 3
    assert "action_mismatch" in result.problems[0]


def test_text_with_no_tool_call_gets_one_nudge() -> None:
    result, model, _e = run([ModelTurn(MODEL_DONE, text="I think it's fine."), ModelTurn(MODEL_DONE, text="Really.")])
    assert result.stop is Stop.INVALID_RESULT and model.calls == 2


def test_a_truncated_turn_counts_as_invalid() -> None:
    result, _m, _e = run([ModelTurn("max_tokens"), ModelTurn("max_tokens")])
    assert result.stop is Stop.INVALID_RESULT and "truncated" in result.problems[0]


def test_a_schema_violation_is_repairable_and_an_amount_field_is_refused() -> None:
    result, _m, _e = run(
        [wants(call("s", SUBMIT, **proposal(points=50000))), wants(call("t", SUBMIT, **proposal(points=1)))]
    )
    assert result.stop is Stop.INVALID_RESULT and "points" in result.problems[0]


# ---------- tool calls inside the loop ----------


def test_every_tool_call_gets_a_result_past_the_per_turn_limit() -> None:
    calls = [call(f"c{i}", "get_stay", stay_id=f"BR-{i}") for i in range(6)]
    result, model, _e = run(
        [wants(*calls), submit(stay_ids=[], recommended_action="request_info", missing_information=["x"])]
    )
    assert result.stop is Stop.MISSING_INFORMATION and result.tool_calls == 4
    second_call_messages = model.seen[1][1]
    results = second_call_messages[-1].results  # type: ignore[union-attr]
    assert {r.call_id for r in results} == {f"c{i}" for i in range(6)}
    assert sum(1 for r in results if "too_many_calls" in r.content) == 2


def test_read_tools_run_side_by_side_within_the_limit() -> None:
    systems = Systems((stay("BR-1000"), stay("BR-2000", "R-2"), stay("BR-3000", "R-3"), stay("BR-4000", "R-4")))
    systems.delay = 0.05
    calls = [call(f"c{i}", "get_points_ledger", stay_id=s.stay_id) for i, s in enumerate(systems.stays)]
    result, model, _e = run(
        [wants(*calls), submit(stay_ids=[], recommended_action="request_info", missing_information=["x"])],
        context(systems),
        limits=Limits(parallel_reads=2),
    )
    assert result.stop is Stop.MISSING_INFORMATION
    assert 1 < systems.peak <= 2 * 2  # bounded: each tool reads twice at most at once per worker
    results = model.seen[1][1][-1].results  # type: ignore[union-attr]
    assert [r.call_id for r in results] == [c.call_id for c in calls], "results keep the order of the calls"


def test_tokens_add_up_across_turns() -> None:
    turn = wants(EVALUATE, input_tokens=100, output_tokens=7)
    final = ModelTurn("tool_use", tool_calls=submit().tool_calls, usage=Usage(200, 9))
    result, _m, _e = run([turn, final])
    assert (result.input_tokens, result.output_tokens) == (300, 16)


def test_each_step_is_reported_with_a_hash_and_never_the_arguments() -> None:
    _r, _m, events = run([wants(EVALUATE), submit()])
    tool_steps = [e for e in events if e.kind == "tool"]
    assert tool_steps and all(e.arguments_hash and len(e.arguments_hash) == 64 for e in tool_steps)
    assert "BR-1000" not in repr(events)
