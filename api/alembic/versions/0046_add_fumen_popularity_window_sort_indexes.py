"""Add fumen popularity window sort indexes."""

from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_fumen_popularity_window_players
        ON fumen_popularity_window ("window", played_user_count DESC, play_count DESC, fumen_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fumen_popularity_window_plays
        ON fumen_popularity_window ("window", play_count DESC, played_user_count DESC, fumen_id)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_fumen_popularity_window_plays", table_name="fumen_popularity_window")
    op.drop_index("ix_fumen_popularity_window_players", table_name="fumen_popularity_window")
