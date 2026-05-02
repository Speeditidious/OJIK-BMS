"""Demote UE tables from default difficulty tables.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-02
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(
        """
        UPDATE difficulty_tables
           SET is_default = false,
               default_order = NULL,
               updated_at = now()
         WHERE slug IN ('4ue', '6ue', '8ue')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE difficulty_tables
           SET is_default = true,
               default_order = CASE slug
                   WHEN '4ue' THEN 14
                   WHEN '6ue' THEN 15
                   WHEN '8ue' THEN 16
               END,
               updated_at = now()
         WHERE slug IN ('4ue', '6ue', '8ue')
        """
    )
