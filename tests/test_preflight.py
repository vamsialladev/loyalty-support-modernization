"""Preflight: readiness per profile, and no value ever reaches the output (spec B.2, Appendix K)."""

import json
from pathlib import Path

import pytest
from dotenv import dotenv_values

from app import preflight
from app.preflight import PROFILES, VARS, build_report, load_settings, main

ROOT = Path(__file__).resolve().parent.parent

# Valid-looking, obviously fake values. Each is distinctive so a leak into the output is easy to spot.
FAKE = {
    "APP_PROFILE": "portfolio",
    "APP_SECRET_KEY": "fake-app-secret-key-0123456789abcdefghijklmnop",
    "PUBLIC_DEMO_MODE": "false",
    "POSTGRES_USER": "loyalty",
    "POSTGRES_PASSWORD": "fake-pg-password-7781",
    "POSTGRES_DB": "loyalty",
    "DATABASE_URL": "postgresql+psycopg://loyalty:fake-pg-password-7781@localhost:5432/loyalty",
    "MOCK_API_DATABASE_URL": "postgresql+psycopg://loyalty:fake-pg-password-7781@localhost:5432/mock_customer_api",
    "MOCK_API_TOKEN": "fake-mock-api-token-4410",
    "DEMO_USER_PASSWORD": "fake-demo-user-password-6633",
    "APP_DB_PASSWORD": "fake-app-db-password-2211",
    "MOCK_API_DB_PASSWORD": "fake-mock-db-password-3322",
    "MOCK_API_URL": "http://fake-mock-api.test:8020",
    "MOCK_API_FAULTS": "false",
    "MOCK_API_SIM_CLOCK": "false",
    "AI_PROVIDER": "mock",
    "ANTHROPIC_API_KEY": "sk-ant-fake-key-do-not-use-000000000000",
    "ANTHROPIC_MODEL": "claude-haiku-5-5",
    "LLM_BUDGET_USD_PER_RUN": "1.00",
    "LLM_BUDGET_USD_TOTAL": "5.00",
    "AWS_PROFILE": "fake-sso-profile-name",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "fake.bedrock-model-id-v1:0",
    "MOONSHOT_API_KEY": "fake-moonshot-key-12345678",
    "ZAI_API_KEY": "fake-zai-key-1234567890ab",
    "DASHSCOPE_API_KEY": "fake-dashscope-key-12345678",
    "LOCAL_MODEL_BASE_URL": "http://fake-local-model.test:8000/v1",
    "OIDC_ISSUER_URL": "https://fake-issuer.test/realms/loyalty",
    "OIDC_CLIENT_ID": "fake-loyalty-console-client",
    "OIDC_CLIENT_SECRET": "fake-oidc-client-secret-998877",
    "KEYCLOAK_ADMIN_PASSWORD": "fake-keycloak-admin-5566",
    "SUPABASE_URL": "https://fakeproject.supabase.test",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_fake_123456789",
    "SUPABASE_SECRET_KEY": "sb_secret_fake_1234567890abc",
    "SUPABASE_DB_URL": "postgresql://postgres:fake-supabase-db-pass@db.fake.supabase.test:5432/postgres",
    "GH_TOKEN": "github_pat_fake_token_abcdefghijklmnop123",
    "VERCEL_TOKEN": "fake-vercel-token-123456789",
    "VERCEL_PROJECT_ID": "prj_fake_project_id",
    "VERCEL_ORG_ID": "team_fake_org_id",
    "NEXT_PUBLIC_API_BASE_URL": "https://fake-api.loyalty.test",
    "MONDAY_API_TOKEN": "fake-monday-token-123456789",
    "MONDAY_BOARD_ID": "4815162342",
    "MIRO_ACCESS_TOKEN": "fake-miro-token-1234567890",
    "MIRO_BOARD_ID": "fake-miro-board-uXjVfake",
    "TELEGRAM_BOT_TOKEN": "123456789:FAKE_telegram_bot_token_abcdefghijk",
    "TELEGRAM_CHAT_ID": "987654321",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://fake-otel-collector.test:4318",
    "LOG_LEVEL": "INFO",
    "FEATURE_LIVE_AI": "false",
    "FEATURE_ADJUSTMENT_EXECUTION": "true",
    "FEATURE_PROTOCOL_LABS": "false",
}

