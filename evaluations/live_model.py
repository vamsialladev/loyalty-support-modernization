"""A real model behind the owner's cap (RFC-0003; BENCH-10). Every call checks the ledger first, and is recorded after.

The check uses the most one call could cost, so the cap holds before the money is spent. When there's no room, the
call never happens: the model looks unavailable to the loop, the case keeps arm B's result, and the runner stops and
marks the run interrupted. An interrupted run is never extrapolated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.config import ModelPrice
from app.ports.model_provider import Message, ModelProvider, ModelTurn, ProviderRejected, ToolSpec, Usage
from evaluations.spend import LEDGER, CapReached, record, require_room

WORST_INPUT_TOKENS = 30_000  # well past the context limit plus the largest tool results, for one call
IMAGE_OUTPUT_TOKENS = 1_000


class GuardedModel:
    def __init__(
        self,
        inner: ModelProvider,
        price: ModelPrice,
        *,
        cap_usd: float,
        run_limit_usd: float,
        reserve_usd: float = 0.0,
        run_name: str = "evaluation",
        kind: str = "evaluation",
        ledger: Path = LEDGER,
    ) -> None:
        self.inner, self.price = inner, price
        self.cap_usd, self.run_limit_usd, self.reserve_usd = cap_usd, run_limit_usd, reserve_usd
        self.run_name, self.kind, self.ledger = run_name, kind, ledger
        self.name, self.model_id = inner.name, inner.model_id
        self.is_mock = False
        self.cost_microusd = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0
        self.stopped_because = ""

    @property
    def stopped(self) -> bool:
        return bool(self.stopped_because)

    def _admit(self, output_tokens: int) -> None:
        if self.stopped:
            raise ProviderRejected(self.stopped_because)
        worst = self.price.cost_microusd(WORST_INPUT_TOKENS, output_tokens) / 1_000_000
        if self.cost_microusd / 1_000_000 + worst > self.run_limit_usd:
            self.stopped_because = f"this run's limit of ${self.run_limit_usd:.2f} would be passed"
            raise ProviderRejected(self.stopped_because)
        try:
            require_room(worst, self.cap_usd, self.reserve_usd, self.ledger)
        except CapReached as exc:
            self.stopped_because = str(exc)
            raise ProviderRejected(self.stopped_because) from exc

    def _record(self, usage: Usage) -> None:
        cost = self.price.cost_microusd(usage.input_tokens, usage.output_tokens)
        self.cost_microusd += cost
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.calls += 1
        record(
            self.kind,
            self.run_name,
            self.model_id,
            usage.input_tokens,
            usage.output_tokens,
            cost / 1_000_000,
            self.ledger,
        )

    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec], max_tokens: int, timeout_seconds: float
    ) -> ModelTurn:
        self._admit(max_tokens)
        turn = self.inner.complete(system, messages, tools, max_tokens, timeout_seconds)
        self._record(turn.usage)
        return turn

    def read_image(
        self, media_type: str, content: bytes, timeout_seconds: float
    ) -> tuple[dict[str, str | None], Usage]:
        self._admit(IMAGE_OUTPUT_TOKENS)
        fields, usage = self.inner.read_image(media_type, content, timeout_seconds)
        self._record(usage)
        return fields, usage


def is_guarded(provider: Any) -> bool:
    return isinstance(provider, GuardedModel)
