"""The loop's limits, the allowed models and the versioned prompt (`config/ai/`, `config/prompts/`)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.ports.model_provider import Usage

ROOT = Path(__file__).resolve().parents[2]
MICRO = 1_000_000


@dataclass(frozen=True)
class Limits:
    max_turns: int = 6
    max_tool_calls_per_turn: int = 4
    parallel_reads: int = 4
    max_identical_calls: int = 2
    deadline_seconds: float = 60.0
    call_timeout_seconds: float = 30.0
    max_provider_failures: int = 2
    max_repairs: int = 1
    max_output_tokens: int = 2000
    context_chars: int = 8000
    tool_result_chars: int = 4000


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float
    checked_on: str
    deprecated: bool = False
    retires_on: str | None = None  # the provider's published retirement date, if any (ENT-15, app/ai/lifecycle.py)
    # Prompt caching (L3, ADR-0091): the 5-minute write rate and the read rate. Left out, cached tokens are charged at
    # twice the input price, the most any cache write costs (the 1-hour rate), so a cap can't be passed by caching.
    cache_write_per_mtok: float | None = None
    cache_read_per_mtok: float | None = None

    @property
    def _unknown_cache_rate(self) -> float:
        return 2 * self.input_per_mtok

    @property
    def worst_input_per_mtok(self) -> float:
        """The most one input token can cost when caching is asked for: the check before a call uses it."""
        rates = (self.input_per_mtok, self.cache_write_per_mtok, self.cache_read_per_mtok)
        known = [r for r in rates if r is not None]
        if self.cache_write_per_mtok is None or self.cache_read_per_mtok is None:
            known.append(self._unknown_cache_rate)
        return max(known)

    def cost_microusd(self, input_tokens: int, output_tokens: int, *, cache_read: int = 0, cache_write: int = 0) -> int:
        """Rounded up, so a cap can't be passed by rounding. `input_tokens` is the uncached part, as the provider
        reports it; cache reads and writes are counted on top."""
        read_rate = self._unknown_cache_rate if self.cache_read_per_mtok is None else self.cache_read_per_mtok
        write_rate = self._unknown_cache_rate if self.cache_write_per_mtok is None else self.cache_write_per_mtok
        dollars_micro = (
            input_tokens * self.input_per_mtok
            + output_tokens * self.output_per_mtok
            + cache_read * read_rate
            + cache_write * write_rate
        )
        return int(dollars_micro) + (0 if dollars_micro == int(dollars_micro) else 1)

    def usage_cost_microusd(self, usage: Usage) -> int:
        return self.cost_microusd(
            usage.input_tokens,
            usage.output_tokens,
            cache_read=usage.cache_read_tokens,
            cache_write=usage.cache_write_tokens,
        )


@dataclass(frozen=True)
class AiConfig:
    limits: Limits
    models: dict[str, ModelPrice]


@lru_cache(maxsize=8)
def ai_config(customer_id: str) -> AiConfig:
    data = yaml.safe_load((ROOT / "config/ai" / f"{customer_id}.yaml").read_text(encoding="utf-8"))
    models = {name: ModelPrice(**values) for name, values in data["models"].items()}
    return AiConfig(Limits(**data["limits"]), models)


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str


@lru_cache(maxsize=8)
def load_prompt(name: str = "arm_c_v1") -> Prompt:
    source = (ROOT / "config/prompts" / f"{name}.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    _empty, front, body = source.split("---\n", 2)
    return Prompt(str(yaml.safe_load(front)["version"]), body.strip())
