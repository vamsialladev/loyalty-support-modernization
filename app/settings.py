"""App settings from environment variables (names in `.env.example`; checked by `python -m app.preflight`)."""

from __future__ import annotations

import os
from dataclasses import dataclass

HOSTED_PROFILES = ("staging", "approved")


def _flag(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() == "true"


def _number(name: str, default: float) -> float:
    """A cap that doesn't parse counts as zero, so nothing live runs on a typo."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return 0.0


@dataclass(frozen=True)
class AppSettings:
    database_url: str
    mock_api_url: str = "http://localhost:8020"
    mock_api_token: str = ""
    customer_id: str = "hg-demo"
    profile: str = "portfolio"
    sim_clock: bool = False
    public_demo_mode: bool = False
    secret_key: str = ""
    worker_health_file: str = ""
    ai_provider: str = "mock"
    feature_live_ai: bool = False
    anthropic_model: str = ""
    ai_budget_per_run_usd: float = 1.0
    ai_budget_daily_usd: float = 5.0
    ai_budget_total_usd: float = 5.0
    auth_mode: str = "local"  # local | oidc
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    app_base_url: str = "http://127.0.0.1:8010"
    rate_limit_per_minute: int = 600
    feature_mcp: bool = False  # spec G.2: each protocol has its own flag, off by default (RFC-0004)
    feature_a2a: bool = False
    feature_ag_ui: bool = False
    protocol_token_issuer: str = ""  # who issues protocol access tokens; empty means OIDC_ISSUER_URL

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
            secret_key=os.environ.get("APP_SECRET_KEY", ""),
            worker_health_file=os.environ.get("WORKER_HEALTH_FILE", ""),
            ai_provider=os.environ.get("AI_PROVIDER", "mock").strip() or "mock",
            feature_live_ai=_flag("FEATURE_LIVE_AI"),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "").strip(),
            ai_budget_per_run_usd=_number("LLM_BUDGET_USD_PER_RUN", 1.0),
            ai_budget_daily_usd=_number("LLM_BUDGET_USD_DAILY", _number("LLM_BUDGET_USD_TOTAL", 5.0)),
            ai_budget_total_usd=_number("LLM_BUDGET_USD_TOTAL", 5.0),
            auth_mode=os.environ.get("AUTH_MODE", "local").strip() or "local",
            oidc_issuer_url=os.environ.get("OIDC_ISSUER_URL", "").strip(),
            oidc_client_id=os.environ.get("OIDC_CLIENT_ID", "").strip(),
            oidc_client_secret=os.environ.get("OIDC_CLIENT_SECRET", ""),
            app_base_url=os.environ.get("APP_BASE_URL", "http://127.0.0.1:8010").strip().rstrip("/"),
            rate_limit_per_minute=int(_number("RATE_LIMIT_PER_MINUTE", 600)),
            feature_mcp=_flag("FEATURE_MCP"),
            feature_a2a=_flag("FEATURE_A2A"),
            feature_ag_ui=_flag("FEATURE_AG_UI"),
            protocol_token_issuer=(
                os.environ.get("PROTOCOL_TOKEN_ISSUER", "").strip() or os.environ.get("OIDC_ISSUER_URL", "").strip()
            ),
        )
