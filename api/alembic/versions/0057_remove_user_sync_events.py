"""Remove user_sync_events.

Revision ID: 0057
Revises: 0056
Create Date: 2026-08-06
"""
from alembic import op


revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop the obsolete sync-event table; activity now uses user_player_stats."""
    op.execute("DROP INDEX IF EXISTS ux_user_sync_events_user_sync_date")
    op.execute("DROP INDEX IF EXISTS ux_user_sync_events_visible_user_sync_date")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_sync_date_user")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_user_synced_at")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_updated_synced_at_id")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_synced_at_id")
    op.execute("DROP TABLE IF EXISTS user_sync_events")


def downgrade() -> None:
    """Recreate user_sync_events and backfill it from user_player_stats."""
    op.execute(
        """
        CREATE TABLE user_sync_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_client_types JSONB NOT NULL DEFAULT '[]'::jsonb
        )
        """
    )
    op.execute(
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
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_sync_events_synced_at_id
        ON user_sync_events (synced_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_sync_events_updated_synced_at_id
        ON user_sync_events (synced_at DESC, id DESC)
        WHERE jsonb_array_length(updated_client_types) > 0
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_sync_events_user_synced_at
        ON user_sync_events (user_id, synced_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_sync_events_sync_date_user
        ON user_sync_events (((synced_at AT TIME ZONE 'UTC')::date), user_id)
        """
    )
