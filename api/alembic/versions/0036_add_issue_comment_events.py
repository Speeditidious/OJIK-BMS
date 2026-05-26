"""Add system event columns to issue_comments; drop unused updated_at sort index.

Revision ID: 0036
Revises: 0035
Create Date: 2026-05-26
"""

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


def upgrade() -> None:
    # The 'updated' sort option was dropped from the UI, so this composite index is
    # no longer reachable. Drop it to keep the schema lean.
    op.drop_index("ix_issues_status_updated_at", table_name="issues")

    # System events (e.g. status changes) live alongside user comments. event_type is
    # NULL for regular user comments; non-NULL rows carry payload metadata and may
    # have a NULL body.
    op.add_column("issue_comments", sa.Column("event_type", sa.String(length=32), nullable=True))
    op.add_column("issue_comments", sa.Column("event_payload", JSONB(), nullable=True))
    op.alter_column("issue_comments", "body", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("issue_comments", "body", existing_type=sa.Text(), nullable=False)
    op.drop_column("issue_comments", "event_payload")
    op.drop_column("issue_comments", "event_type")

    op.create_index(
        "ix_issues_status_updated_at",
        "issues",
        ["status", "updated_at", "id"],
    )
