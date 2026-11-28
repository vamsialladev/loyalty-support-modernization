"""The drill-only mock model faults (docs/drills.md D1 and D6): `MOCK_MODEL_FAULT` makes the mock fail on purpose,
and does nothing with a live provider or in the public demo."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.adapters.mock_model import DrillFaultModel, RulesMockModel
from app.ports.model_provider import MODEL_WANTS_TOOLS, ModelTurn, ProviderUnavailable, ToolCall, Usage
from app.services.assisted import runtime_from_settings
from app.settings import AppSettings


class Fixed:
    name, model_id, is_mock = "mock", "mock-rules-v1", True

    def __init__(self, turn: ModelTurn) -> None:
        self.turn = turn

    def complete(self, *args: Any, **kwargs: Any) -> ModelTurn:
        return self.turn

    def read_image(self, *args: Any) -> tuple[dict[str, str | None], Usage]:
        return {"confirmation": "BR-6638"}, Usage()


def proposal(action: str) -> ModelTurn:
    return ModelTurn(
        MODEL_WANTS_TOOLS,
        "",
        (
            ToolCall("a", "get_member", {}),
            ToolCall("b", "submit_recommendation", {"recommended_action": action, "stay_ids": ["BR-6638"]}),
        ),
    )


def test_unavailable_fails_every_call_as_an_outage() -> None:
    model = DrillFaultModel(Fixed(proposal("adjust")), "unavailable")
    with pytest.raises(ProviderUnavailable):
        model.complete("system", [], [], 100, 5.0)
    with pytest.raises(ProviderUnavailable):
        model.read_image("image/png", b"x", 5.0)


@pytest.mark.parametrize(
    ("engine_says", "model_says"),
    [("adjust", "no_adjustment_credited"), ("no_adjustment_credited", "adjust"), ("deny", "adjust")],
)
def test_wrong_action_names_the_opposite_and_touches_nothing_else(engine_says: str, model_says: str) -> None:
    model = DrillFaultModel(Fixed(proposal(engine_says)), "wrong_action")
    turn = model.complete("system", [], [], 100, 5.0)
    member, submitted = turn.tool_calls
    assert member == ToolCall("a", "get_member", {})
    assert submitted.arguments == {"recommended_action": model_says, "stay_ids": ["BR-6638"]}
    assert model.is_mock and model.model_id == "mock-rules-v1+drill-wrong_action"


def test_an_unknown_fault_fails_loudly() -> None:
    with pytest.raises(ValueError, match="unknown MOCK_MODEL_FAULT"):
        DrillFaultModel(Fixed(proposal("adjust")), "slow")


def settings(**changes: Any) -> AppSettings:
    return dataclasses.replace(AppSettings(database_url="sqlite://"), **changes)


def test_the_fault_wraps_the_mock_only_and_never_in_the_public_demo() -> None:
    assert isinstance(runtime_from_settings(settings()).provider, RulesMockModel)
    wrapped = runtime_from_settings(settings(mock_model_fault="unavailable")).provider
    assert isinstance(wrapped, DrillFaultModel) and wrapped.fault == "unavailable"
    in_demo = runtime_from_settings(settings(mock_model_fault="unavailable", public_demo_mode=True)).provider
    assert isinstance(in_demo, RulesMockModel)  # the public demo ignores it
    live = runtime_from_settings(settings(ai_provider="anthropic", mock_model_fault="unavailable")).provider
    assert not isinstance(live, DrillFaultModel)  # a live provider is never wrapped


def test_the_setting_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("MOCK_MODEL_FAULT", " wrong_action ")
    assert AppSettings.from_env().mock_model_fault == "wrong_action"
    monkeypatch.delenv("MOCK_MODEL_FAULT")
    assert AppSettings.from_env().mock_model_fault == ""