PORTFOLIO_KEYS = [
    "APP_PROFILE",
    "APP_SECRET_KEY",
    "PUBLIC_DEMO_MODE",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "APP_DB_PASSWORD",
    "MOCK_API_DB_PASSWORD",
    "DATABASE_URL",
    "MOCK_API_DATABASE_URL",
    "MOCK_API_TOKEN",
    "DEMO_USER_PASSWORD",
    "AI_PROVIDER",
    "LLM_BUDGET_USD_PER_RUN",
    "LLM_BUDGET_USD_TOTAL",
    "LOG_LEVEL",
    "FEATURE_LIVE_AI",
    "FEATURE_ADJUSTMENT_EXECUTION",
    "FEATURE_PROTOCOL_LABS",
]


def settings_from(values: dict[str, str], environ: dict[str, str] | None = None, tmp_path: Path | None = None):
    if tmp_path is None:
        return load_settings(None, values)
    env = tmp_path / ".env"
    env.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return load_settings(env, environ or {})


def portfolio(**overrides: str) -> dict[str, str]:
    values = {k: FAKE[k] for k in PORTFOLIO_KEYS}
    values.update(overrides)
    return values


def test_all_six_profiles_defined():
    assert set(PROFILES) == {"portfolio", "live-model", "discovery", "staging", "approved", "enterprise-identity"}
    assert set(preflight.PROFILES_ALLOWED) == set(PROFILES)


def test_fake_values_pass_every_format_check():
    # Guards the leak test below: every variable must be exercised as "set", not skipped as invalid.
    assert set(FAKE) == set(VARS)
    assert [name for name, value in FAKE.items() if not VARS[name].check(value)] == []


@pytest.mark.parametrize("as_json", [False, True])
def test_output_never_contains_values(tmp_path, capsys, as_json):
    env = tmp_path / ".env"
    env.write_text("".join(f"{k}={v}\n" for k, v in FAKE.items()), encoding="utf-8")
    for profile in PROFILES:
        main(["--profile", profile, "--env-file", str(env)] + (["--json"] if as_json else []), environ={})
        out = capsys.readouterr().out
        # APP_PROFILE's value is a profile name the report shows by design; short enum-like values (true, INFO,
        # mock) are too short to search for. Every other value must be absent.
        leaked = [name for name, value in FAKE.items() if name != "APP_PROFILE" and len(value) >= 6 and value in out]
        assert leaked == [], f"values of {leaked} appeared in the {profile} output"


