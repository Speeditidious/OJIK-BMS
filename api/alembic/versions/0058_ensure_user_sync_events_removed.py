"""Ensure user_sync_events is removed.

Revision ID: 0058
Revises: 0057
Create Date: 2026-08-06
"""
from alembic import op


revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Idempotently remove user_sync_events for databases that already applied 0057."""
    op.execute("DROP INDEX IF EXISTS ux_user_sync_events_user_sync_date")
    op.execute("DROP INDEX IF EXISTS ux_user_sync_events_visible_user_sync_date")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_sync_date_user")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_user_synced_at")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_updated_synced_at_id")
    op.execute("DROP INDEX IF EXISTS ix_user_sync_events_synced_at_id")
    op.execute("DROP TABLE IF EXISTS user_sync_events")


def downgrade() -> None:
    """No-op: 0057 downgrade recreates user_sync_events when needed."""
    pass
