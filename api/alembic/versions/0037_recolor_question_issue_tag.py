"""Recolor the 'question' issue tag to purple for better contrast.

The 'secondary' design token is too muted on the dark surface, making the badge
hard to read. Switch to a Tailwind purple-500 hex (matches the Completed status
badge), routed through resolveTagBadgeStyle's hex branch.

Revision ID: 0037
Revises: 0036
Create Date: 2026-05-26
"""

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute(
        "UPDATE issue_tags SET color = '#a855f7' WHERE slug = 'question' AND color = 'secondary'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE issue_tags SET color = 'secondary' WHERE slug = 'question' AND color = '#a855f7'"
    )
