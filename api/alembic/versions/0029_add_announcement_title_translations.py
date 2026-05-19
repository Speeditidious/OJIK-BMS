"""Add title_en and title_ja to announcements.

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("announcements", sa.Column("title_en", sa.String(200), nullable=True))
    op.add_column("announcements", sa.Column("title_ja", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("announcements", "title_ja")
    op.drop_column("announcements", "title_en")
