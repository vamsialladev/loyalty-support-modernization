"""The one-container public demo (SEC-18, ADR-0087): connection strings derived from the key, and provisioning on a
real Postgres (marked `postgres`; it uses its own role and database names, so it never touches the test roles)."""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from app.demo_launch import Names, grant_app_role, provision, role_password, url_for

ROOT = Path(__file__).resolve().parent.parent
NEON = "postgresql://neondb_owner:owner-pw@ep-example-123.us-east-2.aws.neon.tech/neondb?sslmode=require"


def test_each_role_gets_its_own_stable_password_from_the_key() -> None:
    assert role_password("k" * 32, "loyalty_app") == role_password("k" * 32, "loyalty_app")
    assert role_password("k" * 32, "loyalty_app") != role_password("k" * 32, "loyalty_owner")
    assert role_password("k" * 32, "loyalty_app") != role_password("j" * 32, "loyalty_app")  # a new key rotates them


def test_connection_strings_keep_the_host_and_tls_and_change_user_and_database() -> None:
    url = url_for(NEON, "loyalty_app", "p@ss/word", "loyalty")
    assert url == (
        "postgresql+psycopg://loyalty_app:p%40ss%2Fword@ep-example-123.us-east-2.aws.neon.tech/loyalty?sslmode=require"
    )
    assert "owner-pw" not in url


def test_the_render_blueprint_is_free_main_only_manual_mock_and_holds_no_secret() -> None:
    import yaml

    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    (service,) = blueprint["services"]
    assert (service["plan"], service["branch"], service["autoDeploy"]) == ("free", "main", False)
    env = {e["key"]: e for e in service["envVars"]}
    assert env["DEMO_DATABASE_URL"] == {"key": "DEMO_DATABASE_URL", "sync": False}  # pasted in Render, never here
    assert env["APP_SECRET_KEY"]["generateValue"] is True
    assert env["PUBLIC_DEMO_MODE"]["value"] == "true" and env["AI_PROVIDER"]["value"] == "mock"
    assert env["FEATURE_LIVE_AI"]["value"] == "false"
    assert not any("postgres" in str(e.get("value", "")) for e in env.values())


def test_the_demo_image_copies_named_folders_and_the_worlds_operational_files_only() -> None:
    text = (ROOT / "Dockerfile.demo").read_text(encoding="utf-8")
    final = text.split("FROM base AS demo", 1)[1]
    copied = {line.split()[1] for line in final.splitlines() if line.startswith("COPY ") and "--from" not in line}
    assert copied == {"alembic.ini", "migrations", "app", "config", "policies", "customer_shapes", "mock_customer_api"}
    assert "COPY --from=world /build/seed_data/v1 ./seed_data/v1" in final
    for never in ("benchmarks", "evaluations", "tests", "docs", "seed_data/generator", "--group data"):
        assert never not in final, never
    assert "USER 10001" in final


@pytest.mark.postgres
def test_provisioning_makes_roles_databases_and_append_only_grants() -> None:
    admin_url = os.environ.get("TEST_MOCK_API_DATABASE_URL")
    if not admin_url:
        pytest.skip("TEST_MOCK_API_DATABASE_URL is not set")
    tag = secrets.token_hex(3)
    names = Names(
        owner=f"demo_owner_{tag}",
        app=f"demo_app_{tag}",
        mock=f"demo_mock_{tag}",
        app_db=f"demo_app_db_{tag}",
        mock_db=f"demo_mock_db_{tag}",
    )
    secret = secrets.token_urlsafe(32)
    urls = provision(admin_url, secret, names)
    assert provision(admin_url, secret, names) == urls  # running it again changes nothing
    env = {**os.environ, "DATABASE_URL": urls["owner"]}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)
    grant_app_role(urls["owner"], names)
    app = create_engine(urls["app"])
    with app.begin() as conn:
        conn.execute(text("SELECT count(*) FROM cases"))  # the app role reads and writes data
    with pytest.raises(ProgrammingError), app.begin() as conn:
        conn.execute(text("DELETE FROM case_events"))  # but never rewrites audit history
    with pytest.raises(ProgrammingError), app.begin() as conn:
        conn.execute(text("CREATE TABLE sneaky (id int)"))  # nor the schema
    app.dispose()
    admin = create_engine(admin_url.replace("postgresql://", "postgresql+psycopg://", 1), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        for database in (names.app_db, names.mock_db):
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        for role in (names.app, names.mock, names.owner):
            conn.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
    admin.dispose()
