"""Online QA samples: closed cases queued for a person to review against the QA rubric (spec E5; ENT-18).

One new table and nothing else, so rolling back drops only the samples. Results are codes, never free text.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qa_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("arm", sa.String(length=8), nullable=False),
        sa.Column("rate_percent", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("closed_by", sa.String(length=64), nullable=False),
        sa.Column("sampled_at_utc", sa.String(length=20), nullable=False),
        sa.Column("reviewer", sa.String(length=64), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column("reviewed_at_utc", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", name="uq_qa_samples_case"),
    )
    op.create_index("ix_qa_samples_status", "qa_samples", ["status"])


def downgrade() -> None:
    op.drop_index("ix_qa_samples_status", table_name="qa_samples")
    op.drop_table("qa_samples")
