"""Add subartist column to songs table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("songs", sa.Column("subartist", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("songs", "subartist")
