"""Add Discord avatar hash to OAuth accounts.

Revision ID: 0039
Revises: 0038
Create Date: 2026-05-27
"""

import sqlalchemy as sa
from alembic import op


revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "oauth_accounts",
        sa.Column("discord_avatar_hash", sa.String(128), nullable=True),
    )
    op.execute(
        """
        UPDATE oauth_accounts
        SET discord_avatar_hash = substring(discord_avatar_url from '/avatars/[^/]+/([^./?]+)')
        WHERE provider = 'discord'
          AND discord_avatar_url IS NOT NULL
          AND discord_avatar_hash IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("oauth_accounts", "discord_avatar_hash")
