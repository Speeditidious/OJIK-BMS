"""Add fumen key mode metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fumens", sa.Column("keymode", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("fumens", "keymode")
