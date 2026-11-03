"""Arm A case tables and local demo auth (Milestone 5, ADR-0045, ADR-0046). Mirrors `app/persistence/models.py`.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference", sa.String(length=32), nullable=False),
        sa.Column("arm", sa.String(length=8), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("queue", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("assigned_to", sa.String(length=64), nullable=True),
        sa.Column("received_at_utc", sa.String(length=20), nullable=False),
        sa.Column("source_ref", sa.String(length=64), nullable=True),
        sa.Column("resolution_code", sa.String(length=48), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_cases_queue_status", "cases", ["queue", "status"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "adjustment_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("member_number", sa.String(length=32), nullable=False),
        sa.Column("stay_id", sa.String(length=32), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=48), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("requested_at_utc", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_adjustment_requests_case_id"), "adjustment_requests", ["case_id"], unique=False)
    op.create_index(op.f("ix_adjustment_requests_stay_id"), "adjustment_requests", ["stay_id"], unique=False)
    op.create_table(
        "case_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("at_utc", sa.String(length=32), nullable=False),
        sa.Column("sim_time_utc", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "step", name="uq_case_events_step"),
    )
    op.create_table(
        "case_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("attached_by", sa.String(length=64), nullable=False),
        sa.Column("attached_at_utc", sa.String(length=20), nullable=False),
        sa.Column("sim_time_utc", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_evidence_case_id"), "case_evidence", ["case_id"], unique=False)
    op.create_table(
        "case_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_notes_case_id"), "case_notes", ["case_id"], unique=False)
    op.create_table(
        "case_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("request_ref", sa.String(length=64), nullable=True),
        sa.Column("received_at_utc", sa.String(length=20), nullable=False),
        sa.Column("contact_channel", sa.String(length=32), nullable=False),
        sa.Column("sender_email", sa.String(length=255), nullable=True),
        sa.Column("form_member_number", sa.String(length=32), nullable=True),
        sa.Column("form_confirmation", sa.String(length=32), nullable=True),
        sa.Column("form_name", sa.String(length=120), nullable=True),
        sa.Column("form_property", sa.String(length=32), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("attachment_names", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_requests_case_id"), "case_requests", ["case_id"], unique=False)
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at_utc", sa.String(length=20), nullable=False),
        sa.Column("expires_at_utc", sa.String(length=20), nullable=False),
        sa.Column("revoked_at_utc", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("adjustment_request_id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(length=32), nullable=False),
        sa.Column("decided_by", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_at_utc", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["adjustment_request_id"],
            ["adjustment_requests.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adjustment_request_id", name="uq_approvals_one_decision"),
        sa.UniqueConstraint("uid"),
    )
    op.create_table(
        "execution_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("adjustment_request_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("started_by", sa.String(length=64), nullable=False),
        sa.Column("started_at_utc", sa.String(length=20), nullable=False),
        sa.Column("finished_at_utc", sa.String(length=20), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("upstream_adjustment_id", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["adjustment_request_id"],
            ["adjustment_requests.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_execution_attempts_adjustment_request_id"),
        "execution_attempts",
        ["adjustment_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_attempts_idempotency_key"), "execution_attempts", ["idempotency_key"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_attempts_idempotency_key"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_adjustment_request_id"), table_name="execution_attempts")
    op.drop_table("execution_attempts")
    op.drop_table("approvals")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_case_requests_case_id"), table_name="case_requests")
    op.drop_table("case_requests")
    op.drop_index(op.f("ix_case_notes_case_id"), table_name="case_notes")
    op.drop_table("case_notes")
    op.drop_index(op.f("ix_case_evidence_case_id"), table_name="case_evidence")
    op.drop_table("case_evidence")
    op.drop_table("case_events")
    op.drop_index(op.f("ix_adjustment_requests_stay_id"), table_name="adjustment_requests")
    op.drop_index(op.f("ix_adjustment_requests_case_id"), table_name="adjustment_requests")
    op.drop_table("adjustment_requests")
    op.drop_table("users")
    op.drop_index("ix_cases_queue_status", table_name="cases")
    op.drop_table("cases")
