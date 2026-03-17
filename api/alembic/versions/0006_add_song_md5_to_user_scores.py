"""Add song_md5 to user_scores; make song_sha256 nullable; replace unique constraint

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-13

Changes:
- user_scores.song_md5 VARCHAR(32) NULLABLE (new column, for LR2 MD5-based records)
- user_scores.song_sha256 changed to NULLABLE (LR2 may only have MD5)
- Drop old unique constraint uq_user_scores (song_sha256 NOT NULL assumption)
- Create functional unique index on (user_id, COALESCE(song_sha256, song_md5), client_type)
- score_history.song_sha256 changed to NULLABLE
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- user_scores ---
    # Add song_md5 column
    op.add_column(
        "user_scores",
        sa.Column("song_md5", sa.String(32), nullable=True),
    )
    op.create_index("ix_user_scores_song_md5", "user_scores", ["song_md5"])

    # Make song_sha256 nullable
    op.alter_column("user_scores", "song_sha256", nullable=True)

    # Drop the old NOT-NULL-based unique constraint
    op.drop_constraint("uq_user_scores", "user_scores", type_="unique")

    # Create functional unique index using COALESCE
    op.execute(
        """
        CREATE UNIQUE INDEX uq_user_scores_coalesce
        ON user_scores (user_id, COALESCE(song_sha256, song_md5), client_type)
        """
    )

    # --- score_history ---
    # Make song_sha256 nullable (LR2 history rows may not have it)
    op.alter_column("score_history", "song_sha256", nullable=True)


def downgrade() -> None:
    # --- score_history ---
    # Restore NOT NULL (will fail if any nulls exist)
    op.alter_column("score_history", "song_sha256", nullable=False)

    # --- user_scores ---
    op.execute("DROP INDEX IF EXISTS uq_user_scores_coalesce")

    op.create_unique_constraint(
        "uq_user_scores",
        "user_scores",
        ["user_id", "song_sha256", "client_type"],
    )

    op.alter_column("user_scores", "song_sha256", nullable=False)

    op.drop_index("ix_user_scores_song_md5", "user_scores")
    op.drop_column("user_scores", "song_md5")
