"""Add nullable fumen_id to user_scores.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_scores", sa.Column("fumen_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.execute("""
        UPDATE user_scores us
        SET fumen_id = f.fumen_id
        FROM fumens f
        WHERE us.fumen_id IS NULL
          AND us.fumen_hash_others IS NULL
          AND us.fumen_sha256 IS NOT NULL
          AND f.sha256 = us.fumen_sha256
    """)
    op.execute("""
        UPDATE user_scores us
        SET fumen_id = f.fumen_id
        FROM fumens f
        WHERE us.fumen_id IS NULL
          AND us.fumen_hash_others IS NULL
          AND us.fumen_sha256 IS NULL
          AND us.fumen_md5 IS NOT NULL
          AND f.md5 = us.fumen_md5
    """)

    missing_registered = op.get_bind().execute(sa.text("""
        SELECT COUNT(*)
        FROM user_scores us
        WHERE us.fumen_id IS NULL
          AND us.fumen_hash_others IS NULL
          AND (
              (us.fumen_sha256 IS NOT NULL AND EXISTS (
                  SELECT 1 FROM fumens f WHERE f.sha256 = us.fumen_sha256
              ))
              OR (
                  us.fumen_sha256 IS NULL
                  AND us.fumen_md5 IS NOT NULL
                  AND EXISTS (SELECT 1 FROM fumens f WHERE f.md5 = us.fumen_md5)
              )
          )
    """)).scalar()
    if missing_registered:
        raise RuntimeError(f"user_scores.fumen_id backfill missed {missing_registered} registered scores")

    op.create_foreign_key(
        "user_scores_fumen_id_fkey",
        "user_scores",
        "fumens",
        ["fumen_id"],
        ["fumen_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_user_scores_user_fumen_id",
        "user_scores",
        ["user_id", "fumen_id"],
        postgresql_where=sa.text("fumen_id IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_fumen_user_id",
        "user_scores",
        ["fumen_id", "user_id"],
        postgresql_where=sa.text("fumen_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_user_scores_fumen_user_id", table_name="user_scores")
    op.drop_index("ix_user_scores_user_fumen_id", table_name="user_scores")
    op.drop_constraint("user_scores_fumen_id_fkey", "user_scores", type_="foreignkey")
    op.drop_column("user_scores", "fumen_id")
