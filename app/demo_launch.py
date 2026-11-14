"""The public demo in one container (spec L1; SEC-18, LIVE-02; ADR-0087): `python -m app.demo_launch`.

Render's free plan runs one web service and no background worker, so this process starts the mock customer API and
the worker as child processes, and the app in the foreground on `$PORT`. It needs **one** secret besides
`APP_SECRET_KEY`: `DEMO_DATABASE_URL`, the Neon project's owner connection string, pasted into Render's dashboard.
From it, on every start, it:

1. makes the three roles (`loyalty_owner`, `loyalty_app`, `mock_api`) and the two databases, if missing, with
   passwords derived from `APP_SECRET_KEY` (so nothing else needs storing, and changing the key rotates them);
2. runs both databases' migrations, then the app role's grants, including append-only audit (ADR-0058);
3. once a day, empties the demo's cases (`app.services.demo.reset`, as the owner), then loads the synthetic world
   and the demo accounts (agent and supervisor only);
4. starts the mock API, the worker and the app, and stops them all if any one of them stops.

This is a demo-only shape, recorded as debt (TD-56): in every other deployment the app, the worker and the mock API
are separate services, as in Compose and the AWS Terraform.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy import create_engine, text

RESET_EVERY = timedelta(hours=24)
MOCK_PORT = 8020


@dataclass(frozen=True)
class Names:
    owner: str = "loyalty_owner"
    app: str = "loyalty_app"
    mock: str = "mock_api"
    app_db: str = "loyalty"
    mock_db: str = "mock_customer_api"


DEFAULT_NAMES = Names()


def role_password(secret: str, role: str) -> str:
    """Stable per role and per key: the container can rebuild every connection string from the key alone."""
    return hmac.new(secret.encode(), f"demo-role:{role}".encode(), hashlib.sha256).hexdigest()[:40]


def _psycopg(url: str) -> str:
    for scheme in ("postgresql://", "postgres://"):
        if url.startswith(scheme):
            return "postgresql+psycopg://" + url[len(scheme) :]
    return url


def url_for(admin_url: str, user: str, password: str, database: str) -> str:
    parts = urlsplit(
        admin_url.replace("postgresql://", "postgresql+psycopg://", 1).replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    )
    host = parts.hostname or "localhost"
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}" + (f":{parts.port}" if parts.port else "")
    return urlunsplit((parts.scheme, netloc, f"/{database}", parts.query, ""))


def provision(admin_url: str, secret: str, names: Names = DEFAULT_NAMES) -> dict[str, str]:
    """Roles and databases, made if missing and passwords set every time. Returns the three connection strings."""
    admin = create_engine(_psycopg(admin_url), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        for role in (names.owner, names.app, names.mock):
            exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar()
            if not exists:
                conn.execute(text(f'CREATE ROLE "{role}" LOGIN'))
            conn.execute(text(f"ALTER ROLE \"{role}\" WITH LOGIN PASSWORD '{role_password(secret, role)}'"))
        for database, owner in ((names.app_db, names.owner), (names.mock_db, names.mock)):
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": database}).scalar()
            if not exists:
                conn.execute(text(f'GRANT "{owner}" TO CURRENT_USER'))  # needed to hand the database to that owner
                conn.execute(text(f'CREATE DATABASE "{database}" OWNER "{owner}"'))
    admin.dispose()
    return {
        "owner": url_for(admin_url, names.owner, role_password(secret, names.owner), names.app_db),
        "app": url_for(admin_url, names.app, role_password(secret, names.app), names.app_db),
        "mock": url_for(admin_url, names.mock, role_password(secret, names.mock), names.mock_db),
    }


def grant_app_role(owner_url: str, names: Names = DEFAULT_NAMES) -> None:
    """The app role's rights, as `infrastructure/postgres/sql/app-owner.sql` sets them: data, not schema; audit
    history append-only."""
    engine = create_engine(owner_url, isolation_level="AUTOCOMMIT")
    app = names.app
    with engine.connect() as conn:
        conn.execute(text(f'GRANT CONNECT ON DATABASE "{names.app_db}" TO "{app}"'))
        conn.execute(text(f'GRANT USAGE ON SCHEMA public TO "{app}"'))
        conn.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{app}"'))
        conn.execute(text(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{app}"'))
        for table in ("case_events", "system_events"):
            conn.execute(text(f'REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM "{app}"'))
        conn.execute(text(f'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON alembic_version FROM "{app}"'))
    engine.dispose()


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, env=env, check=True)  # noqa: S603 - fixed commands from this module


def wait_for(url: str, seconds: float = 120) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3):  # noqa: S310 - a fixed local URL
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError(f"{url} didn't answer within {seconds:.0f} s")


def reset_due(owner_url: str) -> bool:
    engine = create_engine(owner_url)
    with engine.connect() as conn:
        last = conn.execute(text("SELECT max(at_utc) FROM system_events WHERE action = 'demo_reset'")).scalar()
    engine.dispose()
    return last is None or str(last) < (datetime.now(UTC) - RESET_EVERY).strftime("%Y-%m-%dT%H:%M:%S")


def daily_reset(urls: dict[str, str], seed_dir: str) -> None:
    """Empty the demo's cases (as the owner) and reload the synthetic world straight into the mock database, before
    the mock API starts: its control endpoints stay off in public demo mode (TD-11)."""
    from pathlib import Path

    from app.persistence.database import make_engine, make_sessions
    from app.services import demo, jobs
    from app.services.instrumentation import record_system
    from mock_customer_api import db as mock_db
    from mock_customer_api.seed import seed as seed_mock

    with make_sessions(make_engine(urls["owner"]))() as s:
        removed = demo.reset(s)
        record_system(s, jobs.SYSTEM, "demo_reset", removed=removed)
        s.commit()
    counts = seed_mock(mock_db.make_sessions(mock_db.make_engine(urls["mock"])), Path(seed_dir), reset=True)
    print(
        "demo reset: removed " + str(removed) + " cases; mock world " + ", ".join(f"{k} {v}" for k, v in counts.items())
    )


def main() -> int:
    admin_url = os.environ["DEMO_DATABASE_URL"]
    secret = os.environ["APP_SECRET_KEY"]
    if len(secret) < 32:
        raise SystemExit("APP_SECRET_KEY must be at least 32 characters")
    urls = provision(admin_url, secret)
    env = {
        **os.environ,
        "PUBLIC_DEMO_MODE": "true",
        "AI_PROVIDER": "mock",
        "FEATURE_LIVE_AI": "false",
        "MOCK_API_URL": f"http://127.0.0.1:{MOCK_PORT}",
        "MOCK_API_DATABASE_URL": urls["mock"],
        "MOCK_API_TOKEN": role_password(secret, "mock-api-token"),
        "MOCK_API_SEED_DIR": os.environ["MOCK_API_SEED_DIR"],  # set by the image (Dockerfile.demo), not by the app
        "DEMO_USER_PASSWORD": role_password(secret, "demo-accounts"),  # no one types it: visitors use the buttons
        "LOG_FORMAT": "json",
    }
    py = sys.executable
    run([py, "-m", "alembic", "-c", "mock_customer_api/alembic.ini", "upgrade", "head"], env)
    run([py, "-m", "alembic", "upgrade", "head"], {**env, "DATABASE_URL": urls["owner"]})
    grant_app_role(urls["owner"])
    app_env = {**env, "DATABASE_URL": urls["app"]}
    if reset_due(urls["owner"]):
        daily_reset(urls, env["MOCK_API_SEED_DIR"])
        run([py, "-m", "app.seed", "--dataset", "demo", "--skip-mock"], app_env)  # accounts (no admin), policies
    mock = subprocess.Popen(  # noqa: S603
        [
            py,
            "-m",
            "uvicorn",
            "--factory",
            "mock_customer_api.api:serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(MOCK_PORT),
        ],
        env=env,
    )
    children = [mock]
    try:
        wait_for(f"http://127.0.0.1:{MOCK_PORT}/healthz")

        worker = subprocess.Popen([py, "-m", "app.worker"], env=app_env)  # noqa: S603
        children.append(worker)
        port = os.environ.get("PORT", "8010")
        app = subprocess.Popen(  # noqa: S603
            [py, "-m", "uvicorn", "--factory", "app.main:serve", "--host", "0.0.0.0", "--port", port],  # noqa: S104
            env=app_env,
        )
        children.append(app)
        while all(child.poll() is None for child in children):
            time.sleep(2)
        return 1  # one of them stopped: stop the rest, and let the host restart the container
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    sys.exit(main())
