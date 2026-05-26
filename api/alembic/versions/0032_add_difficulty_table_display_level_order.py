"""Add difficulty table display level order settings.

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "difficulty_tables",
        sa.Column("display_level_order", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "difficulty_tables",
        sa.Column("non_regular_level_order", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("difficulty_tables", "non_regular_level_order")
    op.drop_column("difficulty_tables", "display_level_order")
