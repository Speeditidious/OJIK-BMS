"""Add rating-derived rebuild state.

Revision ID: 0049
Revises: 0048
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_table_rating_update_keys",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("fumen_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("fumen_md5", sa.String(length=32), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["table_id"], ["difficulty_tables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "table_id", "effective_date", "fumen_sha256", "fumen_md5"),
    )
    op.create_index(
        "ix_user_table_rating_update_keys_user_date",
        "user_table_rating_update_keys",
        ["user_id", "effective_date"],
    )

    op.create_table(
        "user_rating_derived_state",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("last_rebuilt_effective_date", sa.Date(), nullable=True),
        sa.Column("rebuilt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["table_id"], ["difficulty_tables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "table_id"),
    )
    op.create_index(
        "ix_user_rating_derived_state_user_rebuilt_at",
        "user_rating_derived_state",
        ["user_id", "rebuilt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_rating_derived_state_user_rebuilt_at", table_name="user_rating_derived_state")
    op.drop_table("user_rating_derived_state")
    op.drop_index("ix_user_table_rating_update_keys_user_date", table_name="user_table_rating_update_keys")
    op.drop_table("user_table_rating_update_keys")
