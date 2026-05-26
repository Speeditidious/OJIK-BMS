"""Add 'work_in_progress' issue status and sort indexes.

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-26
"""

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # Replace status CHECK constraint to include work_in_progress.
    op.drop_constraint("ck_issues_status", "issues", type_="check")
    op.create_check_constraint(
        "ck_issues_status",
        "issues",
        "status IN ('open', 'work_in_progress', 'completed', 'not_planned')",
    )

    # Sort indexes for the new sort options on the list endpoint.
    # Each composite is shaped to match `WHERE status = ? ORDER BY <ts> DESC, id DESC`.
    op.create_index(
        "ix_issues_status_created_at",
        "issues",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "ix_issues_status_updated_at",
        "issues",
        ["status", "updated_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_issues_status_updated_at", table_name="issues")
    op.drop_index("ix_issues_status_created_at", table_name="issues")

    # Coerce existing work_in_progress rows back to open before reapplying the old constraint.
    op.execute("UPDATE issues SET status = 'open' WHERE status = 'work_in_progress'")

    op.drop_constraint("ck_issues_status", "issues", type_="check")
    op.create_check_constraint(
        "ck_issues_status",
        "issues",
        "status IN ('open', 'completed', 'not_planned')",
    )
