"""The browser stack's databases on Postgres, as CI runs them (TD-57).

The offline stack runs the app and the worker as two processes. On one SQLite file they race: a deferred `BEGIN`
that upgrades to a write gets `database is locked` at once while the other process writes (`tests/test_sqlite_engine.py`
keeps that as a strict expected failure). Postgres, which every deployment uses, has no such race. So when
`E2E_POSTGRES_URL` (a superuser URL for a throwaway server) is set, each browser test module gets its own app and mock
databases there, made the way the public demo makes them (`app.demo_launch.provision`, `grant_app_role`: the app runs
as a role that can't change the schema or rewrite audit history), and dropped afterwards.
Without it the stack stays on SQLite, so a developer needs no Postgres to run the browser tests.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import create_engine, text

from app.demo_launch import Names, _psycopg, grant_app_role, provision
from tests.conftest import ROOT


def names_for(module: str) -> Names:
    """One pair of databases per test module; the roles are shared (their passwords are reset on every provision)."""
    slug = re.sub(r"[^a-z0-9_]", "_", module.rsplit(".", 1)[-1].lower())[:40]
    return Names(
        owner="e2e_owner", app="e2e_app", mock="e2e_mock", app_db=f"e2e_{slug}_app", mock_db=f"e2e_{slug}_mock"
    )


def drop(admin_url: str, names: Names) -> None:
    """Remove both databases, closing any connection a stopped server left behind (Postgres 13+)."""
    admin = create_engine(_psycopg(admin_url), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        for database in (names.app_db, names.mock_db):
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
    admin.dispose()


def create(admin_url: str, module: str, secret: str, seed_dir: Path) -> tuple[Names, dict[str, str]]:
    """Fresh databases for one module: both migrated, the app role granted, the mock world seeded.

    Returns the names (for `drop`) and the `owner`, `app` and `mock` connection strings.
    """
    from alembic import command
    from alembic.config import Config

    from mock_customer_api import db as mock_db
    from mock_customer_api.seed import seed

    names = names_for(module)
    drop(admin_url, names)  # a run that was killed may have left them
    urls = provision(admin_url, secret, names)
    for ini, url in (("mock_customer_api/alembic.ini", urls["mock"]), ("alembic.ini", urls["owner"])):
        cfg = Config(str(ROOT / ini))
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
    grant_app_role(urls["owner"], names)
    engine = mock_db.make_engine(urls["mock"])
    seed(mock_db.make_sessions(engine), seed_dir)
    engine.dispose()
    return names, urls
