"""Mock customer API: initial schema (members, stays, ledger, posting queue, idempotency, adjustments, tickets).

Revision ID: 0001
Revises:
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.String(20)
DATE = sa.String(10)


def upgrade() -> None:
    op.create_table(
        "members",
        sa.Column("member_number", sa.String(16), primary_key=True),
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("email", sa.String(160), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("date_of_birth", DATE, nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("home_region", sa.String(40), nullable=False),
        sa.Column("enrolled_on", DATE, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("merged_into", sa.String(16), nullable=True),
    )
    op.create_index("ix_members_email", "members", ["email"])
    op.create_index("ix_members_phone", "members", ["phone"])

    op.create_table(
        "stays",
        sa.Column("record_id", sa.String(32), primary_key=True),
        sa.Column("stay_id", sa.String(16), nullable=False),
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("property", sa.String(32), nullable=False),
        sa.Column("member_number", sa.String(16), nullable=True),
        sa.Column("member_on_booking", sa.Boolean, nullable=False),
        sa.Column("arrival_date", DATE, nullable=False),
        sa.Column("nights", sa.Integer, nullable=False),
        sa.Column("checkout_at_utc", TS, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("channel", sa.String(16), nullable=True),
        sa.Column("source_code", sa.String(32), nullable=False),
        sa.Column("rate_code", sa.String(32), nullable=False),
        sa.Column("partner_confirmation", sa.String(20), nullable=True),
        sa.Column("room_revenue_cents", sa.Integer, nullable=False),
        sa.Column("taxes_cents", sa.Integer, nullable=False),
        sa.Column("fees_cents", sa.Integer, nullable=False),
        sa.Column("guest_name", sa.String(160), nullable=False),
    )
    op.create_index("ix_stays_stay_id", "stays", ["stay_id"])
    op.create_index("ix_stays_member_number", "stays", ["member_number"])
    op.create_index("ix_stays_partner_confirmation", "stays", ["partner_confirmation"])

    op.create_table(
        "ledger_entries",
        sa.Column("entry_id", sa.String(32), primary_key=True),
        sa.Column("member_number", sa.String(16), nullable=False),
        sa.Column("stay_id", sa.String(16), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("points", sa.Integer, nullable=False),
        sa.Column("posted_at_utc", TS, nullable=False),
        sa.Column("reverses_entry_id", sa.String(32), nullable=True),
    )
    op.create_index("ix_ledger_entries_member_number", "ledger_entries", ["member_number"])
    op.create_index("ix_ledger_entries_stay_id", "ledger_entries", ["stay_id"])
    op.create_index("ix_ledger_entries_posted_at_utc", "ledger_entries", ["posted_at_utc"])

    op.create_table(
        "posting_queue",
        sa.Column("item_id", sa.String(32), primary_key=True),
        sa.Column("member_number", sa.String(16), nullable=False),
        sa.Column("stay_id", sa.String(16), nullable=False),
        sa.Column("points", sa.Integer, nullable=False),
        sa.Column("queued_at_utc", TS, nullable=False),
        sa.Column("expected_post_at_utc", TS, nullable=False),
        sa.Column("posts_entry_id", sa.String(32), nullable=False),
    )
    op.create_index("ix_posting_queue_stay_id", "posting_queue", ["stay_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("response_body", sa.Text, nullable=False),
        sa.Column("created_at_utc", TS, nullable=False),
    )

    op.create_table(
        "adjustments",
        sa.Column("adjustment_id", sa.String(32), primary_key=True),
        sa.Column("idempotency_key", sa.String(200), sa.ForeignKey("idempotency_records.key"), nullable=False),
        sa.Column("member_number", sa.String(16), nullable=False),
        sa.Column("stay_id", sa.String(16), nullable=False),
        sa.Column("points", sa.Integer, nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("requested_by", sa.String(80), nullable=False),
        sa.Column("created_at_utc", TS, nullable=False),
        sa.Column("ledger_entry_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_adjustments_idempotency_key", "adjustments", ["idempotency_key"], unique=True)
    op.create_index("ix_adjustments_member_number", "adjustments", ["member_number"])
    op.create_index("ix_adjustments_stay_id", "adjustments", ["stay_id"])

    op.create_table(
        "tickets",
        sa.Column("ticket_id", sa.String(32), primary_key=True),
        sa.Column("member_number", sa.String(16), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at_utc", TS, nullable=False),
    )


def downgrade() -> None:
    for table in (
        "tickets",
        "adjustments",
        "idempotency_records",
        "posting_queue",
        "ledger_entries",
        "stays",
        "members",
    ):
        op.drop_table(table)
