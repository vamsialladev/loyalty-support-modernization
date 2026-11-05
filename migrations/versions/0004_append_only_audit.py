"""Append-only audit history: the runtime role can add and read events, never change them (ADR-0058, WP-11).

The role split itself is `infrastructure/postgres/sql/app-owner.sql`, because creating a role needs a superuser. On
SQLite (offline tests) there are no roles, so this revision changes nothing there.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

RUNTIME_ROLE = "loyalty_app"
APPEND_ONLY = ("case_events", "system_events")


def _runtime_role_exists() -> bool:
    return bool(op.get_bind().scalar(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": RUNTIME_ROLE}))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql" or not _runtime_role_exists():
        return
    if bind.scalar(sa.text("SELECT current_user")) == RUNTIME_ROLE:
        raise RuntimeError(
            "migrations must run as the owner role, not loyalty_app. On a volume from before Milestone 6, run "
            "scripts\\stack.ps1 -Action up, which splits the role first (ADR-0058)."
        )
    for table in APPEND_ONLY:
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM {RUNTIME_ROLE}")
    op.execute(f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON alembic_version FROM {RUNTIME_ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql" or not _runtime_role_exists():
        return
    for table in APPEND_ONLY:
        op.execute(f"GRANT UPDATE, DELETE ON {table} TO {RUNTIME_ROLE}")
    op.execute(f"GRANT INSERT, UPDATE, DELETE ON alembic_version TO {RUNTIME_ROLE}")
