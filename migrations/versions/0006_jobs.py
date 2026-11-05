"""The durable job queue (ADR-0060). Mirrors `app/persistence/models.py`.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

ACTIVE = sa.text("status IN ('queued', 'running')")


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("dedupe_key", sa.String(length=80), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("run_after_utc", sa.String(length=20), nullable=False),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_token", sa.String(length=32), nullable=True),
        sa.Column("lease_expires_utc", sa.String(length=20), nullable=True),
        sa.Column("heartbeat_at_utc", sa.String(length=20), nullable=True),
        sa.Column("last_error", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=32), nullable=True),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.Column("finished_at_utc", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_claim", "jobs", ["status", "run_after_utc"], unique=False)
    op.create_index("uq_jobs_active", "jobs", ["dedupe_key"], unique=True, postgresql_where=ACTIVE, sqlite_where=ACTIVE)


def downgrade() -> None:
    op.drop_index("uq_jobs_active", table_name="jobs")
    op.drop_index("ix_jobs_claim", table_name="jobs")
    op.drop_table("jobs")
