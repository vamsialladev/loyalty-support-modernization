"""The guard around a real model: nothing reaches the provider past the cap (BENCH-10; RFC-0003). No network here."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.ai.config import ModelPrice
from app.ports.model_provider import ModelTurn, ProviderRejected, Usage, UserMessage
from evaluations.live_model import WORST_INPUT_TOKENS, GuardedModel
from evaluations.spend import record, spent_usd

PRICE = ModelPrice(0.10, 0.50, "2026-11-06")
WORST = PRICE.cost_microusd(WORST_INPUT_TOKENS, 2000) / 1_000_000


class CountingModel:
    name, model_id, is_mock = "fake", "m", False

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *_args: Any) -> ModelTurn:
        self.calls += 1
        return ModelTurn("end_turn", usage=Usage(1000, 100))

    def read_image(self, *_args: Any) -> tuple[dict[str, str | None], Usage]:
        self.calls += 1
        return {"confirmation": "BR-1"}, Usage(500, 50)


def guarded(ledger: Path, inner: CountingModel, **over: Any) -> GuardedModel:
    settings: dict[str, Any] = {"cap_usd": 5.0, "run_limit_usd": 2.0, "ledger": ledger, "run_name": "r"}
    return GuardedModel(inner, PRICE, **(settings | over))


def call(model: GuardedModel) -> ModelTurn:
    return model.complete("system", [UserMessage("hi")], [], 2000, 30.0)


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    return tmp_path / "ledger.jsonl"


def test_a_call_is_recorded_in_the_ledger(ledger: Path) -> None:
    model = guarded(ledger, CountingModel())
    call(model)
    assert spent_usd(ledger) == pytest.approx(0.00015)
    assert (model.input_tokens, model.output_tokens, model.calls) == (1000, 100, 1)


def test_an_image_read_is_recorded_too(ledger: Path) -> None:
    model = guarded(ledger, CountingModel())
    model.read_image("image/png", b"x", 30.0)
    assert spent_usd(ledger) > 0


def test_no_call_reaches_the_provider_past_the_cap(ledger: Path) -> None:
    record("evaluation", "earlier", "m", 1, 1, 5.0 - WORST / 2, ledger)
    inner = CountingModel()
    model = guarded(ledger, inner)
    with pytest.raises(ProviderRejected):
        call(model)
    assert inner.calls == 0 and model.stopped


def test_once_stopped_it_stays_stopped(ledger: Path) -> None:
    record("evaluation", "earlier", "m", 1, 1, 5.0, ledger)
    inner = CountingModel()
    model = guarded(ledger, inner)
    for _ in range(3):
        with pytest.raises(ProviderRejected):
            call(model)
    assert inner.calls == 0


def test_a_run_stops_at_its_own_limit(ledger: Path) -> None:
    inner = CountingModel()
    model = guarded(ledger, inner, run_limit_usd=WORST * 0.5)
    with pytest.raises(ProviderRejected, match="run's limit"):
        call(model)
    assert inner.calls == 0


def test_dev_work_cant_reach_the_held_out_reserve(ledger: Path) -> None:
    record("evaluation", "dev", "m", 1, 1, 2.5, ledger)
    inner = CountingModel()
    with pytest.raises(ProviderRejected, match="reserved"):
        call(guarded(ledger, inner, reserve_usd=2.5))
    assert inner.calls == 0


def test_held_out_can_use_the_reserve(ledger: Path) -> None:
    record("evaluation", "dev", "m", 1, 1, 2.5, ledger)
    inner = CountingModel()
    call(guarded(ledger, inner, reserve_usd=0.0))
    assert inner.calls == 1


def test_it_says_it_isnt_a_mock(ledger: Path) -> None:
    assert guarded(ledger, CountingModel()).is_mock is False
