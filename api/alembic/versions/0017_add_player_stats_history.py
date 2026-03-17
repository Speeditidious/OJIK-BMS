"""Add user_player_stats_history table and play_count columns to score_history.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_player_stats_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_type", sa.String(32), nullable=False),
        sa.Column("sync_date", sa.Date, nullable=False),
        sa.Column("total_notes_hit", sa.BigInteger, nullable=False),
        sa.Column("total_play_count", sa.Integer, nullable=True),
        sa.UniqueConstraint("user_id", "client_type", "sync_date", name="uq_player_stats_history"),
    )
    op.create_index(
        "ix_player_stats_history_user_date",
        "user_player_stats_history",
        ["user_id", "sync_date"],
    )

    op.add_column("score_history", sa.Column("play_count", sa.Integer, nullable=True))
    op.add_column("score_history", sa.Column("old_play_count", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("score_history", "old_play_count")
    op.drop_column("score_history", "play_count")
    op.drop_index("ix_player_stats_history_user_date", table_name="user_player_stats_history")
    op.drop_table("user_player_stats_history")
