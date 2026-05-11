"""Widen fumen title and artist metadata columns.

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "fumens",
        "title",
        existing_type=sa.String(length=512),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "fumens",
        "artist",
        existing_type=sa.String(length=256),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "fumens",
        "artist",
        existing_type=sa.Text(),
        type_=sa.String(length=256),
        existing_nullable=True,
    )
    op.alter_column(
        "fumens",
        "title",
        existing_type=sa.Text(),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
