"""Add title column to user_day_notes."""

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_day_notes",
        sa.Column("title", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_day_notes", "title")
