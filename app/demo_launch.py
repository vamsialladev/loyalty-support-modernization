"""The public demo in one container (spec L1; SEC-18, LIVE-02; ADR-0087): `python -m app.demo_launch`.

The demo runs as one Cloud Run service (max 1 instance, min 0, instance-based billing; ADR-0088,
`docs/hosting-cloud-run.md`), so this process starts the mock customer API and the worker as child processes, and the
app in the foreground on `$PORT`. It needs **one** secret besides `APP_SECRET_KEY`: `DEMO_DATABASE_URL`, the Neon
project's owner connection string, which the owner puts in Google's Secret Manager. From it, on every start, it:

1. makes the three roles (`loyalty_owner`, `loyalty_app`, `mock_api`) and the two databases, if missing, with
   passwords derived from `APP_SECRET_KEY` (so nothing else needs storing, and changing the key rotates them);
2. runs both databases' migrations, then the app role's grants, including append-only audit (ADR-0058);
3. once a day, empties the demo's cases (`app.services.demo.reset`, as the owner), then loads the synthetic world,
   the demo accounts (agent and supervisor only) and a few sample cases (`app/services/demo_samples.py`);
4. starts the mock API, the worker and the app, and stops them all if any one of them stops.

While it runs, it checks every hour whether a reset is due. An idle instance usually stops within 15 minutes and
resets on its next start, but one kept busy for a day would otherwise never reset. When one is due, it stops the
three processes, resets, and starts them again in this process, so the reset never depends on the host restarting a
process that exits. The demo is unavailable for those seconds.

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
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

NOT_SET_UP_YET = {"42P01", "42501"}  # undefined_table, insufficient_privilege

AUDIT_TABLES = ("case_events", "system_events")  # append-only for the app role (ADR-0058)
RESET_EVERY = timedelta(hours=24)
RESET_CHECK_SECONDS = 3600.0  # how often a running demo asks whether a reset is due
MOCK_PORT = 8020
UVICORN = (sys.executable, "-m", "uvicorn", "--factory")
# After the reset: the demo accounts (agent and supervisor only), the policies, and the sample cases, so a visitor never
# lands on an empty queue (app/services/demo_samples.py). The mock world is loaded directly, before the mock API starts.
SEED_ARGS = ("-m", "app.seed", "--dataset", "demo", "--skip-mock", "--sample-cases")


class Phases:
    """Startup timings in the container's log, one line per phase: its name and seconds, never a value. The first
    database connection is its own phase, so a Neon wake-up shows apart from this process's own work."""

    def __init__(self, clock: Callable[[], float] = time.monotonic, out: Callable[[str], None] = print) -> None:
        self._clock, self._out = clock, out
        self._start = clock()

    @contextmanager
    def __call__(self, name: str) -> Iterator[None]:
        began = self._clock()
        try:
            yield
        except BaseException:
            self._out(f"demo startup: {name} failed after {self._clock() - began:.2f} s")
            raise
        self._out(f"demo startup: {name} {self._clock() - began:.2f} s")

    def total(self, until: str) -> None:
        self._out(f"demo startup: total until {until} {self._clock() - self._start:.2f} s")


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
        for table in AUDIT_TABLES:
            conn.execute(text(f'REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM "{app}"'))
        conn.execute(text(f'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON alembic_version FROM "{app}"'))
    engine.dispose()


