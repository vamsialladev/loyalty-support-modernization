"""The W3C trace context a job was queued under, so the worker's spans join the request's trace (OPS-02, ADR-0077).

One nullable column and nothing else. Older code ignores it, so rolling the app back without the downgrade is safe;
the downgrade drops only this column (the value is telemetry, not business data).

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("trace_parent", sa.String(length=55), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("trace_parent")
