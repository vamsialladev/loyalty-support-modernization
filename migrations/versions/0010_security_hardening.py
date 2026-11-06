"""Rate limits, recovery and API tokens, OIDC links, customer scope, legal hold (spec C.4, C.5; SEC-07, SEC-08, ENT-10).

Tokens are stored only as hashes. `users.customer_id` is filled with the one customer existing rows already belong to.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limits",
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "recovery_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.Column("expires_at_utc", sa.String(length=20), nullable=False),
        sa.Column("used_at_utc", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_table(
        "api_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.Column("expires_at_utc", sa.String(length=20), nullable=False),
        sa.Column("revoked_at_utc", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("external_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("customer_id", sa.String(length=32), nullable=False, server_default="hg-demo"))
        batch.create_index("uq_users_external_id", ["external_id"], unique=True)
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("personal_data_removed_at_utc", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("personal_data_removed_at_utc")
        batch.drop_column("legal_hold")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("uq_users_external_id")
        batch.drop_column("customer_id")
        batch.drop_column("external_id")
    op.drop_table("api_tokens")
    op.drop_table("recovery_tokens")
    op.drop_table("rate_limits")
