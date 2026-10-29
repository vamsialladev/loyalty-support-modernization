"""Static checks on the container setup: no labels or secrets in images, non-root, pinned images, local-only ports,
and the env template and preflight agree (spec F.2, C.6; ADR-0036, ADR-0040)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from dotenv import dotenv_values

from app.preflight import VARS
from tests.conftest import ROOT

DOCKERFILES = [ROOT / "Dockerfile.app", ROOT / "mock_customer_api/Dockerfile"]
NEVER_IN_IMAGES = ["benchmarks/", "evaluations/", "seed_data/", "docs/", "tests/", ".env"]


def test_dockerignore_excludes_ground_truth_data_and_secrets() -> None:
    lines = {line.strip() for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()}
    for entry in NEVER_IN_IMAGES:
        assert entry in lines, f".dockerignore must list {entry}"


@pytest.mark.parametrize("dockerfile", DOCKERFILES, ids=lambda p: p.name)
def test_dockerfiles_copy_only_service_code_and_run_as_non_root(dockerfile: Path) -> None:
    text = dockerfile.read_text(encoding="utf-8")
    copies = re.findall(r"^COPY (?!--from)(\S+)", text, re.MULTILINE)
    for source in copies:
        assert not any(source.startswith(bad.rstrip("/")) for bad in NEVER_IN_IMAGES), (
            f"{dockerfile.name} copies {source}"
        )
        assert source not in (".", "./"), f"{dockerfile.name} copies the whole build context"
    assert re.search(r"^USER 10001$", text, re.MULTILINE)
    for image in re.findall(r"^FROM (\S+)", text, re.MULTILINE):
        assert ":" in image and not image.endswith(":latest"), f"unpinned image {image}"


def test_compose_binds_locally_pins_images_and_requires_secrets() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["db"]["image"] == "postgres:16.15-alpine"
    for name, svc in services.items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name} exposes {port} beyond localhost"
        assert "limits" in svc["deploy"]["resources"], f"{name} has no resource limits"
    for name in ("mock-api", "app"):
        assert services[name]["read_only"] is True
    assert services["mock-api"]["volumes"] == ["./seed_data/v1:/seed_data/v1:ro"]
    raw = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for secret in ("POSTGRES_PASSWORD", "APP_DB_PASSWORD", "MOCK_API_DB_PASSWORD", "MOCK_API_TOKEN", "APP_SECRET_KEY"):
        assert f"${{{secret}:?" in raw, f"compose must refuse to start without {secret}"


def test_database_init_script_holds_no_passwords() -> None:
    script = (ROOT / "infrastructure/postgres/init/01-roles.sh").read_text(encoding="utf-8")
    assert "PASSWORD :'app_pw'" in script and "PASSWORD :'mock_pw'" in script
    assert "REVOKE CONNECT ON DATABASE mock_customer_api FROM PUBLIC" in script
    assert not re.search(r"PASSWORD '[^:]", script)


def test_env_template_and_preflight_agree_on_milestone_4_settings() -> None:
    template = dotenv_values(ROOT / ".env.example", interpolate=False)
    for name in ("APP_DB_PASSWORD", "MOCK_API_DB_PASSWORD", "MOCK_API_URL", "MOCK_API_FAULTS", "MOCK_API_SIM_CLOCK"):
        assert name in template and name in VARS
    assert template["MOCK_API_FAULTS"] == "false" and template["MOCK_API_SIM_CLOCK"] == "false"
    assert "loyalty_app:${APP_DB_PASSWORD}" in (template["DATABASE_URL"] or "")
    assert "mock_api:${MOCK_API_DB_PASSWORD}" in (template["MOCK_API_DATABASE_URL"] or "")


def test_fault_rules_reference_known_faults() -> None:
    from mock_customer_api.faults import FAULTS, FaultBook

    rules = FaultBook.load(True, ROOT / "mock_customer_api/config/fault_rules.yaml").rules
    assert {r.fault for r in rules} <= set(FAULTS)
    assert {"timeout", "rate_limited", "unavailable", "commit_then_lost"} <= {r.fault for r in rules}


# ---------- blank role passwords (verification log, M4 env fix) ----------

ROLE_SECRETS = ("POSTGRES_PASSWORD", "APP_DB_PASSWORD", "MOCK_API_DB_PASSWORD", "MOCK_API_TOKEN", "APP_SECRET_KEY")
SH = shutil.which("sh")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def test_compose_refuses_a_blank_secret_everywhere_it_is_used() -> None:
    # ${NAME} alone expands a blank value with only a warning; ${NAME:?...} stops Compose instead.
    raw = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for name in ROLE_SECRETS:
        uses = re.findall(r"\$\{" + name + r"(\S{0,2})", raw)
        assert uses, f"compose never uses {name}"
        assert all(use.startswith(":?") for use in uses), f"compose can expand {name} to a blank string"


def run_roles_script(tmp_path: Path, app_pw: str, mock_pw: str) -> tuple[int, str]:
    """Run the real init script with psql replaced by a shell function that only records that it ran."""
    log = tmp_path / "psql-calls.log"
    script = (ROOT / "infrastructure/postgres/init/01-roles.sh").as_posix()
    env = {**os.environ, "APP_DB_PASSWORD": app_pw, "MOCK_API_DB_PASSWORD": mock_pw, "POSTGRES_USER": "u"}
    env |= {"POSTGRES_DB": "d", "PSQL_LOG": log.as_posix()}
    result = subprocess.run(
        [str(SH), "-c", 'psql() { echo called >> "$PSQL_LOG"; cat > /dev/null; }; . "$0"', script],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    calls = log.read_text(encoding="utf-8").count("called") if log.exists() else 0
    return result.returncode, f"{calls}|{result.stderr}"


@pytest.mark.skipif(SH is None, reason="needs a POSIX sh (Git for Windows provides one)")
@pytest.mark.parametrize(
    ("app_pw", "mock_pw", "blank"),
    [
        ("", "a-real-mock-password", "APP_DB_PASSWORD"),
        ("a-real-app-password", "", "MOCK_API_DB_PASSWORD"),
        ("pw7x", "a-real-mock-password", "APP_DB_PASSWORD"),
    ],
)
def test_init_script_creates_no_role_with_a_blank_password(
    tmp_path: Path, app_pw: str, mock_pw: str, blank: str
) -> None:
    code, detail = run_roles_script(tmp_path, app_pw, mock_pw)
    calls, stderr = detail.split("|", 1)
    assert code != 0
    assert calls == "0", "psql ran, so a role could have been created with a blank password"
    assert blank in stderr
    assert [pw for pw in (app_pw, mock_pw) if pw and pw in stderr] == [], "a password value was printed"


@pytest.mark.skipif(SH is None, reason="needs a POSIX sh (Git for Windows provides one)")
def test_init_script_runs_with_real_passwords(tmp_path: Path) -> None:
    code, detail = run_roles_script(tmp_path, "a-real-app-password", "a-real-mock-password")
    assert code == 0, detail
    assert detail.split("|", 1)[0] == "3"  # the role block, then one schema change per mock database


@pytest.mark.skipif(POWERSHELL is None, reason="needs PowerShell")
@pytest.mark.parametrize("start", ["pre-milestone-4", "broken-by-the-old-script"])
def test_update_local_env_leaves_every_reference_resolvable(tmp_path: Path, start: str) -> None:
    from app.preflight import build_report, load_settings

    fake = {
        "POSTGRES_PASSWORD": "fake-admin-pw-1234",
        "MOCK_API_TOKEN": "fake-token-123456",
        "APP_SECRET_KEY": "k" * 40,
    }
    if start == "broken-by-the-old-script":
        # What the first version of the script wrote: role passwords appended below the URL lines that use them.
        fake |= {"APP_DB_PASSWORD": "fake-app-role-pw-5566", "MOCK_API_DB_PASSWORD": "fake-mock-role-pw-7788"}
    dropped = {"APP_DB_PASSWORD", "MOCK_API_DB_PASSWORD"}
    lines = []
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0]
        if key in dropped:
            continue
        if key in ("DATABASE_URL", "MOCK_API_DATABASE_URL") and start == "pre-milestone-4":
            db = "loyalty" if key == "DATABASE_URL" else "mock_customer_api"
            line = f"{key}=postgresql+psycopg://loyalty:${{POSTGRES_PASSWORD}}@localhost:5432/{db}"
        lines.append(f"{key}={fake[key]}" if key in fake else line)
    if start == "broken-by-the-old-script":
        lines += [f"{name}={fake[name]}" for name in sorted(dropped)]
    env = tmp_path / "local.env"
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/update-local-env.ps1"),
            "-Path",
            str(env),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "moved above the lines that use them: APP_DB_PASSWORD, MOCK_API_DB_PASSWORD" in result.stdout
    for value in fake.values():
        assert value not in result.stdout + result.stderr

    report = build_report("portfolio", load_settings(env, {}))
    assert report.required["DATABASE_URL"] == "set"
    assert report.required["MOCK_API_DATABASE_URL"] == "set"
    assert report.problems == []
    after = dotenv_values(env, interpolate=False)
    for name, value in fake.items():
        assert after[name] == value, f"{name} was changed"
