"""Add symbol, slug, last_modified_header to difficulty_tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("difficulty_tables", sa.Column("symbol", sa.String(32), nullable=True))
    op.add_column("difficulty_tables", sa.Column("slug", sa.String(64), nullable=True))
    op.add_column(
        "difficulty_tables",
        sa.Column("last_modified_header", sa.String(128), nullable=True),
    )
    op.create_index(
        op.f("ix_difficulty_tables_slug"), "difficulty_tables", ["slug"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_difficulty_tables_slug"), table_name="difficulty_tables")
    op.drop_column("difficulty_tables", "last_modified_header")
    op.drop_column("difficulty_tables", "slug")
    op.drop_column("difficulty_tables", "symbol")
