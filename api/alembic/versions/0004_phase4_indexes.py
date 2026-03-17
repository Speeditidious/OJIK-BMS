"""Phase 4 indexes and score_history.recorded_at column

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add server-side timestamp to score_history for heatmap/calendar queries.
    # played_at reflects the in-game achievement time and is often null for LR2;
    # recorded_at always has a value (set when the row is inserted on the server).
    op.add_column(
        "score_history",
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )

    # Composite index for heatmap/calendar aggregation queries:
    # SELECT DATE(recorded_at), COUNT(*) ... WHERE user_id=? GROUP BY DATE(recorded_at)
    op.create_index(
        "ix_score_history_user_id_recorded_at",
        "score_history",
        ["user_id", "recorded_at"],
    )

    # Composite index for time-series analysis on user_scores
    op.create_index(
        "ix_user_scores_user_id_played_at",
        "user_scores",
        ["user_id", "played_at"],
    )

    # Index for NO SONG detection in Phase 5
    op.create_index(
        "ix_user_owned_songs_user_id_md5",
        "user_owned_songs",
        ["user_id", "song_md5"],
    )

    # Index for schedule calendar queries
    op.create_index(
        "ix_schedules_user_id_scheduled_date",
        "schedules",
        ["user_id", "scheduled_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_schedules_user_id_scheduled_date", table_name="schedules")
    op.drop_index("ix_user_owned_songs_user_id_md5", table_name="user_owned_songs")
    op.drop_index("ix_user_scores_user_id_played_at", table_name="user_scores")
    op.drop_index("ix_score_history_user_id_recorded_at", table_name="score_history")
    op.drop_column("score_history", "recorded_at")
