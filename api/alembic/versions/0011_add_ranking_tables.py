"""Add user_rankings and user_ranking_history tables.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID  # noqa: F401

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_rankings",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", UUID(as_uuid=True), sa.ForeignKey("difficulty_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exp", sa.Double(), nullable=False, server_default="0"),
        sa.Column("exp_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Double(), nullable=False, server_default="0"),
        sa.Column("rating_top_n", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("rating_contributions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("exp_top_contributions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("dan_title", sa.String(64), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("user_id", "table_id"),
    )
    op.execute("CREATE INDEX ix_ur_exp ON user_rankings (table_id, exp DESC)")
    op.execute("CREATE INDEX ix_ur_rating ON user_rankings (table_id, rating DESC)")

    op.create_table(
        "user_ranking_history",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", UUID(as_uuid=True), sa.ForeignKey("difficulty_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("exp", sa.Double(), nullable=False, server_default="0"),
        sa.Column("exp_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Double(), nullable=False, server_default="0"),
        sa.Column("exp_delta", sa.Double(), nullable=False, server_default="0"),
        sa.Column("rating_delta", sa.Double(), nullable=False, server_default="0"),
        sa.Column("change_contributions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.PrimaryKeyConstraint("user_id", "table_id", "date"),
    )
    op.execute("CREATE INDEX ix_urh_user_table_date ON user_ranking_history (user_id, table_id, date DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_urh_user_table_date")
    op.drop_table("user_ranking_history")
    op.execute("DROP INDEX IF EXISTS ix_ur_rating")
    op.execute("DROP INDEX IF EXISTS ix_ur_exp")
    op.drop_table("user_rankings")
