"""App baseline: an empty schema under Alembic's control. Business tables start in revision 0002 (Milestone 5).

Revision ID: 0001
Revises:
Create Date: 2026-10-29
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
