"""Add user_sync_events and user_activity_ranking tables for the home activity section.

Revision ID: 0054
Revises: 0053
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── user_sync_events ────────────────────────────────────────────────────
    # One row per successful sync request, independent from player-stat rows.
    op.create_table(
        "user_sync_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_client_types",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # Expression/DESC-ordered indexes — not representable via op.create_index column lists.
    op.execute(
        """
        CREATE INDEX ix_user_sync_events_synced_at_id
        ON user_sync_events (synced_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_user_sync_events_updated_synced_at_id
        ON user_sync_events (synced_at DESC, id DESC)
        WHERE jsonb_array_length(updated_client_types) > 0
        """
    )
    op.execute(
        """
        CREATE INDEX ix_user_sync_events_user_synced_at
        ON user_sync_events (user_id, synced_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_user_sync_events_sync_date_user
        ON user_sync_events (((synced_at AT TIME ZONE 'UTC')::date), user_id)
        """
    )

    # ── user_activity_ranking ───────────────────────────────────────────────
    # Precomputed 30-day activity leaderboard rows (attendance / plays / notes_hit).
    op.create_table(
        "user_activity_ranking",
        sa.Column("metric", sa.String(length=16), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_user_activity_ranking_metric_rank",
        "user_activity_ranking",
        ["metric", "rank"],
    )

    # ── backfill user_sync_events from existing user_player_stats ──────────
    # One event per (user, UTC day), synced_at = latest sync in that day,
    # updated_client_types = distinct client types synced that day (sorted).
    op.execute(
        sa.text(
            """
            INSERT INTO user_sync_events (user_id, synced_at, updated_client_types)
            SELECT
                user_id,
                MAX(synced_at) AS synced_at,
                to_jsonb(array_agg(DISTINCT client_type ORDER BY client_type)) AS updated_client_types
            FROM user_player_stats
            GROUP BY user_id, (synced_at AT TIME ZONE 'UTC')::date
            """
        )
    )

    # ── new index on existing user_player_stats table ──────────────────────
    op.execute(
        """
        CREATE INDEX ix_user_player_stats_user_client_synced_at_desc
        ON user_player_stats (user_id, client_type, synced_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_player_stats_user_client_synced_at_desc")

    op.drop_index("ix_user_activity_ranking_metric_rank", table_name="user_activity_ranking")
    op.drop_table("user_activity_ranking")

    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_sync_date_user")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_user_synced_at")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_updated_synced_at_id")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_synced_at_id")
    op.drop_table("user_sync_events")
