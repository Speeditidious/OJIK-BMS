"""Add clear_count/hit_notes to user_scores and sync_date/clear_count to score_history.

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_scores: cumulative clear count and total hit notes
    op.add_column(
        "user_scores",
        sa.Column("clear_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_scores",
        sa.Column("hit_notes", sa.BigInteger(), nullable=False, server_default="0"),
    )

    # score_history: date-keyed upsert columns
    op.add_column(
        "score_history",
        sa.Column("sync_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "score_history",
        sa.Column("old_clear_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "score_history",
        sa.Column("clear_count", sa.Integer(), nullable=True),
    )

    # Backfill sync_date from recorded_at before making it NOT NULL
    op.execute(
        "UPDATE score_history SET sync_date = recorded_at::date WHERE sync_date IS NULL"
    )
    op.alter_column("score_history", "sync_date", nullable=False)

    # Remove duplicate rows (keep the earliest per (user_id, song_sha256, client_type, date))
    # before adding the unique constraint.
    op.execute(
        """
        DELETE FROM score_history a
        USING score_history b
        WHERE a.id > b.id
          AND a.user_id = b.user_id
          AND a.song_sha256 IS NOT DISTINCT FROM b.song_sha256
          AND a.client_type = b.client_type
          AND a.sync_date = b.sync_date
        """
    )

    # Unique constraint enabling ON CONFLICT upsert by date
    op.create_unique_constraint(
        "uq_score_history_user_song_client_date",
        "score_history",
        ["user_id", "song_sha256", "client_type", "sync_date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_score_history_user_song_client_date", "score_history", type_="unique"
    )
    op.drop_column("score_history", "clear_count")
    op.drop_column("score_history", "old_clear_count")
    op.drop_column("score_history", "sync_date")
    op.drop_column("user_scores", "hit_notes")
    op.drop_column("user_scores", "clear_count")
