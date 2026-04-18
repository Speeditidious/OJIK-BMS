"""Optimize ranking tables schema.

Remove redundant/computable columns from user_rankings and user_ranking_history.
Rename change_contributions → rating_contributions (full Top-N snapshot).

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_rankings: rating_top_n 제거 (config.toml에서 항상 얻을 수 있음)
    op.drop_column("user_rankings", "rating_top_n")

    # user_ranking_history: 계산 가능한 컬럼 3개 제거
    op.drop_column("user_ranking_history", "exp_level")
    op.drop_column("user_ranking_history", "exp_delta")
    op.drop_column("user_ranking_history", "rating_delta")

    # change_contributions → rating_contributions (상위 10개 → 전체 Top-N 스냅샷)
    op.alter_column(
        "user_ranking_history",
        "change_contributions",
        new_column_name="rating_contributions",
    )


def downgrade() -> None:
    op.alter_column(
        "user_ranking_history",
        "rating_contributions",
        new_column_name="change_contributions",
    )
    op.add_column(
        "user_ranking_history",
        sa.Column("rating_delta", sa.Double(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_ranking_history",
        sa.Column("exp_delta", sa.Double(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_ranking_history",
        sa.Column("exp_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_rankings",
        sa.Column("rating_top_n", sa.Integer(), nullable=False, server_default="50"),
    )
