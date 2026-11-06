"""Arm B's lists for one customer: nicknames and search synonyms (`config/conventional/<customer>.yaml`)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "conventional"


@dataclass(frozen=True)
class ConventionalConfig:
    nicknames: dict[str, frozenset[str]]
    synonyms: dict[str, str]

    @classmethod
    def load(cls, customer_id: str, config_dir: Path = CONFIG_DIR) -> ConventionalConfig:
        data = yaml.safe_load((config_dir / f"{customer_id}.yaml").read_text(encoding="utf-8"))
        nicknames = {name: frozenset(str(n) for n in forms) for name, forms in data["nicknames"].items()}
        return cls(nicknames, {str(k).lower(): str(v) for k, v in data["synonyms"].items()})


@lru_cache(maxsize=8)
def conventional_config(customer_id: str) -> ConventionalConfig:
    return ConventionalConfig.load(customer_id)