def test_template_env_is_not_ready_and_lists_missing(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    code = main(["--profile", "portfolio", "--env-file", str(env)], environ={})
    out = capsys.readouterr().out
    assert code == 1
    assert "APP_SECRET_KEY" in out and "missing" in out
    assert "NOT READY" in out


def test_template_names_match_known_variables():
    template = dotenv_values(ROOT / ".env.example")
    assert set(template) == set(VARS), "every .env.example name is checked by preflight, and vice versa"


def test_template_inline_comments_are_not_values():
    template = dotenv_values(ROOT / ".env.example")
    assert template["APP_PROFILE"] == "portfolio"
    assert template["AI_PROVIDER"] == "mock"
    assert template["ANTHROPIC_API_KEY"] in ("", None)


def test_portfolio_ready_with_local_values():
    report = build_report("portfolio", settings_from(portfolio()))
    assert report.problems == []
    assert report.ready


def test_missing_secret_key_is_not_ready():
    values = portfolio()
    del values["APP_SECRET_KEY"]
    report = build_report("portfolio", settings_from(values))
    assert report.required["APP_SECRET_KEY"] == "missing"
    assert not report.ready


def test_empty_postgres_password_makes_database_url_invalid(tmp_path):
    env = tmp_path / ".env"
    lines = [f"{k}={v}" for k, v in portfolio().items() if k not in ("POSTGRES_PASSWORD", "DATABASE_URL")]
    lines += [
        "POSTGRES_PASSWORD=",
        "DATABASE_URL=postgresql+psycopg://loyalty:${POSTGRES_PASSWORD}@localhost:5432/loyalty",
    ]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = build_report("portfolio", load_settings(env, {}))
    assert report.required["POSTGRES_PASSWORD"] == "missing"
    assert report.required["DATABASE_URL"] == "invalid format"


PER_ROLE_URLS = [
    "DATABASE_URL=postgresql+psycopg://loyalty_app:${APP_DB_PASSWORD}@localhost:5432/loyalty",
    "MOCK_API_DATABASE_URL=postgresql+psycopg://mock_api:${MOCK_API_DB_PASSWORD}@localhost:5432/mock_customer_api",
]
ROLE_PASSWORDS = [f"APP_DB_PASSWORD={FAKE['APP_DB_PASSWORD']}", f"MOCK_API_DB_PASSWORD={FAKE['MOCK_API_DB_PASSWORD']}"]
URL_AND_ROLE_KEYS = ("DATABASE_URL", "MOCK_API_DATABASE_URL", "APP_DB_PASSWORD", "MOCK_API_DB_PASSWORD")


def write_per_role_env(tmp_path: Path, tail: list[str]) -> Path:
    env = tmp_path / ".env"
    head = [f"{k}={v}" for k, v in portfolio().items() if k not in URL_AND_ROLE_KEYS]
    env.write_text("\n".join(head + tail) + "\n", encoding="utf-8")
    return env


def test_per_role_urls_are_ready_when_the_passwords_are_defined_first(tmp_path):
    # The .env.example form since Milestone 4 (ADR-0036): each URL takes its role's password by reference.
    env = write_per_role_env(tmp_path, ROLE_PASSWORDS + PER_ROLE_URLS)
    report = build_report("portfolio", load_settings(env, {}))
    assert report.required["DATABASE_URL"] == "set"
    assert report.required["MOCK_API_DATABASE_URL"] == "set"
    assert report.problems == []


def test_per_role_urls_above_their_passwords_name_the_cause(tmp_path, capsys):
    # The bug from the owner's first run (verification log): update-local-env.ps1 appended the role passwords
    # below the URL lines, so ${APP_DB_PASSWORD} expanded to a blank string.
    env = write_per_role_env(tmp_path, PER_ROLE_URLS + ROLE_PASSWORDS)
    report = build_report("portfolio", load_settings(env, {}))
    assert report.required["DATABASE_URL"] == "invalid format"
    assert report.required["APP_DB_PASSWORD"] == "set"
    assert any("DATABASE_URL uses ${APP_DB_PASSWORD} above the line that defines" in p for p in report.problems)
    assert any("MOCK_API_DATABASE_URL uses ${MOCK_API_DB_PASSWORD} above" in p for p in report.problems)
    main(["--profile", "portfolio", "--env-file", str(env)], environ={})
    out = capsys.readouterr().out
    assert FAKE["APP_DB_PASSWORD"] not in out and FAKE["MOCK_API_DB_PASSWORD"] not in out


def test_reference_to_an_undefined_variable_is_named(tmp_path):
    env = write_per_role_env(tmp_path, [PER_ROLE_URLS[0], f"MOCK_API_DB_PASSWORD={FAKE['MOCK_API_DB_PASSWORD']}"])
    report = build_report("portfolio", load_settings(env, {}))
    assert any("${APP_DB_PASSWORD}, which is not defined in .env" in p for p in report.problems)


def test_reference_supplied_by_the_environment_is_not_a_problem():
    raw = {"DATABASE_URL": PER_ROLE_URLS[0].split("=", 1)[1]}
    assert preflight.reference_problems(raw, {"APP_DB_PASSWORD": "from-the-shell"}) == []
    assert len(preflight.reference_problems(raw, {})) == 1


def test_selected_provider_without_key_is_not_ready():
    report = build_report("portfolio", settings_from(portfolio(AI_PROVIDER="anthropic")))
    assert report.required["ANTHROPIC_API_KEY"] == "missing"
    assert report.required["ANTHROPIC_MODEL"] == "missing"
    assert not report.ready  # never a silent fall back to the mock provider


def test_live_ai_flag_with_mock_provider_is_flagged():
    report = build_report("portfolio", settings_from(portfolio(FEATURE_LIVE_AI="true")))
    assert any("AI_PROVIDER is mock" in p for p in report.problems)


def test_live_model_profile_requires_real_provider_and_flag():
    report = build_report("live-model", settings_from(portfolio()))
    assert any("not mock" in p for p in report.problems)
    assert any("FEATURE_LIVE_AI=true" in p for p in report.problems)
    ready = portfolio(
        AI_PROVIDER="anthropic",
        FEATURE_LIVE_AI="true",
        ANTHROPIC_API_KEY=FAKE["ANTHROPIC_API_KEY"],
        ANTHROPIC_MODEL=FAKE["ANTHROPIC_MODEL"],
    )
    assert build_report("live-model", settings_from(ready)).ready


def test_invalid_format_is_reported_without_value():
    report = build_report("portfolio", settings_from(portfolio(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="abc123xyz")))
    assert report.required["ANTHROPIC_API_KEY"] == "invalid format"
    assert all("abc123xyz" not in p for p in report.problems)


def test_optional_invalid_value_is_a_problem():
    report = build_report("portfolio", settings_from(portfolio(OIDC_ISSUER_URL="not a url")))
    assert report.optional["OIDC_ISSUER_URL"] == "invalid format"
    assert not report.ready


def test_budget_per_run_above_total():
    report = build_report("portfolio", settings_from(portfolio(LLM_BUDGET_USD_PER_RUN="9", LLM_BUDGET_USD_TOTAL="5")))
    assert any("larger than" in p for p in report.problems)


def test_environment_overrides_file(tmp_path):
    settings = settings_from(portfolio(), environ={"LOG_LEVEL": "WARNING"}, tmp_path=tmp_path)
    assert settings.values["LOG_LEVEL"] == "WARNING"
    assert settings.sources["LOG_LEVEL"] == "environment"
    assert settings.sources["APP_SECRET_KEY"] == ".env"


def test_hosted_profile_rejects_local_database_and_debug():
    values = portfolio(APP_PROFILE="staging", LOG_LEVEL="DEBUG")
    values.update(
        {
            k: FAKE[k]
            for k in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "NEXT_PUBLIC_API_BASE_URL")
        }
    )
    report = build_report("staging", settings_from(values))
    assert any("DATABASE_URL points at a local host" in p for p in report.problems)
    assert any("debug" in p for p in report.problems)


