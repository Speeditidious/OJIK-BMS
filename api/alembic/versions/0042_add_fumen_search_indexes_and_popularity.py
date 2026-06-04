"""Add fumen search indexes and play popularity."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "fumen_play_popularity",
        sa.Column(
            "fumen_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fumens.fumen_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("played_user_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_play_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "fumen_popularity_dirty",
        sa.Column(
            "fumen_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fumens.fumen_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "fumen_popularity_window",
        sa.Column("window", sa.String(length=16), primary_key=True),
        sa.Column(
            "fumen_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fumens.fumen_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("played_user_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("play_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_fumen_popularity_window_rank",
        "fumen_popularity_window",
        ["window", "rank"],
    )

    op.execute(
        """
        CREATE INDEX ix_user_scores_synced_at
        ON user_scores (synced_at)
        WHERE fumen_hash_others IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO fumen_play_popularity (fumen_id, played_user_count, total_play_count, updated_at)
        WITH resolved_scores AS (
            SELECT COALESCE(us.fumen_id, f_sha.fumen_id, f_md5.fumen_id) AS resolved_fumen_id,
                   us.user_id,
                   us.play_count
            FROM user_scores us
            LEFT JOIN fumens f_sha
              ON us.fumen_id IS NULL
             AND us.fumen_sha256 IS NOT NULL
             AND us.fumen_sha256 = f_sha.sha256
            LEFT JOIN fumens f_md5
              ON us.fumen_id IS NULL
             AND f_sha.fumen_id IS NULL
             AND us.fumen_md5 IS NOT NULL
             AND us.fumen_md5 = f_md5.md5
            WHERE us.fumen_hash_others IS NULL
        )
        SELECT resolved_fumen_id AS fumen_id,
               COUNT(*)::integer,
               COALESCE(SUM(user_plays), 0)::integer,
               now()
        FROM (
            SELECT resolved_fumen_id, user_id, MAX(COALESCE(play_count, 0)) AS user_plays
            FROM resolved_scores
            WHERE resolved_fumen_id IS NOT NULL
            GROUP BY resolved_fumen_id, user_id
        ) per_user
        GROUP BY resolved_fumen_id
        """
    )

    op.execute(
        """
        CREATE INDEX ix_fumen_play_popularity_count
        ON fumen_play_popularity (played_user_count DESC, total_play_count DESC, fumen_id)
        """
    )
    op.create_index(
        "ix_fumen_play_popularity_plays",
        "fumen_play_popularity",
        ["total_play_count", "fumen_id"],
    )
    op.create_index(
        "ix_fumen_play_popularity_updated_at",
        "fumen_play_popularity",
        ["updated_at"],
    )

    op.execute(
        """
        CREATE INDEX ix_fumens_title_norm_trgm
        ON fumens USING gin ((regexp_replace(lower(coalesce(title, '')), '[^[:alnum:]]+', '', 'g')) gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fumens_artist_norm_trgm
        ON fumens USING gin ((regexp_replace(lower(coalesce(artist, '')), '[^[:alnum:]]+', '', 'g')) gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fumens_title_trgm
        ON fumens USING gin ((lower(coalesce(title, ''))) gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fumens_artist_trgm
        ON fumens USING gin ((lower(coalesce(artist, ''))) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_scores_synced_at")
    op.execute("DROP INDEX IF EXISTS ix_fumens_artist_trgm")
    op.execute("DROP INDEX IF EXISTS ix_fumens_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_fumens_artist_norm_trgm")
    op.execute("DROP INDEX IF EXISTS ix_fumens_title_norm_trgm")
    op.drop_index("ix_fumen_popularity_window_rank", table_name="fumen_popularity_window")
    op.drop_table("fumen_popularity_window")
    op.drop_index("ix_fumen_play_popularity_updated_at", table_name="fumen_play_popularity")
    op.drop_index("ix_fumen_play_popularity_plays", table_name="fumen_play_popularity")
    op.drop_index("ix_fumen_play_popularity_count", table_name="fumen_play_popularity")
    op.drop_table("fumen_popularity_dirty")
    op.drop_table("fumen_play_popularity")
