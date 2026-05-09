"""Add surrogate fumen_id to fumens.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fumens", sa.Column("fumen_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE fumens SET fumen_id = gen_random_uuid() WHERE fumen_id IS NULL")
    op.alter_column("fumens", "fumen_id", server_default=sa.text("gen_random_uuid()"))
    op.alter_column("fumens", "fumen_id", nullable=False)
    op.create_primary_key("fumens_pkey", "fumens", ["fumen_id"])

    bind = op.get_bind()
    null_count = bind.execute(sa.text("SELECT COUNT(*) FROM fumens WHERE fumen_id IS NULL")).scalar()
    if null_count:
        raise RuntimeError(f"fumens.fumen_id backfill left {null_count} NULL rows")
    duplicate_count = bind.execute(sa.text("""
        SELECT COUNT(*)
        FROM (
            SELECT fumen_id
            FROM fumens
            GROUP BY fumen_id
            HAVING COUNT(*) > 1
        ) duplicated
    """)).scalar()
    if duplicate_count:
        raise RuntimeError(f"fumens.fumen_id backfill created {duplicate_count} duplicate ids")


def downgrade() -> None:
    op.drop_constraint("fumens_pkey", "fumens", type_="primary")
    op.drop_column("fumens", "fumen_id")