def test_approved_requires_https_issuer_and_no_demo_mode():
    values = portfolio(APP_PROFILE="approved", PUBLIC_DEMO_MODE="true", OIDC_ISSUER_URL="http://keycloak.test/realms/x")
    values.update({k: FAKE[k] for k in ("OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OTEL_EXPORTER_OTLP_ENDPOINT")})
    report = build_report("approved", settings_from(values))
    assert any("https" in p for p in report.problems)
    assert any("PUBLIC_DEMO_MODE" in p for p in report.problems)


def test_app_profile_mismatch_is_reported():
    report = build_report("discovery", settings_from(portfolio()))
    assert any("different profile" in p for p in report.problems)
    # Overlays accept the base profile.
    assert not any(
        "different profile" in p for p in build_report("enterprise-identity", settings_from(portfolio())).problems
    )


def test_features_unlocked_and_blocked():
    report = build_report("portfolio", settings_from(portfolio()))
    assert report.features["Offline demo (mock AI, local Postgres)"] == []
    assert report.features["Live Claude runs (arm C live, live smoke test)"] == ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"]


def test_unknown_names_are_listed_by_name_only(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("ANTHROPC_API_KEY=sk-ant-typo-value-123456789\n", encoding="utf-8")
    main(["--env-file", str(env)], environ={})
    out = capsys.readouterr().out
    assert "ANTHROPC_API_KEY" in out
    assert "sk-ant-typo-value" not in out


def test_json_output_shape(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("".join(f"{k}={v}\n" for k, v in portfolio().items()), encoding="utf-8")
    code = main(["--profile", "portfolio", "--env-file", str(env), "--json"], environ={})
    data = json.loads(capsys.readouterr().out)
    assert code == 0 and data["ready"] is True
    assert data["required"]["APP_SECRET_KEY"] == "set"
    assert data["sources"]["APP_SECRET_KEY"] == ".env"


def test_missing_env_file_is_handled(tmp_path, capsys):
    code = main(["--profile", "portfolio", "--env-file", str(tmp_path / "absent.env")], environ={})
    assert code == 1
    assert "NOT READY" in capsys.readouterr().out


def test_test_switches_are_refused_in_public_demo_and_hosted_profiles():
    report = build_report("portfolio", settings_from(portfolio(PUBLIC_DEMO_MODE="true", MOCK_API_FAULTS="true")))
    assert any("MOCK_API_FAULTS must be false when PUBLIC_DEMO_MODE" in p for p in report.problems)
    values = portfolio(APP_PROFILE="staging", MOCK_API_SIM_CLOCK="true")
    values.update(
        {
            k: FAKE[k]
            for k in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "NEXT_PUBLIC_API_BASE_URL")
        }
    )
    assert any(
        "MOCK_API_SIM_CLOCK must be false in a hosted profile" in p
        for p in build_report("staging", settings_from(values)).problems
    )
