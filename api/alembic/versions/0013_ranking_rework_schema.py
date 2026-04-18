"""Ranking rework schema.

- user_rankings: add rating_norm column + rebuild indexes.
- user_rankings: TRUNCATE (old standardised values are now meaningless).
- user_ranking_history: DROP TABLE (history is now computed on-demand from user_scores).

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add rating_norm column to user_rankings
    op.add_column(
        "user_rankings",
        sa.Column("rating_norm", sa.Double(), nullable=False, server_default="0"),
    )

    # 2) Rebuild rating index (now sorts by raw top-N sum, not standardised 0-25)
    #    Check actual index name first: \d user_rankings in psql.
    #    The index from migration 0011 was created as ix_ur_rating.
    op.drop_index("ix_ur_rating", table_name="user_rankings")
    op.create_index(
        "ix_ur_rating",
        "user_rankings",
        ["table_id", sa.text("rating DESC")],
    )
    op.create_index(
        "ix_ur_rating_norm",
        "user_rankings",
        ["table_id", sa.text("rating_norm DESC")],
    )

    # 3) Old rating values are on the 0-25 scale; new meaning is raw top-N sum.
    #    Truncate so lifespan recalculation fills correct values from scratch.
    op.execute("TRUNCATE TABLE user_rankings")

    # 4) Drop user_ranking_history — history is now computed on-demand from user_scores.
    #    Indexes on that table are auto-removed by DROP TABLE.
    op.drop_table("user_ranking_history")


def downgrade() -> None:
    # Recreate user_ranking_history (empty — original data is gone)
    op.create_table(
        "user_ranking_history",
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
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("exp", sa.Double(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Double(), nullable=False, server_default="0"),
        sa.Column(
            "rating_contributions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("user_id", "table_id", "date"),
    )
    op.execute(
        "CREATE INDEX ix_urh_user_table_date "
        "ON user_ranking_history (user_id, table_id, date DESC)"
    )

    # Revert indexes on user_rankings
    op.drop_index("ix_ur_rating_norm", table_name="user_rankings")
    op.drop_index("ix_ur_rating", table_name="user_rankings")
    op.create_index(
        "ix_ur_rating",
        "user_rankings",
        ["table_id", sa.text("rating DESC")],
    )

    # Remove rating_norm column
    op.drop_column("user_rankings", "rating_norm")
