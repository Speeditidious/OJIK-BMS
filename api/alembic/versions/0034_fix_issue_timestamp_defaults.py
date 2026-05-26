"""Fix issue table timestamp defaults.

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-25
"""

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


_ISSUE_TABLES = (
    "issue_tags",
    "issues",
    "issue_comments",
    "issue_user_mentions",
    "issue_issue_references",
)


def upgrade() -> None:
    for table_name in _ISSUE_TABLES:
        for column_name in ("created_at", "updated_at"):
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=False),
                type_=sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                existing_nullable=False,
                postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
            )


def downgrade() -> None:
    for table_name in _ISSUE_TABLES:
        for column_name in ("created_at", "updated_at"):
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                type_=sa.DateTime(timezone=False),
                server_default=None,
                existing_nullable=False,
                postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
            )
