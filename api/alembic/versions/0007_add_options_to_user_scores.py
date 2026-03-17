"""Add options JSONB column to user_scores

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-13

Changes:
- user_scores.options JSONB NULLABLE (new column, stores play arrangement/seed data)
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_scores",
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_scores", "options")