def migration_heads() -> tuple[str, str]:
    """The app's and the mock API's migration heads, read from the code (no database)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parent.parent
    heads = []
    for ini in (root / "alembic.ini", root / "mock_customer_api" / "alembic.ini"):
        head = ScriptDirectory.from_config(Config(str(ini))).get_current_head()
        if head is None:
            raise RuntimeError(f"{ini.name} has no migration head")
        heads.append(head)
    return heads[0], heads[1]


# The app role's rights, as the app role sees them. Each row must hold for every table, or setup runs again.
# By table OID, not by name: a name built with format() beside a bound parameter didn't resolve (42P01). And CASE,
# because a sequence check ran on an index before the relkind filter. Both found by tests/test_demo_launch.py's
# Postgres test (verification log, M12 row 45).
GRANTS_IN_PLACE = text(
    """
    SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND CASE  -- CASE, not AND: Postgres may evaluate WHERE terms in any order
        WHEN c.relkind NOT IN ('r', 'p') THEN false
        WHEN NOT has_table_privilege(c.oid, 'SELECT') THEN true
        WHEN c.relname = 'alembic_version' THEN has_table_privilege(c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE')
        WHEN c.relname = ANY(:audit) THEN NOT has_table_privilege(c.oid, 'INSERT')
            OR has_table_privilege(c.oid, 'UPDATE, DELETE, TRUNCATE')
        ELSE NOT (has_table_privilege(c.oid, 'INSERT') AND has_table_privilege(c.oid, 'UPDATE')
            AND has_table_privilege(c.oid, 'DELETE'))
    END
    """
)
SEQUENCES_IN_PLACE = text(
    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = 'public' AND CASE WHEN c.relkind <> 'S' THEN false "
    "ELSE NOT has_sequence_privilege(c.oid, 'USAGE, SELECT') END"
)


def set_up_already(admin_url: str, secret: str, names: Names = DEFAULT_NAMES) -> dict[str, str] | None:
    """The fast path (LIVE-06): the three connection strings when the roles sign in with this key's passwords, both
    databases are at the code's migration heads, and the app role's grants are exactly in place. Otherwise None, and
    the full setup runs, as before. Reads only; never changes the database."""
    urls = {
        "owner": url_for(admin_url, names.owner, role_password(secret, names.owner), names.app_db),
        "app": url_for(admin_url, names.app, role_password(secret, names.app), names.app_db),
        "mock": url_for(admin_url, names.mock, role_password(secret, names.mock), names.mock_db),
    }
    app_head, mock_head = migration_heads()
    try:
        for url, head, check_grants in ((urls["app"], app_head, True), (urls["mock"], mock_head, False)):
            engine = create_engine(url)
            try:
                with engine.connect() as conn:
                    try:
                        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                    except ProgrammingError as error:
                        if getattr(error.orig, "sqlstate", None) in NOT_SET_UP_YET:
                            return None  # no migrations table yet, or no grant to read it
                        raise
                    if version != head:
                        return None
                    if check_grants and (
                        conn.execute(GRANTS_IN_PLACE, {"audit": list(AUDIT_TABLES)}).scalar()
                        or conn.execute(SEQUENCES_IN_PLACE).scalar()
                    ):
                        return None
            finally:
                engine.dispose()
        owner = create_engine(urls["owner"])  # the owner's password too: migrations and resets sign in as it
        try:
            with owner.connect() as conn:
                conn.execute(text("SELECT 1"))
        finally:
            owner.dispose()
    except OperationalError:
        return None  # a role or database missing, or a password from another key: the server refused the sign-in
    # Any other database error is a bug in this check: it fails the start loudly, never falls back silently.
    return urls


def first_connection(admin_url: str) -> None:
    """One `SELECT 1` as the owner: on Neon Free, the first connection after a quiet spell also wakes the compute."""
    engine = create_engine(_psycopg(admin_url))
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
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


def supervise(
    start: Callable[[], list[subprocess.Popen[bytes]]],
    stop: Callable[[list[subprocess.Popen[bytes]]], None],
    is_due: Callable[[], bool],
    reset: Callable[[], None],
    *,
    check_seconds: float = RESET_CHECK_SECONDS,
    poll_seconds: float = 2.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run the processes; reset in place when a reset falls due; return 1 when one of them stops by itself."""
    while True:
        children = start()
        next_check = clock() + check_seconds
        try:
            while all(child.poll() is None for child in children):
                sleep(poll_seconds)
                if clock() >= next_check:
                    next_check = clock() + check_seconds
                    if is_due():
                        break
            else:
                return 1  # one of them stopped: stop the rest, and let the host restart the container
        finally:
            stop(children)
        print("demo reset due while running: processes stopped for the reset")
        reset()


def stop_children(children: list[subprocess.Popen[bytes]]) -> None:
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            child.kill()


def main() -> int:
    admin_url = os.environ["DEMO_DATABASE_URL"]
    secret = os.environ["APP_SECRET_KEY"]
    if len(secret) < 32:
        raise SystemExit("APP_SECRET_KEY must be at least 32 characters")
    phases = Phases()
    with phases("first database connection (includes a Neon wake-up)"):
        first_connection(admin_url)
    with phases("setup check (roles, migration heads, grants)"):
        ready = set_up_already(admin_url, secret)
    if ready is None:
        with phases("roles and databases"):
            urls = provision(admin_url, secret)
    else:
        urls = ready
        print("demo startup: already set up, so roles, migrations and grants are skipped")
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
    if ready is None:
        with phases("mock API migrations"):
            run([py, "-m", "alembic", "-c", "mock_customer_api/alembic.ini", "upgrade", "head"], env)
        with phases("app migrations"):
            run([py, "-m", "alembic", "upgrade", "head"], {**env, "DATABASE_URL": urls["owner"]})
        with phases("app role grants"):
            grant_app_role(urls["owner"])
    app_env = {**env, "DATABASE_URL": urls["app"]}
    port = os.environ.get("PORT", "8010")
    first_start = [True]

    def reset() -> None:
        daily_reset(urls, env["MOCK_API_SEED_DIR"])
        run([py, *SEED_ARGS], app_env)  # accounts (no admin), policies, sample cases

    def start() -> list[subprocess.Popen[bytes]]:
        mock = subprocess.Popen(  # noqa: S603
            [*UVICORN, "mock_customer_api.api:serve", "--host", "127.0.0.1", "--port", str(MOCK_PORT)],
            env=env,
        )
        children = [mock]
        try:
            with phases("the mock API answers"):
                wait_for(f"http://127.0.0.1:{MOCK_PORT}/healthz")
            children.append(subprocess.Popen([py, "-m", "app.worker"], env=app_env))  # noqa: S603
            children.append(
                subprocess.Popen(  # noqa: S603
                    [*UVICORN, "app.main:serve", "--host", "0.0.0.0", "--port", port],  # noqa: S104
                    env=app_env,
                )
            )
            if first_start[0]:  # time the first start only; an in-place reset prints its own lines
                first_start[0] = False
                with phases("the app answers"):
                    wait_for(f"http://127.0.0.1:{port}/healthz")
                phases.total("the app answers")
        except BaseException:
            stop_children(children)
            raise
        return children

    with phases("reset check"):
        due = reset_due(urls["owner"])
    if due:
        with phases("daily reset and sample cases"):
            reset()
    check = float(os.environ.get("DEMO_RESET_CHECK_SECONDS", RESET_CHECK_SECONDS))  # shorter only to test the path
    return supervise(start, stop_children, lambda: reset_due(urls["owner"]), reset, check_seconds=check)


if __name__ == "__main__":
    sys.exit(main())
