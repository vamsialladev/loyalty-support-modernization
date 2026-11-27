"""Cache tokens on each AI run, for provider prompt caching (L3; CACHE-02, ADR-0090).

Two integer columns with a server default of 0, so existing rows read as "no caching" and nothing is rewritten.
Rolling back drops only these two columns.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_runs") as batch:
        batch.add_column(sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("ai_runs") as batch:
        batch.drop_column("cache_write_tokens")
        batch.drop_column("cache_read_tokens")
