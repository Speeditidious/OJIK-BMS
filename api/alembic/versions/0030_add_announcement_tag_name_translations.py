"""Add name_en and name_ja to announcement_tags.

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("announcement_tags", sa.Column("name_en", sa.String(64), nullable=True))
    op.add_column("announcement_tags", sa.Column("name_ja", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("announcement_tags", "name_ja")
    op.drop_column("announcement_tags", "name_en")
