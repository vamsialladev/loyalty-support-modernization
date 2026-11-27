"""Break-glass grants: time-limited administrator access with a reason (ENT-26, ADR-0093).

A new table only; nothing existing changes. Rolling back drops the table. The app role gets its rights from
`infrastructure/postgres/sql/app-owner.sql` (all tables), as every other table does.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "break_glass_grants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_by", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("granted_at_utc", sa.String(20), nullable=False),
        sa.Column("expires_at_utc", sa.String(20), nullable=False),
        sa.Column("ended_at_utc", sa.String(20), nullable=True),
        sa.Column("end_reason", sa.String(16), nullable=True),
        sa.Column("ended_by", sa.String(64), nullable=True),
    )
    op.create_index("ix_break_glass_grants_user_open", "break_glass_grants", ["user_id", "ended_at_utc"])


def downgrade() -> None:
    op.drop_index("ix_break_glass_grants_user_open", table_name="break_glass_grants")
    op.drop_table("break_glass_grants")
