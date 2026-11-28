"""The Milestone 13b drill runner (`scripts/drill.py`) and its workflow (`.github/workflows/drills.yml`), offline: the
parts that need no stack. The drills themselves run in GitHub Actions against a throwaway Compose stack."""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts import drill

ROOT = Path(__file__).resolve().parent.parent


def test_the_env_file_is_read_without_quotes_or_comments(tmp_path: Path) -> None:
    env = tmp_path / ".env.ci"
    env.write_text('# a comment\nDEMO_USER_PASSWORD="throwaway-1"\nPOSTGRES_USER=loyalty\n\n', encoding="utf-8")
    assert drill.read_env(env) == {"DEMO_USER_PASSWORD": "throwaway-1", "POSTGRES_USER": "loyalty"}


def test_a_report_passes_only_if_it_has_checks_and_all_passed(tmp_path: Path) -> None:
    report = drill.Report("d0")
    assert not report.passed  # no checks: nothing was shown
    report.check("one", True)
    assert report.passed
    report.check("two", False, seen=1)
    assert not report.passed
    saved = report.save(tmp_path)
    assert saved.name == "d0.json" and '"passed": false' in saved.read_text(encoding="utf-8")


def test_the_drill_picks_dev_cases_labelled_adjusted() -> None:
    picked = drill.adjustable_cases()
    assert len(picked) >= 2  # D7 needs two approved adjustments
    assert all(len(row["requests"]) == 1 and not row["requests"][0]["attachments"] for row in picked)


def test_postings_bind_their_values_instead_of_pasting_them(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen["command"], seen["sql"] = command, kwargs["input"]
        return subprocess.CompletedProcess(command, 0, stdout="1\n", stderr="")

    monkeypatch.setattr(drill.subprocess, "run", fake_run)
    stack = drill.Stack("ci", Path(".env.ci"), "loyalty")
    assert drill.postings(stack, "GR-85640", "BR-6638'; DROP TABLE x; --") == 1
    assert seen["command"][:6] == ["docker", "compose", "-p", "ci", "--env-file", ".env.ci"]
    assert "-v" in seen["command"] and "stay=BR-6638'; DROP TABLE x; --" in seen["command"]
    assert "DROP" not in seen["sql"] and ":'stay'" in seen["sql"]


def test_the_audit_check_reads_the_action_where_the_security_api_puts_it() -> None:
    """Found on D7's first CI run (2026-11-28): the check looked for a top-level `action` and found none, while the
    API returns Elastic Common Schema documents with `event.action` (verification log M13b row 1)."""
    source = inspect.getsource(drill.drill_d7)  # only the security-event check; a case's audit has a top-level action
    assert 'e.get("event", {}).get("action")' in source and 'e.get("action")' not in source


def test_the_drills_workflow_reads_no_secret_runs_one_at_a_time_and_keeps_its_output() -> None:
    text = (ROOT / ".github" / "workflows" / "drills.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    assert "secrets." not in text
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["drill"]
    assert job["timeout-minutes"] and job["strategy"]["max-parallel"] == 1
    uses = [step.get("uses", "") for step in job["steps"]]
    assert any(u.startswith("actions/upload-artifact@") for u in uses)
    assert "docker compose -p ci --env-file .env.ci down -v" in text  # the throwaway stack is removed
    for forbidden in ("run.app", "neon.tech", "gcloud"):
        assert forbidden not in text  # never the live demo, Cloud Run or Neon
    assert set(drill.DRILLS) >= {"d7", "d3", "d5", "d2"}
    for name in drill.DRILLS:
        assert f'"{name}"' in text, f"{name} isn't in the workflow's drill list"


def test_the_drill_overrides_touch_only_the_mock_api_and_turn_its_faults_on() -> None:
    override = yaml.safe_load((ROOT / "docker-compose.drills.yml").read_text(encoding="utf-8"))
    assert set(override["services"]) == {"mock-api"}
    env = override["services"]["mock-api"]["environment"]
    assert env["MOCK_API_FAULTS"] == "true" and env["MOCK_API_FAULT_RULES_FILE"] == "/drill-rules/rules.yaml"
    assert override["services"]["mock-api"]["volumes"] == ["./drill-output/rules:/drill-rules:ro"]


def test_fault_rules_are_written_where_the_override_mounts_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(drill, "run", commands.append)
    drill.with_faults(drill.Stack("ci", Path(".env.ci"), "loyalty"), tmp_path, [{"fault": "commit_then_lost"}])
    assert yaml.safe_load((tmp_path / "rules" / "rules.yaml").read_text(encoding="utf-8")) == {
        "rules": [{"fault": "commit_then_lost"}]
    }
    [command] = commands
    assert command[:2] == ["docker", "compose"] and command.count("-f") == 2
    assert command[-1] == "mock-api" and "--no-deps" in command


def test_the_job_check_binds_the_case_number(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen["command"], seen["sql"] = command, kwargs["input"]
        return subprocess.CompletedProcess(command, 0, stdout="running:worker-1\n", stderr="")

    monkeypatch.setattr(drill.subprocess, "run", fake_run)
    stack = drill.Stack("ci", Path(".env.ci"), "loyalty", "loyalty")
    assert drill.job_state(stack, 7) == "running:worker-1"
    assert "case=7" in seen["command"] and ":'case'" in seen["sql"] and "-d" in seen["command"]
