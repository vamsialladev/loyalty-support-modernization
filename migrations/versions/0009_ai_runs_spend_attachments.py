"""AI runs, their steps, spending caps and attachments (RFC-0002; spec B.9, LIVE-05, Appendix H).

Steps hold what happened, never the content of evidence: tool name, a hash of the arguments, status, size and timing.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("caller", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("policy_versions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stop_reason", sa.String(length=32), nullable=True),
        sa.Column("turns", sa.Integer(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_microusd", sa.Integer(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("problems", sa.JSON(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("correlation_id", sa.String(length=32), nullable=True),
        sa.Column("started_at_utc", sa.String(length=20), nullable=False),
        sa.Column("finished_at_utc", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_runs_case_id", "ai_runs", ["case_id"])
    op.create_table(
        "ai_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("arguments_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("result_chars", sa.Integer(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_steps_run_id", "ai_steps", ["run_id"])
    op.create_table(
        "ai_spend",
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("period"),
    )
    op.create_table(
        "case_attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=128), nullable=False),
        sa.Column("media_type", sa.String(length=48), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("added_by", sa.String(length=64), nullable=False),
        sa.Column("added_at_utc", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_attachments_case_id", "case_attachments", ["case_id"])
    with op.batch_alter_table("recommendations") as batch:
        batch.add_column(sa.Column("ai_run_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("ai", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("recommendations") as batch:
        batch.drop_column("ai")
        batch.drop_column("ai_run_id")
    op.drop_index("ix_case_attachments_case_id", table_name="case_attachments")
    op.drop_table("case_attachments")
    op.drop_table("ai_spend")
    op.drop_index("ix_ai_steps_run_id", table_name="ai_steps")
    op.drop_table("ai_steps")
    op.drop_index("ix_ai_runs_case_id", table_name="ai_runs")
    op.drop_table("ai_runs")
