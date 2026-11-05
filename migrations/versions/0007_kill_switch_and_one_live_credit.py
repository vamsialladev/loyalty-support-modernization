"""The kill switch, and one live credit per stay enforced by the database (ADR-0061; closes TD-13).

The index holds even if the code has a bug. If earlier data already has two live credits for one stay, this revision
stops and names them, because which one is right is a person's call.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

LIVE = "status IN ('executing', 'execution_unknown', 'executed', 'execution_conflict')"


def upgrade() -> None:
    op.create_table(
        "system_switches",
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("engaged", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(length=64), nullable=True),
        sa.Column("changed_at_utc", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("name"),
    )
    switches = sa.table("system_switches", sa.column("name", sa.String), sa.column("engaged", sa.Boolean))
    op.bulk_insert(switches, [{"name": "adjustments", "engaged": False}])

    query = f"SELECT stay_id FROM adjustment_requests WHERE {LIVE} GROUP BY stay_id HAVING count(*) > 1"  # noqa: S608
    duplicates = [row[0] for row in op.get_bind().execute(sa.text(query))]
    if duplicates:
        raise RuntimeError(f"these stays have more than one live credit; resolve them first: {duplicates}")
    op.create_index(
        "uq_adjustment_requests_live_stay",
        "adjustment_requests",
        ["stay_id"],
        unique=True,
        postgresql_where=sa.text(LIVE),
        sqlite_where=sa.text(LIVE),
    )


def downgrade() -> None:
    op.drop_index("uq_adjustment_requests_live_stay", table_name="adjustment_requests")
    op.drop_table("system_switches")
