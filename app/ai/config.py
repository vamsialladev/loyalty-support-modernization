"""The loop's limits, the allowed models and the versioned prompt (`config/ai/`, `config/prompts/`)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

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

    def cost_microusd(self, input_tokens: int, output_tokens: int) -> int:
        """Rounded up, so a cap can't be passed by rounding."""
        dollars_micro = input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok
        return int(dollars_micro) + (0 if dollars_micro == int(dollars_micro) else 1)


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
