"""The CI and deploy workflows keep their rules (DEL-02, DEL-03, DEL-04, SEC-11; ADR-0084)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return data


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    return workflow.get("on") or workflow.get(True) or {}  # PyYAML reads the key `on` as True


def test_every_action_and_image_is_pinned_to_an_exact_version() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for ref in re.findall(r"uses:\s*([^\s#]+)", text):
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@v\d+\.\d+\.\d+", ref), f"{path.name}: {ref}"
        for image in re.findall(r"(?:image:|docker run --rm[^\n]*?)\s((?:[\w.-]+/)*[\w.-]+:[\w.-]+)", text):
            assert not image.endswith(":latest"), f"{path.name}: {image}"


def test_ci_uses_no_secrets_so_a_fork_pull_request_gets_none() -> None:
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "secrets." not in text
    assert _load("ci.yml")["permissions"] == {"contents": "read"}


def test_every_job_has_a_time_limit_and_extra_permissions_only_where_needed() -> None:
    jobs = _load("ci.yml")["jobs"]
    for name, job in jobs.items():
        assert job.get("timeout-minutes"), name
        extra = {k for k, v in (job.get("permissions") or {}).items() if v == "write"}
        assert extra <= {"id-token", "attestations"}, name
        if extra:
            assert name == "images", f"{name} asks for write permissions"


def test_the_pipeline_has_the_milestone_12_jobs() -> None:
    jobs = _load("ci.yml")["jobs"]
    assert {"checks", "postgres", "browser", "images", "compose", "release-gate", "secrets"} <= set(jobs)
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "alembic downgrade base" in text and "alembic upgrade head" in text  # migration on an empty database
    assert "--exit-code 1" in text and "--ignore-unfixed" in text  # scanners fail the build, never just report
    assert "sbom-action" in text and "attest-build-provenance" in text
    assert jobs["browser"]["container"]["image"].startswith("mcr.microsoft.com/playwright/python:v")
    checks = " ".join(str(step.get("run", "")) for step in jobs["checks"]["steps"])
    assert '-m "not browser"' in checks and "playwright install" not in checks


def _locked_version(package: str) -> str:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    (version,) = {p["version"] for p in lock["package"] if p["name"] == package}
    return str(version)


def test_the_browser_job_runs_the_browser_tests_and_never_skips_them() -> None:
    """A Playwright bump on an older image skipped all 11 browser tests and the job passed (2026-11-14)."""
    job = _load("ci.yml")["jobs"]["browser"]
    assert job["env"]["REQUIRE_BROWSER"] == "1"
    tag = job["container"]["image"].split(":v", 1)[1]
    assert tag == f"{_locked_version('playwright')}-noble", "the Playwright image must carry the locked version"
    assert "REQUIRE_BROWSER" in (ROOT / "scripts" / "ci_local.ps1").read_text(encoding="utf-8")


def test_a_missing_browser_fails_where_it_must_run_and_skips_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.browser.test_legacy_e2e import browser_unavailable

    monkeypatch.setenv("REQUIRE_BROWSER", "1")
    with pytest.raises(pytest.fail.Exception, match="must run here"):
        browser_unavailable("Chromium is not available")
    monkeypatch.delenv("REQUIRE_BROWSER")
    with pytest.raises(pytest.skip.Exception):
        browser_unavailable("Chromium is not available")


def test_deploy_is_manual_gated_and_keyless() -> None:
    deploy = _load("deploy.yml")
    assert set(_triggers(deploy)) == {"workflow_dispatch"}
    job = deploy["jobs"]["deploy"]
    assert job["environment"] == "production"
    assert job["permissions"]["id-token"] == "write"
    text = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
    assert "aws-access-key-id" not in text and "secrets." not in text  # credentials come from OIDC only
    assert "refs/heads/main" in job["if"]
