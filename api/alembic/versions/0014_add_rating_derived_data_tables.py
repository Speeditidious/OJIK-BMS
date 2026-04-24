"""Add derived tables for rating checkpoints and daily update counts.

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_table_rating_checkpoints",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("difficulty_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("exp", sa.Double(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Double(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("user_id", "table_id", "effective_date"),
    )

    op.create_table(
        "user_table_rating_update_daily",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("difficulty_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("update_count", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "table_id", "effective_date"),
    )
    op.create_index(
        "ix_user_table_rating_update_daily_user_date",
        "user_table_rating_update_daily",
        ["user_id", "effective_date"],
    )

    op.create_table(
        "user_rating_update_daily",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("update_count", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "effective_date"),
    )


def downgrade() -> None:
    op.drop_table("user_rating_update_daily")
    op.drop_index(
        "ix_user_table_rating_update_daily_user_date",
        table_name="user_table_rating_update_daily",
    )
    op.drop_table("user_table_rating_update_daily")
    op.drop_table("user_table_rating_checkpoints")
