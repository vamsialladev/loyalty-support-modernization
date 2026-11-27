"""Time the public demo's start, locally, against a throwaway Postgres 16 (LIVE-06; verification log M12).

    uv run python scripts/demo_startup_timing.py --image loyalty-demo:before --image loyalty-demo:after \
        --label compare

Each image gets a fresh Postgres on a private Docker network and one first start: roles, databases, migrations, the
daily reset and the sample cases. Then the images take turns for `--rounds` ordinary cold starts against their own
database (the reset isn't due), as Cloud Run starts after the first deploy. Taking turns keeps the comparison fair on
a busy machine; the report says how many other containers were running. For each run it records the seconds from
`docker run` to the first HTTP 200 on `/login` from this machine, and the container's own `demo startup:` lines, if
the image prints them. Everything is thrown away after.

What this can't measure: Neon's wake-up and Cloud Run's own start (pulling the image, starting the container). The
live demo's log lines give the first; the live cold start minus this local number bounds the rest.

The database password and the app key are random per call, used only inside Docker, and never printed or saved.
"""

from __future__ import annotations

import argparse
import json
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTGRES_IMAGE = "postgres:16.15-alpine"  # the same image as CI's Postgres job


def docker(*args: str, check: bool = True) -> str:
    done = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if check and done.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed: {done.stderr.strip()[:300]}")
    return done.stdout


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_healthy(name: str, seconds: float = 120) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if docker("inspect", name, "--format", "{{.State.Health.Status}}", check=False).strip() == "healthy":
            return
        time.sleep(1)
    raise RuntimeError(f"{name} wasn't healthy within {seconds:.0f} s")


def time_to_login(url: str, container: str, seconds: float = 300) -> float:
    """Seconds until /login answers 200; fails early if the container stops."""
    began = time.monotonic()
    while time.monotonic() - began < seconds:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - a fixed local URL
                if response.status == 200:
                    return time.monotonic() - began
        except (urllib.error.URLError, OSError):
            pass
        if docker("inspect", container, "--format", "{{.State.Running}}", check=False).strip() != "true":
            raise RuntimeError(f"{container} stopped before /login answered")
        time.sleep(0.25)
    raise RuntimeError(f"/login didn't answer within {seconds:.0f} s")


def startup_lines(container: str, seconds: float = 15) -> list[str]:
    """The launcher's `demo startup:` lines. /login can answer a moment before the launcher prints its last line (its
    own check polls once a second), so wait for the total line; an image without timings prints none at all."""
    command = ["docker", "logs", container]
    deadline = time.monotonic() + seconds
    while True:
        logs = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
        text = logs.stdout + logs.stderr
        lines = [line.strip() for line in text.splitlines() if line.startswith("demo startup:")]
        if not lines or any("total until" in line for line in lines) or time.monotonic() > deadline:
            return lines
        time.sleep(0.5)


def start_database(network: str, name: str, password: str) -> str:
    docker(
        "run", "-d", "--name", name, "--network", network, "-e", "POSTGRES_USER=demo_admin",
        "-e", f"POSTGRES_PASSWORD={password}", "-e", "POSTGRES_DB=demo_admin",
        "--health-cmd", "pg_isready -U demo_admin -d demo_admin", "--health-interval", "2s",
        "--health-retries", "60", POSTGRES_IMAGE,
    )  # fmt: skip
    wait_healthy(name)
    return f"postgresql://demo_admin:{password}@{name}:5432/demo_admin"


def one_start(image: str, network: str, admin_url: str, app_key: str, name: str) -> dict[str, object]:
    port = free_port()
    began = time.monotonic()
    docker(
        "run", "-d", "--name", name, "--network", network, "-p", f"127.0.0.1:{port}:8080",
        "--memory", "1g", "--cpus", "1", "--cap-drop", "ALL",  # Cloud Run's size: 1 vCPU, 1 GiB
        "-e", "PORT=8080", "-e", f"DEMO_DATABASE_URL={admin_url}", "-e", f"APP_SECRET_KEY={app_key}",
        "-e", "PUBLIC_DEMO_MODE=true", "-e", "AI_PROVIDER=mock", "-e", "FEATURE_LIVE_AI=false",
        "-e", "APP_PROFILE=portfolio", "-e", "LOG_LEVEL=INFO", image,
    )  # fmt: skip
    launched = time.monotonic() - began
    try:
        seconds = launched + time_to_login(f"http://127.0.0.1:{port}/login", name)
        return {"seconds_to_login_200": round(seconds, 2), "lines": startup_lines(name)}
    except RuntimeError:
        tail = docker("logs", "--tail", "20", name, check=False)  # the launcher and servers print no secret
        print(f"{name} failed; its last log lines:\n{tail}", flush=True)
        raise
    finally:
        docker("rm", "-f", name, check=False)


def measure(images: list[str], rounds: int) -> dict[str, list[dict[str, object]]]:
    """Each image gets its own fresh database and one first start (the reset), then the images take turns for
    `rounds` ordinary cold starts, so a busy machine slows both alike."""
    tag = secrets.token_hex(3)
    network = f"demo-timing-{tag}"
    results: dict[str, list[dict[str, object]]] = {image: [] for image in images}
    databases: dict[str, str] = {}
    keys = {image: secrets.token_urlsafe(48) for image in images}
    docker("network", "create", network)
    try:
        for i, image in enumerate(images):
            databases[image] = start_database(network, f"demo-timing-pg-{tag}-{i}", secrets.token_urlsafe(24))
        plan = [(image, "first start of the day (reset)") for image in images]
        plan += [(image, "ordinary cold start (no reset)") for _ in range(rounds) for image in images]
        for image, kind in plan:
            result = one_start(image, network, databases[image], keys[image], f"demo-timing-app-{tag}")
            results[image].append({"kind": kind, **result})
            print(f"{image} ({kind}): {result['seconds_to_login_200']:.2f} s to /login 200", flush=True)
    finally:
        for i in range(len(images)):
            docker("rm", "-f", f"demo-timing-pg-{tag}-{i}", check=False)
        docker("network", "rm", network, check=False)
    return results


def other_running_containers() -> int:
    return len([line for line in docker("ps", "-q", check=False).splitlines() if line.strip()])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", action="append", required=True, help="repeat to compare images turn by turn")
    parser.add_argument("--label", required=True, help="a short name for the report file")
    parser.add_argument("--rounds", type=int, default=3, help="ordinary cold starts per image")
    args = parser.parse_args()
    busy = other_running_containers()
    results = measure(args.image, args.rounds)
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    out = ROOT / "performance" / "reports" / f"{day}-demo-startup-{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "label": args.label,
        "measured_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "where": "local Docker Desktop on Windows, 1 CPU and 1 GiB per container, Postgres 16.15 in Docker",
        "other_containers_running_at_start": busy,
        "not_measured": "Neon wake-up; Cloud Run's image pull and container start",
        "images": results,
    }
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
