"""Static checks on the container setup: no labels or secrets in images, non-root, pinned images, local-only ports,
and the env template and preflight agree (spec F.2, C.6; ADR-0036, ADR-0040)."""

from __future__ import annotations

import re
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
