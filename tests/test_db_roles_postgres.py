"""Live checks on a running stack's database roles (ADR-0036): each role has a stored password, and a blank password
is refused over TCP. They read no secret and print none.

They need TEST_DB_ROLES_CONTAINER (the Postgres container, e.g. loyalty-db-1); `scripts\\stack.ps1 -Action
verify-roles` and the compose check set it. Without it they are SKIPPED with that reason; they never silently pass.
"""

from __future__ import annotations

import os
import subprocess

import psycopg
import pytest

CONTAINER = os.environ.get("TEST_DB_ROLES_CONTAINER", "")
HOST, PORT = os.environ.get("TEST_DB_ROLES_HOST", "127.0.0.1:5432").rsplit(":", 1)
ROLES = {"loyalty_app": "loyalty", "mock_api": "mock_customer_api"}

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not CONTAINER, reason="TEST_DB_ROLES_CONTAINER is not set (no running stack named)"),
]


def test_each_role_has_a_stored_scram_password() -> None:
    # Inside the container, over the local socket as the bootstrap superuser; only booleans come back.
    sql = (
        "select rolname || '=' || coalesce(rolpassword like 'SCRAM-SHA-256$%', false) "
        "from pg_authid where rolname in ('loyalty_app', 'mock_api') order by 1"
    )
    result = subprocess.run(
        ["docker", "exec", CONTAINER, "sh", "-c", 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -c "$0"', sql],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["loyalty_app=true", "mock_api=true"]


@pytest.mark.parametrize(("role", "database"), ROLES.items())
def test_blank_password_is_refused(role: str, database: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # No fallback credentials: libpq would otherwise try PGPASSWORD or a password file.
    monkeypatch.delenv("PGPASSWORD", raising=False)
    with pytest.raises(psycopg.OperationalError) as refused:
        psycopg.connect(
            host=HOST,
            port=int(PORT),
            user=role,
            dbname=database,
            password="",
            passfile=os.devnull,
            connect_timeout=5,
        )
    assert "password" in str(refused.value).lower()
