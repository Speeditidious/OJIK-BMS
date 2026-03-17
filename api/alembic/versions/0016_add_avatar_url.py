"""Add avatar_url to users and discord_avatar_url to oauth_accounts.

Revision ID: 0016
Revises: 0015
"""

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(512), nullable=True))
    op.add_column(
        "oauth_accounts",
        sa.Column("discord_avatar_url", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_column("oauth_accounts", "discord_avatar_url")
