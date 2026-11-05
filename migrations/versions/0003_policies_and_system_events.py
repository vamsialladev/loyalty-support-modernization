"""Policy versions and chunks, full-text search, system events (ADR-0057). Mirrors `app/persistence/models.py`.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("at_utc", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("policy_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("effective_from", sa.String(length=10), nullable=False),
        sa.Column("effective_to", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.Column("published_by", sa.String(length=64), nullable=True),
        sa.Column("published_at_utc", sa.String(length=20), nullable=True),
        sa.Column("regression", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "policy_id", "version", name="uq_policy_versions_version"),
    )
    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_version_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.String(length=16), nullable=False),
        sa.Column("heading", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_version_id", "section_id", name="uq_policy_chunks_section"),
    )
    op.create_index(op.f("ix_policy_chunks_policy_version_id"), "policy_chunks", ["policy_version_id"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_policy_chunks_search ON policy_chunks "
            "USING gin (to_tsvector('english', heading || ' ' || text))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX ix_policy_chunks_search")
    op.drop_index(op.f("ix_policy_chunks_policy_version_id"), table_name="policy_chunks")
    op.drop_table("policy_chunks")
    op.drop_table("policy_versions")
    op.drop_table("system_events")
