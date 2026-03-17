"""Add subtitle to songs and score_rate to score_history.

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # songs: subtitle field for difficulty sub-chart label
    op.add_column(
        "songs",
        sa.Column("subtitle", sa.String(256), nullable=True),
    )

    # score_history: explicit score_rate column for Rank display
    # (ScoreHistory.score already holds this value; score_rate is an alias
    #  added for clarity in the recent-updates API response)
    op.add_column(
        "score_history",
        sa.Column("score_rate", sa.Float(), nullable=True),
    )
    # Backfill score_rate from existing score column
    op.execute("UPDATE score_history SET score_rate = score WHERE score_rate IS NULL")


def downgrade() -> None:
    op.drop_column("score_history", "score_rate")
    op.drop_column("songs", "subtitle")
