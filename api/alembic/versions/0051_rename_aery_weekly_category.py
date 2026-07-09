"""Rename AERY weekly category key to 5aery."""

from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE weeklies
           SET category_key = '5aery'
         WHERE category_key = 'aery'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE weeklies
           SET category_key = 'aery'
         WHERE category_key = '5aery'
        """
    )
