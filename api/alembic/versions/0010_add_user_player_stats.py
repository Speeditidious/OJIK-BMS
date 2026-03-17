"""Add user_player_stats table for cumulative player totals.

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_player_stats",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("client_type", sa.String(32), nullable=False),
        sa.Column("total_notes_hit", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_play_count", sa.Integer(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "client_type"),
    )


def downgrade() -> None:
    op.drop_table("user_player_stats")
