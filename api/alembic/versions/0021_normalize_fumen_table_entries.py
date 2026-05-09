"""Normalize fumen table entries out of fumens.table_entries.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fumen_table_entries",
        sa.Column("fumen_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fumen_id"], ["fumens.fumen_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["table_id"], ["difficulty_tables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("fumen_id", "table_id"),
    )
    op.create_index(
        "ix_fumen_table_entries_table_id_level",
        "fumen_table_entries",
        ["table_id", "level", "fumen_id"],
    )

    op.execute("""
        INSERT INTO fumen_table_entries (fumen_id, table_id, level)
        SELECT
            f.fumen_id,
            (entry->>'table_id')::uuid,
            COALESCE(entry->>'level', '')
        FROM fumens f
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(f.table_entries, '[]'::jsonb)) AS entry
        WHERE entry->>'table_id' IS NOT NULL
        ON CONFLICT (fumen_id, table_id) DO NOTHING
    """)

    missing = op.get_bind().execute(sa.text("""
        SELECT COUNT(*)
        FROM fumens f
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(f.table_entries, '[]'::jsonb)) AS entry
        WHERE entry->>'table_id' IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM fumen_table_entries fte
              WHERE fte.fumen_id = f.fumen_id
                AND fte.table_id = (entry->>'table_id')::uuid
          )
    """)).scalar()
    if missing:
        raise RuntimeError(f"fumen_table_entries backfill missed {missing} entries")

    op.drop_index("ix_fumens_table_entries", table_name="fumens", if_exists=True)
    op.drop_column("fumens", "table_entries")


def downgrade() -> None:
    op.add_column("fumens", sa.Column("table_entries", postgresql.JSONB(), nullable=True))
    op.execute("""
        UPDATE fumens f
        SET table_entries = sub.entries
        FROM (
            SELECT
                fumen_id,
                jsonb_agg(
                    jsonb_build_object('table_id', table_id::text, 'level', level)
                    ORDER BY table_id::text
                ) AS entries
            FROM fumen_table_entries
            GROUP BY fumen_id
        ) sub
        WHERE f.fumen_id = sub.fumen_id
    """)
    op.drop_index("ix_fumen_table_entries_table_id_level", table_name="fumen_table_entries")
    op.drop_table("fumen_table_entries")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_fumens_table_entries "
        "ON fumens USING gin (table_entries jsonb_path_ops)"
    )
