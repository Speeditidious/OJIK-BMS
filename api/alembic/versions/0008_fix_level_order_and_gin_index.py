"""fix level_order int→str and add fumens table_entries GIN index

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-31
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert any integer elements in level_order JSONB arrays to strings
    op.execute(
        """
        UPDATE difficulty_tables
        SET level_order = (
            SELECT jsonb_agg(elem #>> '{}')
            FROM jsonb_array_elements(level_order) AS elem
        )
        WHERE level_order IS NOT NULL
          AND jsonb_typeof(level_order) = 'array'
          AND jsonb_typeof(level_order->0) = 'number'
        """
    )

    # Add GIN index on fumens.table_entries for fast containment queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_fumens_table_entries "
        "ON fumens USING gin (table_entries jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_fumens_table_entries")
    # Note: downgrade does not revert str→int conversion (data is compatible)
