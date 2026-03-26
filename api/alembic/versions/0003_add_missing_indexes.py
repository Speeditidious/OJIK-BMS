"""add missing indexes: ix_courses_source_table_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This index exists in the model but was missing from the DB
    op.create_index("ix_courses_source_table_id", "courses", ["source_table_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_courses_source_table_id", table_name="courses")
