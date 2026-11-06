"""Recommendations, feedback and case groups: what arm B and the complete console need (spec B.11; ADR-0062, ADR-0063).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("group_ref", sa.String(length=32), nullable=True))
        batch.create_index("ix_cases_group_ref", ["group_ref"])
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=32), nullable=False),
        sa.Column("member_number", sa.String(length=32), nullable=True),
        sa.Column("stay_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.String(length=64), nullable=True),
        sa.Column("points_owed", sa.Integer(), nullable=False),
        sa.Column("earned_points", sa.Integer(), nullable=False),
        sa.Column("credited_points", sa.Integer(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=True),
        sa.Column("checkout_day", sa.String(length=10), nullable=True),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendations_case_id", "recommendations", ["case_id"])
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("rating", sa.String(length=16), nullable=True),
        sa.Column("reason_code", sa.String(length=48), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=64), nullable=False),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_case_id", "feedback", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_feedback_case_id", table_name="feedback")
    op.drop_table("feedback")
    op.drop_index("ix_recommendations_case_id", table_name="recommendations")
    op.drop_table("recommendations")
    with op.batch_alter_table("cases") as batch:
        batch.drop_index("ix_cases_group_ref")
        batch.drop_column("group_ref")
