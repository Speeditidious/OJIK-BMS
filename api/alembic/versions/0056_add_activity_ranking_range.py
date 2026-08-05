"""Add weekly/monthly range support to user_activity_ranking.

Revision ID: 0056
Revises: 0055
Create Date: 2026-08-05
"""
import sqlalchemy as sa

from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def _pk_name(table_name: str) -> str:
    bind = op.get_bind()
    return sa.inspect(bind).get_pk_constraint(table_name).get("name") or f"{table_name}_pkey"


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in sa.inspect(bind).get_columns("user_activity_ranking")}
    if "range" not in columns:
        op.add_column(
            "user_activity_ranking",
            sa.Column("range", sa.String(length=16), nullable=False, server_default="monthly"),
        )

    op.execute("DROP INDEX IF EXISTS ix_user_activity_ranking_metric_rank")
    op.drop_constraint(_pk_name("user_activity_ranking"), "user_activity_ranking", type_="primary")
    op.create_primary_key(
        "user_activity_ranking_pkey",
        "user_activity_ranking",
        ["range", "metric", "user_id"],
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_activity_ranking_range_metric_rank
        ON user_activity_ranking ("range", metric, rank)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM user_activity_ranking WHERE range <> 'monthly'")
    op.execute("DROP INDEX IF EXISTS ix_user_activity_ranking_range_metric_rank")
    op.drop_constraint(_pk_name("user_activity_ranking"), "user_activity_ranking", type_="primary")
    op.create_primary_key(
        "user_activity_ranking_pkey",
        "user_activity_ranking",
        ["metric", "user_id"],
    )
    op.create_index(
        "ix_user_activity_ranking_metric_rank",
        "user_activity_ranking",
        ["metric", "rank"],
    )
    op.drop_column("user_activity_ranking", "range")
