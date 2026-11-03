"""App settings from environment variables (names in `.env.example`; checked by `python -m app.preflight`)."""

from __future__ import annotations

import os
from dataclasses import dataclass

HOSTED_PROFILES = ("staging", "approved")


def _flag(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() == "true"


@dataclass(frozen=True)
class AppSettings:
    database_url: str
    mock_api_url: str = "http://localhost:8020"
    mock_api_token: str = ""
    customer_id: str = "hg-demo"
    profile: str = "portfolio"
    sim_clock: bool = False
    public_demo_mode: bool = False

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies everywhere except plain-http local profiles (the stack binds to 127.0.0.1 only)."""
        return self.profile in HOSTED_PROFILES or self.public_demo_mode

    @classmethod
    def from_env(cls) -> AppSettings:
        return cls(
            database_url=os.environ["DATABASE_URL"],
            mock_api_url=os.environ.get("MOCK_API_URL", "http://localhost:8020"),
            mock_api_token=os.environ.get("MOCK_API_TOKEN", ""),
            customer_id=os.environ.get("APP_CUSTOMER_ID", "hg-demo"),
            profile=os.environ.get("APP_PROFILE", "portfolio"),
            sim_clock=_flag("MOCK_API_SIM_CLOCK"),
            public_demo_mode=_flag("PUBLIC_DEMO_MODE"),
        )
