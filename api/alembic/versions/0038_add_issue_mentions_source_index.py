"""Add source lookup index for issue user mentions.

Revision ID: 0038
Revises: 0037
Create Date: 2026-05-26
"""

from alembic import op


revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_issue_user_mentions_source",
        "issue_user_mentions",
        ["issue_id", "comment_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_issue_user_mentions_source", table_name="issue_user_mentions")
