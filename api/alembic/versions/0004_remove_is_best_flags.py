"""remove is_best_* columns and partial indexes from user_scores

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop partial indexes before dropping the columns they reference
    op.drop_index("ix_user_scores_best_ct_sha256", table_name="user_scores")
    op.drop_index("ix_user_scores_best_ex_sha256", table_name="user_scores")
    op.drop_index("ix_user_scores_best_bp_sha256", table_name="user_scores")
    op.drop_index("ix_user_scores_best_ct_md5", table_name="user_scores")
    op.drop_index("ix_user_scores_best_ex_md5", table_name="user_scores")
    op.drop_index("ix_user_scores_best_bp_md5", table_name="user_scores")
    op.drop_index("ix_user_scores_best_ct_others", table_name="user_scores")
    op.drop_index("ix_user_scores_best_ex_others", table_name="user_scores")

    op.drop_column("user_scores", "is_best_clear_type")
    op.drop_column("user_scores", "is_best_exscore")
    op.drop_column("user_scores", "is_best_min_bp")
    op.drop_column("user_scores", "is_best_max_combo")


def downgrade() -> None:
    op.add_column(
        "user_scores",
        sa.Column("is_best_max_combo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "user_scores",
        sa.Column("is_best_min_bp", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "user_scores",
        sa.Column("is_best_exscore", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "user_scores",
        sa.Column("is_best_clear_type", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_index(
        "ix_user_scores_best_ct_sha256", "user_scores", ["user_id", "fumen_sha256", "client_type"],
        postgresql_where=sa.text("is_best_clear_type = TRUE AND fumen_sha256 IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_best_ex_sha256", "user_scores", ["user_id", "fumen_sha256", "client_type"],
        postgresql_where=sa.text("is_best_exscore = TRUE AND fumen_sha256 IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_best_bp_sha256", "user_scores", ["user_id", "fumen_sha256", "client_type"],
        postgresql_where=sa.text("is_best_min_bp = TRUE AND fumen_sha256 IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_best_ct_md5", "user_scores", ["user_id", "fumen_md5", "client_type"],
        postgresql_where=sa.text(
            "is_best_clear_type = TRUE AND fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"
        ),
    )
    op.create_index(
        "ix_user_scores_best_ex_md5", "user_scores", ["user_id", "fumen_md5", "client_type"],
        postgresql_where=sa.text(
            "is_best_exscore = TRUE AND fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"
        ),
    )
    op.create_index(
        "ix_user_scores_best_bp_md5", "user_scores", ["user_id", "fumen_md5", "client_type"],
        postgresql_where=sa.text(
            "is_best_min_bp = TRUE AND fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"
        ),
    )
    op.create_index(
        "ix_user_scores_best_ct_others", "user_scores", ["user_id", "fumen_hash_others", "client_type"],
        postgresql_where=sa.text("is_best_clear_type = TRUE AND fumen_hash_others IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_best_ex_others", "user_scores", ["user_id", "fumen_hash_others", "client_type"],
        postgresql_where=sa.text("is_best_exscore = TRUE AND fumen_hash_others IS NOT NULL"),
    )
