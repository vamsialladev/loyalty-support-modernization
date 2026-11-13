"""Static checks on the container setup: no labels or secrets in images, non-root, pinned images, local-only ports,
and the env template and preflight agree (spec F.2, C.6; ADR-0036, ADR-0040)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

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
    stages = set(re.findall(r"^FROM \S+ AS (\S+)", text, re.MULTILINE))
    for image in re.findall(r"^FROM (\S+)", text, re.MULTILINE):
        if image in stages:  # a reference to an earlier stage of this file (Milestone 12 multi-stage builds)
            continue
        assert ":" in image and not image.endswith(":latest"), f"unpinned image {image}"


ROLE_SECRETS = (
    "POSTGRES_PASSWORD",
    "APP_DB_PASSWORD",
    "APP_OWNER_DB_PASSWORD",
    "MOCK_API_DB_PASSWORD",
    "MOCK_API_TOKEN",
    "APP_SECRET_KEY",
    "DEMO_USER_PASSWORD",
)


def test_compose_binds_locally_pins_images_and_requires_secrets() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["db"]["image"] == "postgres:16.15-alpine"
    for name, svc in services.items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name} exposes {port} beyond localhost"
        assert "limits" in svc["deploy"]["resources"], f"{name} has no resource limits"
    for name in ("mock-api", "app", "migrate", "worker"):
        assert services[name]["read_only"] is True
    assert services["mock-api"]["volumes"] == ["./seed_data/v1:/seed_data/v1:ro"]
    raw = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for secret in ROLE_SECRETS:
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

SH = shutil.which("sh")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def test_compose_refuses_a_blank_secret_everywhere_it_is_used() -> None:
    # ${NAME} alone expands a blank value with only a warning; ${NAME:?...} stops Compose instead.
    raw = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for name in ROLE_SECRETS:
        uses = re.findall(r"\$\{" + name + r"(\S{0,2})", raw)
        assert uses, f"compose never uses {name}"
        assert all(use.startswith(":?") for use in uses), f"compose can expand {name} to a blank string"


def run_roles_script(
    tmp_path: Path, app_pw: str, mock_pw: str, owner_pw: str = "a-real-owner-password"
) -> tuple[int, str]:
    """Run the real init script with psql replaced by a shell function that only records that it ran."""
    log = tmp_path / "psql-calls.log"
    script = (ROOT / "infrastructure/postgres/init/01-roles.sh").as_posix()
    env = {**os.environ, "APP_DB_PASSWORD": app_pw, "MOCK_API_DB_PASSWORD": mock_pw, "POSTGRES_USER": "u"}
    env |= {"APP_OWNER_DB_PASSWORD": owner_pw}
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
    assert detail.split("|", 1)[0] == "5"  # the role block, one schema change per mock database, the app role split x2


@pytest.mark.skipif(SH is None, reason="needs a POSIX sh (Git for Windows provides one)")
def test_init_script_refuses_a_blank_owner_password(tmp_path: Path) -> None:
    code, detail = run_roles_script(tmp_path, "a-real-app-password", "a-real-mock-password", owner_pw="")
    assert code != 0 and detail.split("|", 1)[0] == "0" and "APP_OWNER_DB_PASSWORD" in detail


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
        fake |= {"APP_OWNER_DB_PASSWORD": "fake-owner-role-pw-9900"}
    dropped = {"APP_DB_PASSWORD", "APP_OWNER_DB_PASSWORD", "MOCK_API_DB_PASSWORD"}
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


# ---------- the upgrade path from an earlier milestone's volume (ADR-0052) ----------


def test_only_the_migrate_service_holds_the_owner_password() -> None:
    services = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    assert "loyalty_owner" in services["migrate"]["environment"]["DATABASE_URL"]
    assert services["app"]["depends_on"]["migrate"] == {"condition": "service_completed_successfully"}
    # The database servers create the roles, so they hold every role's password; test-db is a second one (M12).
    for name in set(services) - {"migrate", "db", "test-db"}:
        environment = str(services[name].get("environment", ""))
        assert "OWNER" not in environment and "loyalty_owner" not in environment, name
    assert "alembic" not in (ROOT / "Dockerfile.app").read_text(encoding="utf-8").splitlines()[-1]


def test_services_that_migrate_at_start_get_a_start_period() -> None:
    services = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    for name in ("app", "mock-api", "worker"):
        assert services[name]["healthcheck"]["start_period"] == "120s", name
        assert services[name]["healthcheck"]["timeout"] == "10s", name  # a 3 s limit failed on a busy machine


def test_stack_up_reports_the_cause_and_the_compose_check_covers_the_upgrade() -> None:
    stack = (ROOT / "scripts/stack.ps1").read_text(encoding="utf-8")
    assert "scripts/stack_diagnose.py" in stack and "$diagnosis -eq 3" in stack
    check = (ROOT / "scripts/compose_check.ps1").read_text(encoding="utf-8")
    for step in (
        "downgrade 0001",
        "a running app on an old schema",
        "-Action seed",
        "mock data already loaded, skipped",
    ):
        assert step in check, step


def test_the_real_milestone_5_upgrade_runs_in_the_compose_check_and_ci() -> None:
    check = (ROOT / "scripts/compose_check.ps1").read_text(encoding="utf-8")
    assert "scripts\\upgrade_check_m5.ps1" in check
    upgrade = (ROOT / "scripts/upgrade_check_m5.ps1").read_text(encoding="utf-8")
    assert '$lastMilestone5Commit = "68deba1"' in upgrade and "git worktree add --detach" in upgrade
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "sh scripts/ci_postgres_setup.sh" in workflow  # one setup for CI and scripts/ci_local.ps1 (M12)
    setup = (ROOT / "scripts/ci_postgres_setup.sh").read_text(encoding="utf-8")
    assert "{=T/loyalty_app,loyalty_app=CTc/loyalty_app}" in setup


def test_the_upgrade_checks_worker_step_needs_a_real_claim_and_the_whole_log() -> None:
    upgrade = (ROOT / "scripts/upgrade_check_m5.ps1").read_text(encoding="utf-8")
    assert "upgrade_check_probe" in upgrade and "dead|unknown_kind" in upgrade
    assert "--tail" not in upgrade, "a tail can scroll a failed claim away"


# ---------- Milestone 12: profiles, hardening, image targets (DEL-01, TD-52; ADR-0073, ADR-0074) ----------

DEFAULT_STACK = {"db", "mock-api", "migrate", "app", "worker"}


def _services() -> dict[str, Any]:
    services: dict[str, Any] = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    return services


def test_the_default_stack_is_unchanged_and_every_extra_service_sits_in_a_profile() -> None:
    services = _services()
    assert {name for name, svc in services.items() if "profiles" not in svc} == DEFAULT_STACK
    profiles = {p for svc in services.values() for p in svc.get("profiles", [])}
    assert profiles == {"demo", "test", "enterprise-identity", "labs"}
    assert services["keycloak"]["profiles"] == ["enterprise-identity", "labs"]
    assert set(services["mcp"]["profiles"]) == set(services["a2a-specialist"]["profiles"]) == {"labs"}


def test_every_service_drops_capabilities_and_privilege_escalation() -> None:
    for name, svc in _services().items():
        assert "no-new-privileges:true" in svc["security_opt"], name
        assert svc["cap_drop"] == ["ALL"], name
        assert set(svc.get("cap_add", [])) <= {"CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"}, name
        if svc.get("cap_add"):
            assert svc.get("image", "").startswith("postgres:"), f"{name}: only Postgres' entrypoint needs these"


def test_protocol_services_use_one_public_issuer_and_fetch_keys_by_service_name() -> None:
    services = _services()
    for name in ("mcp", "a2a-specialist"):
        env = services[name]["environment"]
        assert env["PROTOCOL_TOKEN_ISSUER"] == "http://127.0.0.1:${KEYCLOAK_HOST_PORT:-8090}/realms/hotel", name
        assert env["PROTOCOL_TOKEN_FETCH_URL"] == "http://keycloak:8080/realms/hotel", name
        assert services[name]["build"]["target"] == "protocols", name
        assert services[name]["read_only"] is True, name
    command = " ".join(services["keycloak"]["command"])
    assert "--hostname=http://127.0.0.1:${KEYCLOAK_HOST_PORT:-8090}" in command
    assert "--hostname-backchannel-dynamic=true" in command


def test_keycloak_refuses_to_start_without_its_admin_password_but_the_default_stack_needs_none() -> None:
    keycloak = _services()["keycloak"]
    assert 'test -n "$$KC_BOOTSTRAP_ADMIN_PASSWORD" ||' in keycloak["command"][0]
    assert keycloak["environment"]["KC_BOOTSTRAP_ADMIN_PASSWORD"] == "${KEYCLOAK_ADMIN_PASSWORD:-}"


def test_the_test_database_keeps_nothing_and_the_demo_seed_runs_after_the_app() -> None:
    services = _services()
    assert "volumes" not in services["test-db"] or all("pgdata" not in v for v in services["test-db"]["volumes"])
    assert services["test-db"]["tmpfs"] == ["/var/lib/postgresql/data"]
    assert services["demo-seed"]["depends_on"] == {"app": {"condition": "service_healthy"}}
    assert services["demo-seed"]["command"] == ["python", "-m", "app.seed", "--dataset", "demo"]


def _stages(dockerfile: Path) -> dict[str, str]:
    text = dockerfile.read_text(encoding="utf-8")
    parts = re.split(r"^FROM ", text, flags=re.MULTILINE)[1:]
    return {part.split()[2] if " AS " in part.split("\n")[0] else "?": part for part in parts}


@pytest.mark.parametrize("dockerfile", DOCKERFILES, ids=lambda p: p.name)
def test_uv_stays_in_the_build_stages_and_the_runtime_runs_as_10001_with_a_healthcheck(dockerfile: Path) -> None:
    stages = _stages(dockerfile)
    runtime = list(stages)[-1]
    assert runtime in ("app", "runtime")
    for name, body in stages.items():
        if "COPY --from=uv" in body:
            assert name.startswith("deps"), f"uv is copied into {name}"
    assert "USER 10001" in stages[runtime] and "HEALTHCHECK" in stages[runtime]


def test_the_core_image_has_no_protocol_sdks_and_the_protocols_image_has_them() -> None:
    stages = _stages(ROOT / "Dockerfile.app")
    assert "--group protocols" in stages["deps-protocols"]
    assert "--group protocols" not in stages["deps"]
    assert "COPY --from=deps /opt/venv" in stages["app"] and "COPY protocols" not in stages["app"]
    assert "COPY --from=deps-protocols /opt/venv" in stages["protocols"]
