"""Helpers for identifying records imported during a user's first sync."""

from datetime import UTC, datetime, timedelta

INITIAL_SYNC_WINDOW_HOURS = 3
INITIAL_SYNC_SQL_INTERVAL = f"interval '{INITIAL_SYNC_WINDOW_HOURS} hours'"


def parse_first_synced_at(value: str | None) -> datetime | None:
    """Parse a stored first-sync timestamp as a timezone-aware datetime."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def initial_sync_cutoff(value: str | None) -> datetime | None:
    """Return the end timestamp of the first-sync uncertainty window."""
    first_synced_at = parse_first_synced_at(value)
    if first_synced_at is None:
        return None
    return first_synced_at + timedelta(hours=INITIAL_SYNC_WINDOW_HOURS)


def is_initial_sync_timestamp(
    first_synced_at: dict[str, str] | None,
    client_type: str | None,
    synced_at: datetime | None,
) -> bool:
    """Return whether a row's sync timestamp falls inside the first-sync window."""
    if not first_synced_at or not client_type or synced_at is None:
        return False

    cutoff = initial_sync_cutoff(first_synced_at.get(client_type))
    if cutoff is None:
        return False

    if synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=UTC)
    return synced_at <= cutoff
