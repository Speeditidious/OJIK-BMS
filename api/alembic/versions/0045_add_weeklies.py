"""Add weeklies and weekly_fumens tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weeklies",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("category_key", sa.String(length=64), nullable=False),
        sa.Column("bracket_key", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("config_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_forced", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "category_key", "bracket_key", "period_start",
            name="uq_weeklies_category_bracket_period",
        ),
    )
    op.create_index(
        "ix_weeklies_category_bracket_period",
        "weeklies",
        ["category_key", "bracket_key", "period_start"],
    )

    op.create_table(
        "weekly_fumens",
        sa.Column(
            "weekly_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("weeklies.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column(
            "fumen_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fumens.fumen_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "table_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("difficulty_tables.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("table_symbol", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_weekly_fumens_weekly_id", "weekly_fumens", ["weekly_id"])
    op.create_index("ix_weekly_fumens_fumen_id", "weekly_fumens", ["fumen_id"])

    # Weekly record lookup starts from a fumen identity, not from user_id.
    # These partial indexes cover sha256 and LR2 md5-only identity paths.
    op.execute(
        """
        CREATE INDEX ix_user_scores_weekly_sha256_user_ts
        ON user_scores (fumen_sha256, user_id, recorded_at, synced_at)
        WHERE fumen_hash_others IS NULL AND fumen_sha256 IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_user_scores_weekly_md5_user_ts
        ON user_scores (fumen_md5, user_id, recorded_at, synced_at)
        WHERE fumen_hash_others IS NULL AND fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_scores_weekly_md5_user_ts")
    op.execute("DROP INDEX IF EXISTS ix_user_scores_weekly_sha256_user_ts")
    op.drop_index("ix_weekly_fumens_fumen_id", table_name="weekly_fumens")
    op.drop_index("ix_weekly_fumens_weekly_id", table_name="weekly_fumens")
    op.drop_table("weekly_fumens")
    op.drop_index("ix_weeklies_category_bracket_period", table_name="weeklies")
    op.drop_table("weeklies")
