"""Approval binding: what a request proposes, what an approval is bound to, and when each ends (ADR-0059).

Existing approvals get no binding, so they can't be executed: they must be approved again.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("sim_now_utc", sa.String(length=20), nullable=True))
    with op.batch_alter_table("adjustment_requests") as batch:
        batch.add_column(sa.Column("evidence_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("policy_refs", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("checkout_day", sa.String(length=10), nullable=True))
        batch.add_column(sa.Column("invalidated_at_utc", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("invalidated_reason", sa.String(length=48), nullable=True))
    with op.batch_alter_table("approvals") as batch:
        batch.add_column(sa.Column("expires_at_utc", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("binding_mac", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("approvals") as batch:
        batch.drop_column("binding_mac")
        batch.drop_column("expires_at_utc")
    with op.batch_alter_table("adjustment_requests") as batch:
        batch.drop_column("invalidated_reason")
        batch.drop_column("invalidated_at_utc")
        batch.drop_column("checkout_day")
        batch.drop_column("policy_refs")
        batch.drop_column("evidence_hash")
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("sim_now_utc")
