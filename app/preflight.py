"""Configuration readiness per operating profile, without ever printing a value (spec B.2, Appendix K).

    python -m app.preflight --profile portfolio
    python -m app.preflight --profile live-model --json

Each known variable is reported as `set`, `missing` or `invalid format`, with where it came from (`environment`
or `.env`). The process environment overrides `.env`. Exit code 0 = the profile is ready, 1 = not ready,
2 = usage error. Decisions: ADR-0014.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

Check = Callable[[str], bool]

PROFILES_ALLOWED = ("portfolio", "live-model", "discovery", "staging", "approved", "enterprise-identity", "protocols")
PROVIDERS = ("mock", "anthropic", "bedrock", "moonshot", "zai", "dashscope")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "postgres"}


# ---------- format checks (pure; they see a value but never return or print it) ----------


def _nonempty(value: str) -> bool:
    return bool(value.strip())


def _min_len(n: int) -> Check:
    return lambda value: len(value.strip()) >= n


def _enum(*options: str) -> Check:
    return lambda value: value.strip() in options


def _bool(value: str) -> bool:
    return value.strip().lower() in {"true", "false"}


def _positive_number(value: str) -> bool:
    try:
        return float(value) > 0
    except ValueError:
        return False


def _regex(pattern: str) -> Check:
    compiled = re.compile(pattern)
    return lambda value: compiled.fullmatch(value.strip()) is not None


def _prefix(prefix: str, min_total: int) -> Check:
    return lambda value: value.startswith(prefix) and len(value) >= min_total


def _url(*schemes: str) -> Check:
    def check(value: str) -> bool:
        parts = urlsplit(value.strip())
        return parts.scheme in schemes and bool(parts.hostname)

    return check


def _postgres_url(value: str) -> bool:
    """A Postgres URL with a host, a user and a non-empty password (an empty one means POSTGRES_PASSWORD is unset)."""
    parts = urlsplit(value.strip())
    return (
        parts.scheme in {"postgresql", "postgresql+psycopg", "postgres"}
        and bool(parts.hostname)
        and bool(parts.username)
        and bool(parts.password)
    )


@dataclass(frozen=True)
class Var:
    name: str
    check: Check
    expected: str
    secret: bool = False


VARS: dict[str, Var] = {
    v.name: v
    for v in [
        Var("APP_PROFILE", _enum(*PROFILES_ALLOWED), "one of " + ", ".join(PROFILES_ALLOWED)),
        Var("APP_SECRET_KEY", _min_len(32), "at least 32 characters", secret=True),
        Var("PUBLIC_DEMO_MODE", _bool, "true or false"),
        Var("POSTGRES_USER", _nonempty, "non-empty"),
        Var("POSTGRES_PASSWORD", _min_len(8), "at least 8 characters", secret=True),
        Var("POSTGRES_DB", _nonempty, "non-empty"),
        Var("DATABASE_URL", _postgres_url, "postgresql URL with user, password and host", secret=True),
        Var("MOCK_API_DATABASE_URL", _postgres_url, "postgresql URL with user, password and host", secret=True),
        Var("MOCK_API_TOKEN", _min_len(12), "at least 12 characters", secret=True),
        Var("APP_DB_PASSWORD", _min_len(8), "at least 8 characters", secret=True),
        Var("APP_OWNER_DB_PASSWORD", _min_len(8), "at least 8 characters", secret=True),
        Var("MOCK_API_DB_PASSWORD", _min_len(8), "at least 8 characters", secret=True),
        Var("MOCK_API_URL", _url("http", "https"), "an http(s) URL"),
        Var("DEMO_USER_PASSWORD", _min_len(12), "at least 12 characters", secret=True),
        Var("MOCK_API_FAULTS", _bool, "true or false"),
        Var("MOCK_API_SIM_CLOCK", _bool, "true or false"),
        Var("AI_PROVIDER", _enum(*PROVIDERS), "one of " + ", ".join(PROVIDERS)),
        Var("ANTHROPIC_API_KEY", _prefix("sk-ant-", 24), "starts with sk-ant-", secret=True),
        Var("ANTHROPIC_MODEL", _regex(r"claude-[a-z0-9][a-z0-9.\-]*"), "an exact Claude model ID (claude-...)"),
        Var("LLM_BUDGET_USD_PER_RUN", _positive_number, "a positive number of US dollars"),
        Var("LLM_BUDGET_USD_TOTAL", _positive_number, "a positive number of US dollars"),
        Var("LLM_BUDGET_USD_DAILY", _positive_number, "a positive number of US dollars"),
        Var("AUTH_MODE", _enum("local", "oidc"), "local or oidc"),
        Var("APP_BASE_URL", _url("http", "https"), "an http(s) URL"),
        Var("RATE_LIMIT_PER_MINUTE", _positive_number, "a positive number"),
        Var("MAX_QUEUED_INVESTIGATIONS", _regex(r"[1-9]\d*"), "a whole number above 0"),
        Var("RETENTION_DAYS", _positive_number, "a positive number"),
        Var("SECURITY_EVENT_RETENTION_DAYS", _positive_number, "a positive number (30 or more)"),
        Var("AWS_PROFILE", _nonempty, "an AWS SSO profile name"),
        Var("AWS_REGION", _regex(r"[a-z]{2}(-gov)?-[a-z]+-\d"), "an AWS region such as us-east-1"),
        Var("BEDROCK_MODEL_ID", _regex(r"[A-Za-z0-9][A-Za-z0-9.:\-]+"), "a Bedrock model or inference-profile ID"),
        Var("MOONSHOT_API_KEY", _min_len(16), "at least 16 characters", secret=True),
        Var("ZAI_API_KEY", _min_len(16), "at least 16 characters", secret=True),
        Var("DASHSCOPE_API_KEY", _min_len(16), "at least 16 characters", secret=True),
        Var("LOCAL_MODEL_BASE_URL", _url("http", "https"), "an http(s) URL"),
        Var("OIDC_ISSUER_URL", _url("http", "https"), "an http(s) URL"),
        Var("OIDC_FETCH_URL", _url("http", "https"), "an http(s) URL"),
        Var("OIDC_CLIENT_ID", _nonempty, "non-empty"),
        Var("OIDC_CLIENT_SECRET", _min_len(16), "at least 16 characters", secret=True),
        Var("KEYCLOAK_ADMIN_PASSWORD", _min_len(12), "at least 12 characters", secret=True),
        Var("SUPABASE_URL", _url("https"), "an https URL"),
        Var("SUPABASE_PUBLISHABLE_KEY", _min_len(16), "at least 16 characters", secret=True),
        Var("SUPABASE_SECRET_KEY", _min_len(16), "at least 16 characters", secret=True),
        Var("SUPABASE_DB_URL", _postgres_url, "postgresql URL with user, password and host", secret=True),
        Var("GH_TOKEN", _regex(r"(github_pat_|ghp_)[A-Za-z0-9_]{20,}"), "a GitHub token (github_pat_...)", secret=True),
        Var("VERCEL_TOKEN", _min_len(16), "at least 16 characters", secret=True),
        Var("VERCEL_PROJECT_ID", _nonempty, "non-empty"),
        Var("VERCEL_ORG_ID", _nonempty, "non-empty"),
        Var("NEXT_PUBLIC_API_BASE_URL", _url("https"), "an https URL"),
        Var("MONDAY_API_TOKEN", _min_len(16), "at least 16 characters", secret=True),
        Var("MONDAY_BOARD_ID", _regex(r"\d+"), "digits"),
        Var("MIRO_ACCESS_TOKEN", _min_len(16), "at least 16 characters", secret=True),
        Var("MIRO_BOARD_ID", _nonempty, "non-empty"),
        Var("TELEGRAM_BOT_TOKEN", _regex(r"\d+:[A-Za-z0-9_\-]{30,}"), "a BotFather token", secret=True),
        Var("TELEGRAM_CHAT_ID", _regex(r"-?\d+"), "digits"),
        Var("OTEL_EXPORTER_OTLP_ENDPOINT", _url("http", "https"), "an http(s) URL"),
        Var("LOG_LEVEL", _enum("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), "DEBUG, INFO, WARNING, ERROR"),
        Var("LOG_FORMAT", _enum("json", "text"), "json or text"),
        Var("FEATURE_LIVE_AI", _bool, "true or false"),
        Var("FEATURE_ADJUSTMENT_EXECUTION", _bool, "true or false"),
        Var("FEATURE_PROTOCOL_LABS", _bool, "true or false"),
        Var("FEATURE_MCP", _bool, "true or false"),
        Var("FEATURE_A2A", _bool, "true or false"),
        Var("FEATURE_AG_UI", _bool, "true or false"),
        Var("PROTOCOL_TOKEN_ISSUER", _url("http", "https"), "an http(s) URL"),
        Var("PROTOCOL_TOKEN_FETCH_URL", _url("http", "https"), "an http(s) URL"),
        Var("MCP_HOST", _enum("127.0.0.1", "0.0.0.0"), "127.0.0.1, or 0.0.0.0 inside a container"),  # noqa: S104
        Var("MCP_PORT", _regex(r"\d{2,5}"), "a port number"),
        Var("MCP_RESOURCE_URL", _url("http", "https"), "an http(s) URL"),
        Var("A2A_SPECIALIST_HOST", _enum("127.0.0.1", "0.0.0.0"), "127.0.0.1, or 0.0.0.0 inside a container"),  # noqa: S104
        Var("A2A_SPECIALIST_PORT", _regex(r"\d{2,5}"), "a port number"),
        Var("A2A_SPECIALIST_URL", _url("http", "https"), "an http(s) URL"),
        Var("A2A_CALLBACK_BASES", _regex(r"https?://[^,\s]+(,https?://[^,\s]+)*"), "comma-separated http(s) URLs"),
        Var("A2A_CALLBACK_URL", _url("http", "https"), "an http(s) URL"),
        Var("A2A_COORDINATOR_CLIENT_ID", _nonempty, "non-empty"),
        Var("A2A_COORDINATOR_CLIENT_SECRET", _min_len(16), "at least 16 characters", secret=True),
    ]
}

SECRET_NAMES = frozenset(name for name, var in VARS.items() if var.secret)

PROVIDER_VARS: dict[str, tuple[str, ...]] = {
    "mock": (),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    "bedrock": ("AWS_PROFILE", "AWS_REGION", "BEDROCK_MODEL_ID"),
    "moonshot": ("MOONSHOT_API_KEY",),
    "zai": ("ZAI_API_KEY",),
    "dashscope": ("DASHSCOPE_API_KEY",),
}

_CORE = (
    "APP_PROFILE",
    "APP_SECRET_KEY",
    "PUBLIC_DEMO_MODE",
    "AI_PROVIDER",
    "LLM_BUDGET_USD_PER_RUN",
    "LLM_BUDGET_USD_TOTAL",
    "LOG_LEVEL",
    "FEATURE_LIVE_AI",
    "FEATURE_ADJUSTMENT_EXECUTION",
    "FEATURE_PROTOCOL_LABS",
)
_LOCAL_DB = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "APP_DB_PASSWORD",
    "APP_OWNER_DB_PASSWORD",
    "MOCK_API_DB_PASSWORD",
    "DATABASE_URL",
    "MOCK_API_DATABASE_URL",
    "MOCK_API_TOKEN",
    "DEMO_USER_PASSWORD",
)
_OIDC = ("OIDC_ISSUER_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET")
PROTOCOL_FLAGS = ("FEATURE_MCP", "FEATURE_A2A", "FEATURE_AG_UI")


# ---------- reading configuration ----------


@dataclass(frozen=True)
class Settings:
    """Known variable values and where each came from. Values stay in memory; nothing here prints them."""

    values: dict[str, str]
    sources: dict[str, str]
    unknown_in_file: tuple[str, ...] = ()
    reference_problems: tuple[str, ...] = ()


_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)")


def reference_problems(raw: Mapping[str, str | None], environ: Mapping[str, str]) -> list[str]:
    """`${NAME}` uses that will expand to a blank string, by name only.

    python-dotenv and Docker Compose both expand references top to bottom, so a variable used on a line above its own
    definition is blank at that point (unless the process environment supplies it).
    """
    order = {name: index for index, name in enumerate(raw)}
    problems = []
    for index, (name, value) in enumerate(raw.items()):
        for ref in dict.fromkeys(_REFERENCE.findall(value or "")):
            if environ.get(ref, "").strip():
                continue
            if ref not in order:
                problems.append(
                    f"{name} uses ${{{ref}}}, which is not defined in .env, so it expands to a blank string"
                )
            elif order[ref] > index:
                problems.append(
                    f"{name} uses ${{{ref}}} above the line that defines {ref}, so it expands to a blank string; "
                    f"move {ref} above {name} (scripts\\update-local-env.ps1 does this)"
                )
    return problems


def load_settings(env_file: Path | None, environ: Mapping[str, str]) -> Settings:
    file_values: dict[str, str] = {}
    unknown: list[str] = []
    references: list[str] = []
    if env_file is not None and env_file.is_file():
        references = reference_problems(dotenv_values(env_file, interpolate=False), environ)
        for key, value in dotenv_values(env_file).items():
            if key in VARS:
                file_values[key] = value or ""
            else:
                unknown.append(key)
    values: dict[str, str] = {}
    sources: dict[str, str] = {}
    for name in VARS:
        if environ.get(name, "").strip():
            values[name], sources[name] = environ[name], "environment"
        elif file_values.get(name, "").strip():
            values[name], sources[name] = file_values[name], ".env"
    return Settings(values, sources, tuple(sorted(unknown)), tuple(references))


# ---------- profiles ----------


def _flag(settings: Settings, name: str) -> bool:
    return settings.values.get(name, "").strip().lower() == "true"


def _provider(settings: Settings) -> str:
    return settings.values.get("AI_PROVIDER", "").strip()


def _required_for_provider(settings: Settings) -> tuple[str, ...]:
    return PROVIDER_VARS.get(_provider(settings), ())


def _is_local(url: str) -> bool:
    return (urlsplit(url.strip()).hostname or "") in LOCAL_HOSTS


def _check_provider_consistency(settings: Settings) -> list[str]:
    problems = []
    if _flag(settings, "FEATURE_LIVE_AI") and _provider(settings) == "mock":
        problems.append("FEATURE_LIVE_AI is true but AI_PROVIDER is mock: choose a provider or turn live AI off")
    return problems


def _check_test_switches(settings: Settings) -> list[str]:
    """Fault injection and the simulated clock are for tests and the benchmark only (ADR-0037, ADR-0038)."""
    if not _flag(settings, "PUBLIC_DEMO_MODE"):
        return []
    return [
        f"{name} must be false when PUBLIC_DEMO_MODE is true"
        for name in ("MOCK_API_FAULTS", "MOCK_API_SIM_CLOCK")
        if _flag(settings, name)
    ]


def _check_budgets(settings: Settings) -> list[str]:
    try:
        per_run = float(settings.values.get("LLM_BUDGET_USD_PER_RUN", ""))
        total = float(settings.values.get("LLM_BUDGET_USD_TOTAL", ""))
    except ValueError:
        return []
    if per_run > total:
        return ["LLM_BUDGET_USD_PER_RUN is larger than LLM_BUDGET_USD_TOTAL"]
    return []


def _check_live(settings: Settings) -> list[str]:
    problems = []
    if _provider(settings) in ("", "mock"):
        problems.append("live-model needs AI_PROVIDER set to a real provider, not mock")
    if not _flag(settings, "FEATURE_LIVE_AI"):
        problems.append("live-model needs FEATURE_LIVE_AI=true")
    return problems


def _check_hosted(settings: Settings) -> list[str]:
    problems = []
    for name in ("DATABASE_URL", "MOCK_API_DATABASE_URL"):
        if name in settings.values and _is_local(settings.values[name]):
            problems.append(f"{name} points at a local host; a hosted profile needs the managed database")
    if settings.values.get("LOG_LEVEL", "").strip() == "DEBUG":
        problems.append("LOG_LEVEL is DEBUG; hosted profiles must not run in debug mode")
    for name in ("MOCK_API_FAULTS", "MOCK_API_SIM_CLOCK"):
        if _flag(settings, name):
            problems.append(f"{name} must be false in a hosted profile (tests and benchmark only)")
    return problems


# Values that are someone's default, a template's or a test's: never acceptable outside a laptop (DEL-05, ADR-0075).
KNOWN_DEFAULTS = frozenset({"admin", "password", "changeme", "secret", "loyalty", "postgres", "test", "demo"})
DEFAULT_MARKERS = ("throwaway", "change-me", "changeme", "example", "check-only", "for-tests", "placeholder")
HOSTED_MIN_SECRET = 16


def _looks_default(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered in KNOWN_DEFAULTS or any(marker in lowered for marker in DEFAULT_MARKERS)


def _check_no_default_credentials(settings: Settings) -> list[str]:
    """Hosted profiles: no secret may be a known default, a template or test value, or short. Names only, never
    values. Database passwords are also checked inside the URLs that carry them."""
    problems = []
    for name in sorted(SECRET_NAMES):
        value = settings.values.get(name, "")
        if not value.strip():
            continue
        in_url = name.endswith(("DATABASE_URL", "_DB_URL"))
        secret = (urlsplit(value).password or "") if in_url else value
        if _looks_default(secret):
            problems.append(f"{name} looks like a default or test value; set a real secret in the platform's store")
        elif len(secret.strip()) < HOSTED_MIN_SECRET:
            problems.append(f"{name} is shorter than {HOSTED_MIN_SECRET} characters; hosted profiles need longer")
    return problems


def _check_protocols(settings: Settings) -> list[str]:
    """The protocol services need an issuer for their access tokens, and at least one of them switched on."""
    problems = []
    if not any(_flag(settings, name) for name in PROTOCOL_FLAGS):
        problems.append("protocols needs at least one of " + ", ".join(PROTOCOL_FLAGS) + " set to true")
    if not (settings.values.get("PROTOCOL_TOKEN_ISSUER") or settings.values.get("OIDC_ISSUER_URL")):
        problems.append("protocols needs PROTOCOL_TOKEN_ISSUER or OIDC_ISSUER_URL: tokens are checked against it")
    return problems


def _check_approved(settings: Settings) -> list[str]:
    problems = _check_hosted(settings)
    if settings.values.get("DEMO_USER_PASSWORD", "").strip():
        problems.append("DEMO_USER_PASSWORD must be empty in the approved profile: no shared demo accounts")
    issuer = settings.values.get("OIDC_ISSUER_URL", "")
    if issuer and urlsplit(issuer).scheme != "https":
        problems.append("OIDC_ISSUER_URL must use https in the approved profile")
    if _flag(settings, "PUBLIC_DEMO_MODE"):
        problems.append("PUBLIC_DEMO_MODE must be false in the approved profile")
    return problems


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    required: tuple[str, ...]
    checks: tuple[Callable[[Settings], list[str]], ...] = ()
    accepts_app_profile: tuple[str, ...] = field(default=())

    def app_profiles(self) -> tuple[str, ...]:
        return (self.name, *self.accepts_app_profile)


_COMMON_CHECKS = (_check_provider_consistency, _check_budgets, _check_test_switches)

PROFILES: dict[str, Profile] = {
    p.name: p
    for p in [
        Profile(
            "portfolio",
            "Default. Synthetic data, local mock APIs, offline mock AI unless a provider is chosen.",
            _CORE + _LOCAL_DB,
            _COMMON_CHECKS,
        ),
        Profile(
            "live-model",
            "Portfolio plus a live model with explicit credentials and budget caps.",
            _CORE + _LOCAL_DB,
            (*_COMMON_CHECKS, _check_live),
            accepts_app_profile=("portfolio",),
        ),
        Profile(
            "discovery",
            "Synthetic customer-shaped examples with configurable policies; no real customer connections.",
            _CORE + _LOCAL_DB,
            _COMMON_CHECKS,
        ),
        Profile(
            "staging",
            "Hosted staging: managed Postgres, Supabase, a public API URL for the frontend. Only once authorized.",
            (
                *_CORE,
                "DATABASE_URL",
                "MOCK_API_DATABASE_URL",
                "MOCK_API_TOKEN",
                "SUPABASE_URL",
                "SUPABASE_PUBLISHABLE_KEY",
                "SUPABASE_SECRET_KEY",
                "NEXT_PUBLIC_API_BASE_URL",
            ),
            (*_COMMON_CHECKS, _check_hosted, _check_no_default_credentials),
        ),
        Profile(
            "approved",
            "Approved deployment: enterprise identity, managed database, explicit model and telemetry destinations.",
            (*_CORE, "DATABASE_URL", "MOCK_API_DATABASE_URL", "MOCK_API_TOKEN", "OTEL_EXPORTER_OTLP_ENDPOINT", *_OIDC),
            (*_COMMON_CHECKS, _check_approved, _check_no_default_credentials),
        ),
        Profile(
            "enterprise-identity",
            "Portfolio plus the local OpenID Connect provider (Keycloak in Compose).",
            _CORE + _LOCAL_DB + _OIDC + ("KEYCLOAK_ADMIN_PASSWORD",),
            _COMMON_CHECKS,
            accepts_app_profile=("portfolio",),
        ),
        Profile(
            "protocols",
            "Portfolio plus the MCP, A2A and AG-UI services, with access tokens from the local Keycloak (RFC-0004).",
            _CORE + _LOCAL_DB + ("KEYCLOAK_ADMIN_PASSWORD",),
            (*_COMMON_CHECKS, _check_protocols),
            accepts_app_profile=("portfolio",),
        ),
    ]
}

# Feature or exercise -> the variables that unlock it (Appendix K2.5).
FEATURES: dict[str, tuple[str, ...]] = {
    "Offline demo (mock AI, local Postgres)": ("APP_SECRET_KEY", *_LOCAL_DB),
    "Live Claude runs (arm C live, live smoke test)": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    "Claude via Amazon Bedrock (configure only)": ("AWS_PROFILE", "AWS_REGION", "BEDROCK_MODEL_ID"),
    "Kimi exercise": ("MOONSHOT_API_KEY",),
    "GLM exercise": ("ZAI_API_KEY",),
    "Qwen exercise": ("DASHSCOPE_API_KEY",),
    "Local open model": ("LOCAL_MODEL_BASE_URL",),
    "Enterprise identity demo (Keycloak)": (*_OIDC, "KEYCLOAK_ADMIN_PASSWORD"),
    "Protocol services (MCP, A2A, AG-UI; tokens from Keycloak)": ("PROTOCOL_TOKEN_ISSUER", "KEYCLOAK_ADMIN_PASSWORD"),
    "A2A coordinator (its own Keycloak client)": ("A2A_COORDINATOR_CLIENT_ID", "A2A_COORDINATOR_CLIENT_SECRET"),
    "Supabase profile": ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "SUPABASE_DB_URL"),
    "GitHub API scripts": ("GH_TOKEN",),
    "Vercel deploy (only when authorized)": ("VERCEL_TOKEN", "VERCEL_PROJECT_ID", "VERCEL_ORG_ID"),
    "Monday.com exercise": ("MONDAY_API_TOKEN", "MONDAY_BOARD_ID"),
    "Miro exercise": ("MIRO_ACCESS_TOKEN", "MIRO_BOARD_ID"),
    "Telegram exercise": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"),
    "OpenTelemetry export to a collector (otherwise console)": ("OTEL_EXPORTER_OTLP_ENDPOINT",),
}


# ---------- the report ----------


def status_of(settings: Settings, name: str) -> str:
    if name not in settings.values:
        return "missing"
    return "set" if VARS[name].check(settings.values[name]) else "invalid format"


@dataclass(frozen=True)
class Report:
    profile: str
    required: dict[str, str]
    optional: dict[str, str]
    sources: dict[str, str]
    problems: list[str]
    features: dict[str, list[str]]
    unknown_in_file: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "ready": self.ready,
            "required": self.required,
            "optional": self.optional,
            "sources": self.sources,
            "problems": self.problems,
            "features": {
                name: ("unlocked" if not needs else {"blocked": needs}) for name, needs in self.features.items()
            },
            "unknown_in_file": list(self.unknown_in_file),
        }


def build_report(profile_name: str, settings: Settings) -> Report:
    profile = PROFILES[profile_name]
    required_names = list(dict.fromkeys(profile.required + _required_for_provider(settings)))
    required = {name: status_of(settings, name) for name in required_names}
    optional = {name: status_of(settings, name) for name in VARS if name not in required}

    problems = list(settings.reference_problems)
    problems += [
        f"{name} is {status} (expected {VARS[name].expected})" for name, status in required.items() if status != "set"
    ]
    for name, status in optional.items():
        if status == "invalid format":
            problems.append(f"{name} is set but has an invalid format (expected {VARS[name].expected})")
    app_profile = settings.values.get("APP_PROFILE", "").strip()
    if app_profile in PROFILES_ALLOWED and app_profile not in profile.app_profiles():
        problems.append(f"APP_PROFILE names a different profile than --profile {profile_name}")
    for check in profile.checks:
        problems.extend(check(settings))

    features = {
        feature: [name for name in needs if status_of(settings, name) != "set"] for feature, needs in FEATURES.items()
    }
    return Report(
        profile_name, required, optional, dict(settings.sources), problems, features, settings.unknown_in_file
    )


def render_text(report: Report) -> str:
    lines = [
        f"Preflight - profile: {report.profile}",
        PROFILES[report.profile].description,
        "Values are never printed. Status only: set / missing / invalid format.",
        "",
        "Required for this profile",
    ]
    width = max(len(name) for name in VARS) + 2
    for name, status in report.required.items():
        lines.append(f"  {name:<{width}}{status:<16}{report.sources.get(name, '-')}")
    lines += ["", "Optional (unlock features and exercises)"]
    for name, status in report.optional.items():
        lines.append(f"  {name:<{width}}{status:<16}{report.sources.get(name, '-')}")
    lines += ["", "Features and exercises"]
    for feature, needs in report.features.items():
        lines.append(f"  unlocked  {feature}" if not needs else f"  blocked   {feature}: needs {', '.join(needs)}")
    if report.unknown_in_file:
        lines += ["", "Unknown names in .env (typo?): " + ", ".join(report.unknown_in_file)]
    lines.append("")
    if report.ready:
        lines.append("Result: READY")
    else:
        lines.append(f"Result: NOT READY ({len(report.problems)} problem{'s' if len(report.problems) != 1 else ''})")
        lines += [f"  - {problem}" for problem in report.problems]
    return "\n".join(lines)


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.preflight", description="Configuration readiness per profile; never prints values."
    )
    parser.add_argument(
        "--profile", choices=PROFILES_ALLOWED, default=None, help="defaults to APP_PROFILE, then portfolio"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="default: .env in the current folder")
    parser.add_argument("--json", action="store_true", help="machine-readable output (still no values)")
    args = parser.parse_args(argv)

    settings = load_settings(args.env_file, os.environ if environ is None else environ)
    profile = args.profile or settings.values.get("APP_PROFILE", "").strip() or "portfolio"
    if profile not in PROFILES:
        profile = "portfolio"
    report = build_report(profile, settings)
    print(json.dumps(report.as_dict(), indent=2) if args.json else render_text(report))
    return 0 if report.ready else 1


if __name__ == "__main__":
    sys.exit(main())
