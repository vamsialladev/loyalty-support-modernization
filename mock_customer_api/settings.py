"""Settings from environment variables (names in `.env.example`). No secret value is ever logged."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() == "true"


@dataclass(frozen=True)
class Settings:
    database_url: str
    token: str
    customer_id: str = "hg-demo"
    faults_enabled: bool = False
    sim_clock_enabled: bool = False
    public_demo_mode: bool = False
    seed_dir: Path = Path("seed_data/v1")
    fault_rules_file: Path | None = None
    timeout_fault_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> Settings:
        rules = os.environ.get("MOCK_API_FAULT_RULES_FILE", "").strip()
        return cls(
            database_url=os.environ["MOCK_API_DATABASE_URL"],
            token=os.environ["MOCK_API_TOKEN"],
            customer_id=os.environ.get("MOCK_API_CUSTOMER_ID", "hg-demo"),
            faults_enabled=_flag("MOCK_API_FAULTS"),
            sim_clock_enabled=_flag("MOCK_API_SIM_CLOCK"),
            public_demo_mode=_flag("PUBLIC_DEMO_MODE"),
            seed_dir=Path(os.environ.get("MOCK_API_SEED_DIR", "seed_data/v1")),
            fault_rules_file=Path(rules) if rules else None,
            timeout_fault_seconds=float(os.environ.get("MOCK_API_TIMEOUT_FAULT_SECONDS", "5")),
        )

    def __post_init__(self) -> None:
        if self.public_demo_mode and (self.faults_enabled or self.sim_clock_enabled):
            raise ValueError("MOCK_API_FAULTS and MOCK_API_SIM_CLOCK must be false when PUBLIC_DEMO_MODE is true")
