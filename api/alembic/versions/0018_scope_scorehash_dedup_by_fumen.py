"""Scope scorehash deduplication by fumen identity.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_user_scores_scorehash", table_name="user_scores")
    op.create_index(
        "uq_user_scores_scorehash",
        "user_scores",
        [
            "scorehash",
            "user_id",
            "client_type",
            sa.text("COALESCE(fumen_sha256, '')"),
            sa.text("COALESCE(fumen_md5, '')"),
            sa.text("COALESCE(fumen_hash_others, '')"),
        ],
        unique=True,
        postgresql_where=sa.text("scorehash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_scores_scorehash", table_name="user_scores")
    op.create_index(
        "uq_user_scores_scorehash",
        "user_scores",
        ["scorehash", "user_id", "client_type"],
        unique=True,
        postgresql_where=sa.text("scorehash IS NOT NULL"),
    )
