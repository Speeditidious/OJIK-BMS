"""Add localized client update body fields.

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_update_announcements", sa.Column("body_markdown_en", sa.Text(), nullable=True))
    op.add_column("client_update_announcements", sa.Column("body_markdown_ja", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("client_update_announcements", "body_markdown_ja")
    op.drop_column("client_update_announcements", "body_markdown_en")
