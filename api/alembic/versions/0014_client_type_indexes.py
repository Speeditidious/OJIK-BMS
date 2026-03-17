"""Add composite indexes on (user_id, client_type) for user_scores and score_history.

grade-distribution, summary, and filter endpoints all do WHERE user_id=? AND client_type=?
but no covering composite index existed. These indexes avoid full user_id scans when
client_type is part of the filter.

Revision ID: 0014
Revises: 0013
"""

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.create_index(
        "ix_user_scores_user_id_client_type",
        "user_scores",
        ["user_id", "client_type"],
    )
    op.create_index(
        "ix_score_history_user_id_client_type",
        "score_history",
        ["user_id", "client_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_score_history_user_id_client_type", table_name="score_history")
    op.drop_index("ix_user_scores_user_id_client_type", table_name="user_scores")
