"""Add partial unique index on score_history for md5-only rows (no sha256).

Without this, LR2 scores that only have song_md5 (no sha256) bypass the
existing uq_score_history_user_song_client_date constraint because
NULL != NULL in PostgreSQL. Each sync re-inserts a new row instead of
updating the existing one.

Revision ID: 0013
Revises: 0012
"""

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX uq_score_history_md5_no_sha256
        ON score_history (user_id, song_md5, client_type, sync_date)
        WHERE song_sha256 IS NULL AND song_md5 IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_score_history_md5_no_sha256")
