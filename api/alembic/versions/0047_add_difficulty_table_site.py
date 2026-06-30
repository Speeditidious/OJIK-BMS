"""Add representative site URL to difficulty tables."""

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("difficulty_tables", sa.Column("site", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("difficulty_tables", "site")
