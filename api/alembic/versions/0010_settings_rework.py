"""settings rework: add bio, remove is_public

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.String(500), nullable=True))
    op.drop_column("users", "is_public")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.drop_column("users", "bio")
