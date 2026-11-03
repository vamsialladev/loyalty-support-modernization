"""`scripts/stack_diagnose.py`: the stack's real cause in plain words, never a secret (ADR-0052)."""

from __future__ import annotations

from scripts.stack_diagnose import (
    NEEDS_MIGRATION,
    PROBLEM,
    READY,
    ServiceState,
    mask,
    readiness_problems,
    report,
    service_problem,
)

READYZ_OK = {"status": "ready", "database": "ok", "customer_systems": "ok"}


def running(service: str = "app", **kwargs: object) -> ServiceState:
    return ServiceState(service, "running", health="healthy", **kwargs)  # type: ignore[arg-type]


def test_a_healthy_stack_is_ready() -> None:
    assert report([running("db"), running("mock-api"), running("app")], READYZ_OK) == (READY, [])


def test_no_containers_says_compose_failed_first() -> None:
    code, messages = report([], None)
    assert code == PROBLEM and "failed before creating them" in messages[0]


def test_an_unmigrated_database_asks_for_migration() -> None:
    code, messages = report([running()], {"database": "not_migrated", "customer_systems": "ok"})
    assert code == NEEDS_MIGRATION and "not migrated" in messages[0]


def test_an_unseeded_mock_is_a_hint_not_a_fault() -> None:
    code, messages = readiness_problems({"database": "ok", "customer_systems": "not_seeded"})
    assert code == READY and "-Action seed" in messages[0]


def test_unreachable_systems_are_problems() -> None:
    assert readiness_problems(None)[0] == PROBLEM
    assert readiness_problems({"database": "unreachable", "customer_systems": "ok"})[0] == PROBLEM
    assert readiness_problems({"database": "ok", "customer_systems": "unreachable"})[0] == PROBLEM


def test_a_failed_migration_is_named() -> None:
    svc = ServiceState(
        "app",
        "exited",
        exit_code=1,
        logs=["INFO [alembic.runtime.migration] Running upgrade", "Traceback (most recent call last):", "boom Error"],
    )
    problem = service_problem(svc)
    assert problem and "migration failed" in problem and "boom Error" in problem


def test_a_changed_role_password_is_explained_without_the_password() -> None:
    logs = [
        "connection to postgresql://loyalty_app:s3cret-value@db:5432/loyalty failed: password authentication failed"
    ]
    problem = service_problem(ServiceState("app", "exited", exit_code=1, logs=logs))
    assert problem and "stored in the volume" in problem and "s3cret-value" not in problem


def test_a_volume_from_newer_code_is_explained() -> None:
    problem = service_problem(ServiceState("app", "exited", exit_code=1, logs=["Can't locate revision identified by"]))
    assert problem and "newer code" in problem


def test_slow_start_says_nothing_is_broken() -> None:
    logs = ['INFO: 127.0.0.1:1 - "GET /healthz HTTP/1.1" 200 OK']
    problem = service_problem(ServiceState("app", "running", health="unhealthy", logs=logs))
    assert problem and "Nothing is broken" in problem


def test_never_answering_quotes_the_health_check_and_real_logs_only() -> None:
    svc = ServiceState(
        "app",
        "running",
        health="unhealthy",
        last_check="Traceback\nurllib.error.URLError: <urlopen error [Errno 111] Connection refused>",
        logs=['"GET /readyz HTTP/1.1" 503', "INFO: Waiting for application startup."],
    )
    problem = service_problem(svc)
    assert problem and "Connection refused" in problem and "Waiting for application startup" in problem
    assert "/readyz" not in problem


def test_other_states() -> None:
    still = service_problem(ServiceState("app", "running", health="starting"))
    assert still and "still starting" in still
    stopped = service_problem(ServiceState("app", "exited", exit_code=137))
    assert stopped and "exit code 137" in stopped
    assert "restarting" in (service_problem(ServiceState("app", "restarting")) or "")
    assert service_problem(ServiceState("db", "running")) is None  # no health check configured


def test_credentials_in_log_lines_are_masked() -> None:
    assert mask("postgresql+psycopg://user:hunter2@db/x") == "postgresql+psycopg://user:***@db/x"
    assert "hunter2" not in mask("password=hunter2 next")
    assert "hunter2" not in mask('"token": "hunter2"')
    assert mask("nothing secret here") == "nothing secret here"
