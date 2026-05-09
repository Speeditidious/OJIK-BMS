"""Remove persisted NO PLAY score rows.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-09
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM user_scores WHERE clear_type = 0")
    op.execute("DELETE FROM user_rankings")
    op.execute("DELETE FROM user_table_rating_checkpoints")
    op.execute("DELETE FROM user_table_rating_update_daily")
    op.execute("DELETE FROM user_rating_update_daily")


def downgrade() -> None:
    pass
