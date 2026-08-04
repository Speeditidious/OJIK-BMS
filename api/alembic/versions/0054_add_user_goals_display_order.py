"""Add user_goals.display_order for owner-defined goal ordering.

Revision ID: 0054
Revises: 0053
Create Date: 2026-08-04
"""
import sqlalchemy as sa

from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_goals", sa.Column("display_order", sa.Integer(), nullable=True))
    # Backfill with the order users currently see (created_at DESC) so the
    # column's introduction is invisible to them.
    op.execute(
        """
        UPDATE user_goals AS g
        SET display_order = numbered.rn - 1
        FROM (
            SELECT goal_id,
                   row_number() OVER (
                       PARTITION BY user_id ORDER BY created_at DESC
                   ) AS rn
            FROM user_goals
            WHERE deleted_at IS NULL
        ) AS numbered
        WHERE g.goal_id = numbered.goal_id
        """
    )


def downgrade() -> None:
    op.drop_column("user_goals", "display_order")
