"""The provider adapters and the harness's caps (BENCH-10, ENT-15, LIVE-05, AI-12). No network and no key: `client`
is fake."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2 as httpx
import pytest
from sqlalchemy import select

from app.adapters.anthropic_model import AnthropicModel
from app.adapters.mock_model import RulesMockModel, ScriptedModel, wants
from app.ai.config import ModelPrice, ai_config
from app.ai.harness import (
    AiRuntime,
    SpendCaps,
    add_spend,
    latest_run,
    periods,
    remaining_microusd,
    run_loop,
    spent_microusd,
)
from app.ai.loop import Stop
from app.ai.tools import TOOL_SPECS
from app.persistence.models import AiStep, Case
from app.ports.model_provider import (
    AssistantMessage,
    ProviderRejected,
    ProviderUnavailable,
    ToolResult,
    ToolResults,
    UserMessage,
)
from app.services import cases as svc
from app.services.assisted import mode_label, runtime_from_settings
from app.settings import AppSettings
from tests.arm_a import ArmA, make_arm_a
from tests.test_ai_loop import context, proposal


class FakeMessages:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome: Any) -> None:
        self.messages = FakeMessages(outcome)
        self.timeout = 0.0

    def with_options(self, timeout: float) -> FakeClient:
        self.timeout = timeout
        return self


def response(*content: Any, stop_reason: str = "tool_use") -> Any:
    usage = SimpleNamespace(
        input_tokens=11, output_tokens=7, cache_read_input_tokens=0, cache_creation_input_tokens=None
    )
    return SimpleNamespace(content=list(content), stop_reason=stop_reason, usage=usage)


def tool_block(name: str = "get_member", **args: Any) -> Any:
    return SimpleNamespace(type="tool_use", id="toolu_1", name=name, input=args)


def complete(model: AnthropicModel, messages: list[Any] | None = None) -> Any:
    return model.complete("system text", messages or [UserMessage("hello")], list(TOOL_SPECS), 500, 12.5)


def test_the_request_has_strict_tools_and_no_forbidden_parameters() -> None:
    client = FakeClient(response(tool_block()))
    turn = complete(AnthropicModel("claude-haiku-5-5", client=client))
    sent = client.messages.kwargs
    assert sent["model"] == "claude-haiku-5-5" and sent["output_config"] == {"effort": "low"}
    assert sent["tool_choice"] == {"type": "auto"} and all(t["strict"] is True for t in sent["tools"])
    for forbidden in ("temperature", "top_p", "top_k", "thinking", "budget_tokens"):
        assert forbidden not in sent, forbidden
    assert client.timeout == 12.5
    assert (
        turn.tool_calls[0].name == "get_member" and turn.usage.input_tokens == 11 and turn.usage.cache_write_tokens == 0
    )


def test_an_assistant_turn_goes_back_unchanged_and_all_results_in_one_message() -> None:
    thinking = SimpleNamespace(type="thinking", thinking="", signature="sig")
    client = FakeClient(response(thinking, tool_block()))
    model = AnthropicModel("claude-haiku-5-5", client=client)
    turn = complete(model)
    results = ToolResults((ToolResult("a", "1"), ToolResult("b", "2", True)))
    complete(model, [UserMessage("hello"), AssistantMessage(turn), results])
    wire = client.messages.kwargs["messages"]
    assert wire[1] == {"role": "assistant", "content": turn.state} and wire[1]["content"][0] is thinking
    assert [b["tool_use_id"] for b in wire[2]["content"]] == ["a", "b"] and wire[2]["content"][1]["is_error"] is True


def test_a_refusal_comes_through_as_a_stop_reason() -> None:
    assert complete(AnthropicModel("m", client=FakeClient(response(stop_reason="refusal")))).stop_reason == "refusal"


def _status(cls: Any, code: int) -> Any:
    req = httpx.Request("POST", "https://example.test")
    return cls("no", response=httpx.Response(code, request=req), body=None)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (_status(anthropic.RateLimitError, 429), ProviderUnavailable),
        (_status(anthropic.InternalServerError, 503), ProviderUnavailable),
        (anthropic.APITimeoutError(httpx.Request("POST", "https://example.test")), ProviderUnavailable),
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://example.test")), ProviderUnavailable),
        (_status(anthropic.AuthenticationError, 401), ProviderRejected),
        (_status(anthropic.NotFoundError, 404), ProviderRejected),
        (_status(anthropic.BadRequestError, 400), ProviderRejected),
    ],
)
def test_errors_are_sorted_into_retry_and_dont(error: Exception, kind: type[Exception]) -> None:
    with pytest.raises(kind):
        complete(AnthropicModel("m", client=FakeClient(error)))


def test_a_mock_labels_itself() -> None:
    assert RulesMockModel.is_mock is True and ScriptedModel([]).is_mock is True


def test_settings_decide_live_and_half_set_means_no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def settings(**kw: Any) -> AppSettings:
        return AppSettings(database_url="sqlite://", **kw)

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert runtime_from_settings(settings()).provider.is_mock is True  # type: ignore[union-attr]
    assert mode_label(settings()) == "MOCK mock-rules-v1"
    off = runtime_from_settings(settings(ai_provider="anthropic", anthropic_model="claude-haiku-5-5"))
    assert off.provider is None and "FEATURE_LIVE_AI" in off.unavailable_reason
    no_key = runtime_from_settings(
        settings(ai_provider="anthropic", feature_live_ai=True, anthropic_model="claude-haiku-5-5")
    )
    assert no_key.provider is None and "key" in no_key.unavailable_reason
    assert runtime_from_settings(settings(ai_provider="zai")).provider is None
    bedrock = runtime_from_settings(settings(ai_provider="bedrock", feature_live_ai=True))
    assert bedrock.provider is None and "configured only" in bedrock.unavailable_reason  # ENT-13: blocked, fails safe
    label = mode_label(settings(ai_provider="anthropic", feature_live_ai=True, anthropic_model="claude-haiku-5-5"))
    assert label == "LIVE claude-haiku-5-5"


def test_only_listed_models_have_prices_and_arithmetic_rounds_up() -> None:
    assert "claude-haiku-5-5" in ai_config("hg-demo").models
    price = ModelPrice(0.10, 0.50, "2026-11-06")
    assert price.cost_microusd(1000, 100) == 150
    assert price.cost_microusd(1, 0) == 1  # 0.1 of a micro-dollar rounds up
    assert ai_config("hg-demo").models["claude-haiku-5-5"].checked_on


# ---------- the harness, on a real database ----------


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def _case(arm: ArmA, s: Any) -> Case:
    request = svc.IntakeRequest(received_at_utc="2026-08-20T12:00:00Z", contact_channel="email", text="Points.")
    return svc.create_case(s, arm.who("agent.ana"), request, arm="C")


class LiveLike(ScriptedModel):
    """Priced like a real model: nothing here calls a network."""

    name = "anthropic"
    is_mock = False


def test_an_unlisted_or_deprecated_model_fails_safe(arm: ArmA, monkeypatch: pytest.MonkeyPatch) -> None:
    with arm.sessions() as s:
        case = _case(arm, s)
        model = LiveLike([wants()], model_id="claude-not-on-the-list")
        run, result = run_loop(s, arm.who("agent.ana"), case, AiRuntime(model), context(), UserMessage("x"), [])
        assert run is not None and run.stop_reason == "unknown_model" and model.calls == 0
        assert result.proposal is None


def test_no_provider_means_no_run_and_says_why(arm: ArmA) -> None:
    with arm.sessions() as s:
        case = _case(arm, s)
        run, result = run_loop(s, arm.who("agent.ana"), case, AiRuntime(None), context(), UserMessage("x"), [])
        assert run is None and result.stop is Stop.PROVIDER_REJECTED and result.problems == ["no_provider"]


def test_spend_is_stored_survives_a_new_session_and_blocks_at_the_cap(arm: ArmA) -> None:
    now = datetime(2026, 11, 6, tzinfo=UTC)
    caps = SpendCaps(per_run_usd=1.0, daily_usd=0.01, monthly_usd=5.0)
    with arm.sessions() as s:
        add_spend(s, 4000, now)
        add_spend(s, 4000, now)
    with arm.sessions() as s:  # a restart: nothing was only in memory
        day, month = periods(now)
        assert spent_microusd(s, day) == spent_microusd(s, month) == 8000
        assert remaining_microusd(s, caps, now) == 2000
        add_spend(s, 2000, now)
        assert remaining_microusd(s, caps, now) == 0
        next_day = datetime(2026, 11, 7, tzinfo=UTC)
        assert remaining_microusd(s, caps, next_day) == min(1_000_000, 10_000, 5_000_000 - 10_000)


def test_a_capped_run_never_calls_the_model(arm: ArmA) -> None:
    with arm.sessions() as s:
        case = _case(arm, s)
        add_spend(s, 2_000_000)
        model = LiveLike([wants()], model_id="claude-haiku-5-5")
        runtime = AiRuntime(model, SpendCaps(1.0, 1.0, 1.0))
        run, _result = run_loop(s, arm.who("agent.ana"), case, runtime, context(), UserMessage("x"), [])
        assert run is not None and run.stop_reason == "budget_exhausted" and model.calls == 0


def test_a_live_runs_cost_is_recorded_as_it_goes(arm: ArmA) -> None:
    final = wants(
        SimpleNamespace(
            call_id="s",
            name="submit_recommendation",
            arguments=proposal(stay_ids=[], recommended_action="request_info", missing_information=["x"]),
        ),  # type: ignore[arg-type]
        input_tokens=1000,
        output_tokens=100,
    )
    with arm.sessions() as s:
        case = _case(arm, s)
        runtime = AiRuntime(LiveLike([final], model_id="claude-haiku-5-5"))
        run, result = run_loop(s, arm.who("agent.ana"), case, runtime, context(), UserMessage("x"), ["p@1"])
        assert result.stop is Stop.MISSING_INFORMATION
        assert run is not None and run.cost_microusd == 150 and run.is_mock is False
        assert spent_microusd(s, periods()[0]) == 150
        assert run.policy_versions == ["p@1"] and run.prompt_version == "arm_c_v1" and run.status == "finished"


def test_run_records_hold_no_evidence_and_no_secret(arm: ArmA) -> None:
    secretish = "sk-ant-should-never-be-stored"
    final = wants(
        SimpleNamespace(
            call_id="s",
            name="submit_recommendation",
            arguments=proposal(
                summary=secretish, stay_ids=[], recommended_action="request_info", missing_information=["x"]
            ),
        ),  # type: ignore[arg-type]
    )
    with arm.sessions() as s:
        case = _case(arm, s)
        run_loop(s, arm.who("agent.ana"), case, AiRuntime(ScriptedModel([final])), context(), UserMessage("x"), [])
        run = latest_run(s, case)
        assert run is not None
        steps = list(s.scalars(select(AiStep).where(AiStep.run_id == run.id)))
        assert steps
        stored = repr(run.__dict__) + repr([step.__dict__ for step in steps])
        assert secretish not in stored and "Ana Ruiz" not in stored
