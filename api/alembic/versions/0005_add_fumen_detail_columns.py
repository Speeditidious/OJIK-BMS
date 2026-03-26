"""add fumen detail columns, rename total_notes to notes_total, drop bpm

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old single bpm column (not written by any code path)
    op.drop_column("fumens", "bpm")

    # Rename total_notes → notes_total for consistency with other notes_* columns
    op.alter_column("fumens", "total_notes", new_column_name="notes_total")

    # Add new detail columns
    op.add_column("fumens", sa.Column("bpm_min", sa.Float(), nullable=True))
    op.add_column("fumens", sa.Column("bpm_max", sa.Float(), nullable=True))
    op.add_column("fumens", sa.Column("bpm_main", sa.Float(), nullable=True))
    op.add_column("fumens", sa.Column("notes_n", sa.Integer(), nullable=True))
    op.add_column("fumens", sa.Column("notes_ln", sa.Integer(), nullable=True))
    op.add_column("fumens", sa.Column("notes_s", sa.Integer(), nullable=True))
    op.add_column("fumens", sa.Column("notes_ls", sa.Integer(), nullable=True))
    op.add_column("fumens", sa.Column("length", sa.Integer(), nullable=True))
    op.add_column(
        "fumens",
        sa.Column(
            "added_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("fumens", "added_by_user_id")
    op.drop_column("fumens", "length")
    op.drop_column("fumens", "notes_ls")
    op.drop_column("fumens", "notes_s")
    op.drop_column("fumens", "notes_ln")
    op.drop_column("fumens", "notes_n")
    op.drop_column("fumens", "bpm_main")
    op.drop_column("fumens", "bpm_max")
    op.drop_column("fumens", "bpm_min")
    # Rename notes_total back to total_notes
    op.alter_column("fumens", "notes_total", new_column_name="total_notes")
    # Re-add the old bpm column
    op.add_column("fumens", sa.Column("bpm", sa.Float(), nullable=True))
