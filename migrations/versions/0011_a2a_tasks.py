"""A2A tasks from the loyalty coordinator to the reservation evidence specialist (spec G.4; RFC-0004; ADR-0071).

Adds one table and nothing else, so turning A2A off or rolling back leaves every existing table as it was.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "a2a_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("peer", sa.String(length=255), nullable=False),
        sa.Column("remote_task_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("notification_token_hash", sa.String(length=64), nullable=True),
        sa.Column("artifact", sa.JSON(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.String(length=120), nullable=True),
        sa.Column("correlation_id", sa.String(length=32), nullable=True),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.Column("finished_at_utc", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_a2a_tasks_case_id", "a2a_tasks", ["case_id"])
    op.create_index(
        "uq_a2a_tasks_active",
        "a2a_tasks",
        ["case_id"],
        unique=True,
        postgresql_where=sa.text("state = 'submitted'"),
        sqlite_where=sa.text("state = 'submitted'"),
    )


def downgrade() -> None:
    op.drop_index("uq_a2a_tasks_active", table_name="a2a_tasks")
    op.drop_index("ix_a2a_tasks_case_id", table_name="a2a_tasks")
    op.drop_table("a2a_tasks")
