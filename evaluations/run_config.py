"""What one benchmark run is configured to do (spec E.3; BENCH-02), and the limits nothing may exceed.

A configuration is checked before a run starts, so a live run with no ceiling, or a ceiling above the owner's cap, never
begins. Mock and live are kept apart here too (spec E.5): a mock configuration can't hold a cost ceiling, because it
spends nothing, and a live one must.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "benchmarks" / "configs"
THRESHOLDS = ROOT / "benchmarks" / "benchmark-thresholds.yaml"
ARMS = ("A", "A_as_is", "B", "C")
SPLITS = ("dev", "validation", "heldout", "stress", "fairness")
PROVIDERS = ("none", "mock", "live")
REQUIRED = (
    "dataset_version",
    "arm",
    "provider",
    "model",
    "prompt_version",
    "retrieval",
    "tool_permissions",
    "limits",
    "timeout_retry",
    "concurrency",
    "repetitions",
    "cost_ceiling_usd",
    "environment",
    "cache_state",
)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RunConfig:
    name: str
    dataset_version: str
    arm: str
    provider: str
    model: str | None
    prompt_version: str | None
    retrieval: str
    tool_permissions: str
    limits: str
    timeout_retry: str
    concurrency: int
    repetitions: int
    cost_ceiling_usd: float | None
    environment: str
    cache_state: str

    @property
    def kind(self) -> str:
        """The folder a run's results go in. Deterministic, mock and live results are never mixed."""
        return {"none": "deterministic", "mock": "mock", "live": "live"}[self.provider]


def hard_cap_usd(path: Path = THRESHOLDS) -> float:
    """The owner's cap on all live spending, smoke test and evaluation together."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return float(data["live_spend"]["hard_cap_total_usd"])


def check(config: RunConfig, cap_usd: float) -> None:
    """Raises ConfigError for anything that mustn't run. Nothing here depends on a setting being right elsewhere."""
    if config.arm not in ARMS:
        raise ConfigError(f"unknown arm {config.arm}")
    if config.provider not in PROVIDERS:
        raise ConfigError(f"unknown provider {config.provider}")
    if config.arm == "C" and config.provider == "none":
        raise ConfigError("arm C needs a provider: mock or live")
    if config.arm != "C" and config.provider != "none":
        raise ConfigError(f"arm {config.arm} doesn't use a model")
    if config.provider == "live":
        if not config.model:
            raise ConfigError("a live run names its model")
        if config.cost_ceiling_usd is None or config.cost_ceiling_usd <= 0:
            raise ConfigError("a live run needs a cost ceiling")
        if config.cost_ceiling_usd > cap_usd:
            raise ConfigError(f"the ceiling is above the owner's cap of ${cap_usd:.2f}")
    elif config.cost_ceiling_usd is not None:
        raise ConfigError("only a live run spends money, so only a live run has a ceiling")
    if config.concurrency < 1 or config.repetitions < 1:
        raise ConfigError("concurrency and repetitions start at 1")


def load(name: str, config_dir: Path = CONFIG_DIR, cap_usd: float | None = None) -> RunConfig:
    data = yaml.safe_load((config_dir / f"{name}.yaml").read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED if field not in data]
    if missing:
        raise ConfigError(f"{name} is missing {', '.join(missing)}")
    config = RunConfig(name=name, **{field: data[field] for field in REQUIRED})
    check(config, hard_cap_usd() if cap_usd is None else cap_usd)
    return config
