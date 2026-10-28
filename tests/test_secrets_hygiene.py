"""Secrets stay out of Git (Appendix K2.1 to K2.3, K2.6). Failures name files and variables, never values."""

import json
import re
import subprocess
from pathlib import Path

import pytest
from dotenv import dotenv_values

from app import env_leaks
from app.env_leaks import find_leaks, secret_values, tracked_files
from app.preflight import SECRET_NAMES

ROOT = Path(__file__).resolve().parent.parent


REFERENCE = re.compile(r"\$\{[A-Z_]+\}")


def literal_secrets(template: dict[str, str | None]) -> list[str]:
    """Secret-flagged names holding a literal value. A URL may reference ${VAR} as its password, nothing else."""
    filled = []
    for name in sorted(SECRET_NAMES):
        value = (template.get(name) or "").strip()
        if not value:
            continue
        if "://" in value:
            userinfo = value.split("://", 1)[1].split("@", 1)[0]
            password = userinfo.split(":", 1)[1] if ":" in userinfo else ""
            if password and not REFERENCE.fullmatch(password):
                filled.append(name)
        elif not REFERENCE.fullmatch(value):
            filled.append(name)
    return filled


def test_env_example_has_no_secret_values():
    # Raw text, no interpolation, so ${POSTGRES_PASSWORD} stays a reference.
    template = dotenv_values(ROOT / ".env.example", interpolate=False)
    assert literal_secrets(template) == [], ".env.example must not hold secret values"


def test_literal_secret_check_catches_keys_and_url_passwords():
    template = {
        "ANTHROPIC_API_KEY": "sk-ant-literal-value",
        "DATABASE_URL": "postgresql+psycopg://loyalty:hunter2-literal@localhost:5432/loyalty",
        "MOCK_API_DATABASE_URL": "postgresql+psycopg://loyalty:${POSTGRES_PASSWORD}@localhost:5432/mock",
        "MOCK_API_TOKEN": "",
    }
    assert literal_secrets(template) == ["ANTHROPIC_API_KEY", "DATABASE_URL"]


@pytest.mark.parametrize("path", [".env", ".env.local", ".env.production", "secrets/x.txt", "deploy.pem", "id.key"])
def test_env_files_are_git_ignored(path):
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
    assert result.returncode == 0, f"{path} is not Git-ignored"


def test_env_example_is_not_ignored():
    result = subprocess.run(["git", "check-ignore", "-q", ".env.example"], cwd=ROOT)
    assert result.returncode == 1


def test_claude_settings_deny_env():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    deny = settings["permissions"]["deny"]
    assert "Read(./.env)" in deny
    assert "Edit(./.env)" in deny


def test_scanner_finds_a_planted_value(tmp_path):
    planted = tmp_path / "notes.md"
    planted.write_text("config: fake-planted-secret-31337\n", encoding="utf-8")
    clean = tmp_path / "clean.md"
    clean.write_text("nothing here\n", encoding="utf-8")
    secrets = secret_values({"MOCK_API_TOKEN": "fake-planted-secret-31337", "LOG_LEVEL": "INFO"})
    assert find_leaks(secrets, [planted, clean]) == [(str(planted), "MOCK_API_TOKEN")]


def test_secret_values_skips_short_and_non_secret_names():
    found = secret_values(
        {"LOG_LEVEL": "WARNING-long-value", "APP_SECRET_KEY": "short", "GH_TOKEN": "github_pat_x123456"}
    )
    assert list(found) == ["GH_TOKEN"]


def test_secret_values_skips_unchanged_template_defaults():
    url = "postgresql+psycopg://loyalty:@localhost:5432/loyalty"
    assert secret_values({"DATABASE_URL": url}, {"DATABASE_URL": url}) == {}
    assert list(secret_values({"DATABASE_URL": url.replace(":@", ":changed-pass@")}, {"DATABASE_URL": url})) == [
        "DATABASE_URL"
    ]


def test_no_env_secret_value_in_tracked_files():
    env = ROOT / ".env"
    if not env.is_file():
        pytest.skip("no .env file on this machine (CI): nothing can leak from it")
    secrets = secret_values(dotenv_values(env), dotenv_values(ROOT / ".env.example"))
    leaks = find_leaks(secrets, tracked_files(ROOT))
    assert leaks == [], "secret values from .env found in tracked files: " + ", ".join(f"{n} in {p}" for p, n in leaks)


def test_cli_exit_code_and_output_in_a_repo(tmp_path, capsys):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".env").write_text("MOCK_API_TOKEN=fake-cli-planted-token-777\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("token: fake-cli-planted-token-777\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    assert env_leaks.main(tmp_path) == 1
    out = capsys.readouterr().out
    assert "MOCK_API_TOKEN" in out and "README.md" in out
    assert "fake-cli-planted-token-777" not in out
    (tmp_path / "README.md").write_text("clean\n", encoding="utf-8")
    assert env_leaks.main(tmp_path) == 0


def test_cli_without_env_file(tmp_path, capsys):
    assert env_leaks.main(tmp_path) == 0
    assert "nothing to check" in capsys.readouterr().out
