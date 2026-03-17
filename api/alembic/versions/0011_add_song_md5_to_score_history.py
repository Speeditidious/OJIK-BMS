"""Add song_md5 column to score_history for LR2 md5-only scores.

Revision ID: 0011
Revises: 0010
"""
import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "score_history",
        sa.Column("song_md5", sa.String(32), nullable=True),
    )
    op.create_index("ix_score_history_song_md5", "score_history", ["song_md5"])


def downgrade() -> None:
    op.drop_index("ix_score_history_song_md5", table_name="score_history")
    op.drop_column("score_history", "song_md5")
