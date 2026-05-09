"""Move user fumen tags to fumen_id references.

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_fumen_tags", sa.Column("fumen_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.execute("""
        UPDATE user_fumen_tags t
        SET fumen_id = f.fumen_id
        FROM fumens f
        WHERE (
            t.fumen_sha256 IS NOT NULL
            AND f.sha256 = t.fumen_sha256
        ) OR (
            t.fumen_sha256 IS NULL
            AND t.fumen_md5 IS NOT NULL
            AND f.md5 = t.fumen_md5
        )
    """)

    missing = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM user_fumen_tags WHERE fumen_id IS NULL")
    ).scalar()
    if missing:
        raise RuntimeError(f"user_fumen_tags has {missing} rows that do not match fumens")

    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, fumen_id, tag
                    ORDER BY display_order ASC, id ASC
                ) AS rn
            FROM user_fumen_tags
        )
        DELETE FROM user_fumen_tags t
        USING ranked r
        WHERE t.id = r.id
          AND r.rn > 1
    """)

    op.alter_column("user_fumen_tags", "fumen_id", nullable=False)
    op.create_foreign_key(
        "user_fumen_tags_fumen_id_fkey",
        "user_fumen_tags",
        "fumens",
        ["fumen_id"],
        ["fumen_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_user_fumen_tags_fumen_id", "user_fumen_tags", ["fumen_id"])
    op.create_index(
        "uq_user_fumen_tags_fumen",
        "user_fumen_tags",
        ["user_id", "fumen_id", "tag"],
        unique=True,
    )

    op.drop_index("uq_user_fumen_tags_sha256", table_name="user_fumen_tags", if_exists=True)
    op.drop_index("uq_user_fumen_tags_md5", table_name="user_fumen_tags", if_exists=True)
    op.drop_index("ix_user_fumen_tags_fumen_sha256", table_name="user_fumen_tags", if_exists=True)
    op.drop_index("ix_user_fumen_tags_fumen_md5", table_name="user_fumen_tags", if_exists=True)
    op.drop_column("user_fumen_tags", "fumen_sha256")
    op.drop_column("user_fumen_tags", "fumen_md5")


def downgrade() -> None:
    op.add_column("user_fumen_tags", sa.Column("fumen_md5", sa.String(length=32), nullable=True))
    op.add_column("user_fumen_tags", sa.Column("fumen_sha256", sa.String(length=64), nullable=True))
    op.execute("""
        UPDATE user_fumen_tags t
        SET fumen_sha256 = f.sha256,
            fumen_md5 = f.md5
        FROM fumens f
        WHERE t.fumen_id = f.fumen_id
    """)

    op.drop_index("uq_user_fumen_tags_fumen", table_name="user_fumen_tags")
    op.drop_index("ix_user_fumen_tags_fumen_id", table_name="user_fumen_tags")
    op.drop_constraint("user_fumen_tags_fumen_id_fkey", "user_fumen_tags", type_="foreignkey")
    op.drop_column("user_fumen_tags", "fumen_id")

    op.create_index("ix_user_fumen_tags_fumen_sha256", "user_fumen_tags", ["fumen_sha256"])
    op.create_index("ix_user_fumen_tags_fumen_md5", "user_fumen_tags", ["fumen_md5"])
    op.create_index(
        "uq_user_fumen_tags_sha256",
        "user_fumen_tags",
        ["user_id", "fumen_sha256", "tag"],
        unique=True,
        postgresql_where=sa.text("fumen_sha256 IS NOT NULL"),
    )
    op.create_index(
        "uq_user_fumen_tags_md5",
        "user_fumen_tags",
        ["user_id", "fumen_md5", "tag"],
        unique=True,
        postgresql_where=sa.text("fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"),
    )
