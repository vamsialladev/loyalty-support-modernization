"""Say why the local stack isn't working, in plain words, instead of only "unhealthy" (ADR-0052).

    uv run python scripts/stack_diagnose.py --project loyalty --env-file .env

Reads each container's state, health checks and recent log lines from Docker, and the app's `/readyz`.
`scripts\\stack.ps1` runs this after `up`. Exit code: 0 ready, 1 a problem it names, 3 the app database needs
migrating. Credentials in log lines are masked before anything is printed; values from the env file are never printed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

READY, PROBLEM, NEEDS_MIGRATION = 0, 1, 3
_URL_PASSWORD = re.compile(r"(://[^:/\s]+:)[^@\s]+@")
_NAMED_SECRET = re.compile(r"(?i)((?:password|passwd|token|secret)[\"']?\s*[=:]\s*[\"']?)[^\s\"',]+")


def mask(line: str) -> str:
    return _NAMED_SECRET.sub(r"\1***", _URL_PASSWORD.sub(r"\1***@", line))


@dataclass(frozen=True)
class ServiceState:
    service: str
    state: str  # running | exited | created | restarting | ...
    exit_code: int = 0
    health: str | None = None  # starting | healthy | unhealthy | None (no health check)
    last_check: str = ""
    logs: list[str] = field(default_factory=list)


def _recent(logs: list[str], count: int = 5) -> str:
    useful = [line.strip() for line in logs if line.strip() and "/healthz" not in line and "/readyz" not in line]
    return " | ".join(mask(line) for line in useful[-count:]) or "(no log lines apart from health checks)"


def _log_cause(service: str, logs: list[str]) -> str | None:
    text = "\n".join(logs)
    if "password authentication failed" in text:
        return (
            f"{service}: the database refused its password. Role passwords are stored in the volume when it is first "
            "created, so changing them in .env later doesn't update them. Restore the old values, or delete the "
            "volume with scripts\\stack.ps1 -Action clean (this deletes the local data)."
        )
    if "permission denied for schema" in text:
        return f"{service}: its database role can't create tables. The init script didn't finish; check the db logs."
    if "Can't locate revision" in text:
        return (
            f"{service}: this volume was migrated by newer code than this checkout. Update the checkout, or delete "
            "the volume with scripts\\stack.ps1 -Action clean (this deletes the local data)."
        )
    if "alembic" in text.lower() and ("Traceback" in text or "Error" in text):
        return f"{service}: its database migration failed, so it never started. Last lines: {_recent(logs)}"
    return None


def service_problem(svc: ServiceState) -> str | None:
    """The cause, in plain words, if this service isn't up; None if it is."""
    if svc.state == "exited" or (svc.state != "running" and svc.exit_code != 0):
        return _log_cause(svc.service, svc.logs) or (
            f"{svc.service}: stopped with exit code {svc.exit_code}. Last lines: {_recent(svc.logs)}"
        )
    if svc.state != "running":
        return f"{svc.service}: container state is '{svc.state}'."
    if svc.health in (None, "healthy"):
        return None
    cause = _log_cause(svc.service, svc.logs)
    if cause:
        return cause
    answering = any("/healthz" in line and "200" in line for line in svc.logs)
    if answering:
        return (
            f"{svc.service}: it is answering now but took longer to start than the wait allowed, usually a slow "
            "machine or a cold start. Nothing is broken: run the same command again."
        )
    if svc.health == "starting":
        return f"{svc.service}: still starting. Run the same command again in a minute. Last lines: {_recent(svc.logs)}"
    check = mask(svc.last_check.strip().splitlines()[-1]) if svc.last_check.strip() else "no output"
    return f"{svc.service}: never answered its health check ({check}). Last lines: {_recent(svc.logs)}"


def readiness_problems(readyz: dict[str, Any] | None) -> tuple[int, list[str]]:
    """What the app's /readyz says, as (exit code, messages). An unseeded mock API is normal: a hint, not a fault."""
    if readyz is None:
        return PROBLEM, ["app: /readyz did not answer."]
    code, messages = READY, []
    database = readyz.get("database")
    if database == "not_migrated":
        code = NEEDS_MIGRATION
        messages.append("app database: not migrated to the current schema.")
    elif database != "ok":
        code = PROBLEM
        messages.append(f"app database: {database}.")
    systems = readyz.get("customer_systems")
    if systems == "not_seeded":
        messages.append("mock customer API: no data loaded yet. Run scripts\\stack.ps1 -Action seed.")
    elif systems != "ok":
        code = code or PROBLEM
        messages.append(f"mock customer API: {systems}.")
    return code, messages


def report(services: list[ServiceState], readyz: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not services:
        return PROBLEM, ["No containers exist for this project: docker compose failed before creating them."]
    problems = [p for p in (service_problem(svc) for svc in services) if p]
    if problems:
        return PROBLEM, problems
    return readiness_problems(readyz)


# ---------- reading Docker (thin; everything above is pure and unit-tested) ----------


def _run(*args: str) -> str:
    done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # noqa: S603
    return (done.stdout or "") + (done.stderr or "")


def read_services(project: str) -> list[ServiceState]:
    names = _run(
        "docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Names}}"
    )
    out = []
    for name in names.split():
        info = json.loads(_run("docker", "inspect", name))[0]
        state, health = info["State"], info["State"].get("Health") or {}
        checks = health.get("Log") or [{}]
        out.append(
            ServiceState(
                service=info["Config"]["Labels"].get("com.docker.compose.service", name),
                state=state["Status"],
                exit_code=int(state.get("ExitCode", 0)),
                health=health.get("Status"),
                last_check=str(checks[-1].get("Output", "")),
                logs=_run("docker", "logs", "--tail", "60", name).splitlines(),
            )
        )
    return out


def read_readyz(port: str) -> dict[str, Any] | None:
    try:
        body = httpx.get(f"http://127.0.0.1:{port}/readyz", timeout=5).json()
    except (httpx.HTTPError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stack_diagnose")
    parser.add_argument("--project", default="loyalty")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    port = dotenv_values(args.env_file).get("APP_HOST_PORT") or "8010"
    code, messages = report(read_services(args.project), read_readyz(port))
    for message in messages:
        print(message)
    if code == READY and not messages:
        print("stack: ready")
    return code


if __name__ == "__main__":
    sys.exit(main())
