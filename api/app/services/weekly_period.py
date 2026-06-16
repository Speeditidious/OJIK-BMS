"""Weekly rollover period calculation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def current_period(
    now: datetime,
    day_of_week: str,
    hour: int,
    minute: int,
    tz_name: str,
) -> tuple[datetime, datetime]:
    """Return [start, end) of the weekly period containing *now*.

    start = most recent rollover instant <= now, expressed in UTC.
    end = start + 7 days.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    tz = ZoneInfo(tz_name)
    local = now.astimezone(tz)
    target_wd = _WEEKDAYS[day_of_week]

    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_since = (local.weekday() - target_wd) % 7
    candidate = candidate - timedelta(days=days_since)
    if candidate > local:
        candidate = candidate - timedelta(days=7)

    start_utc = candidate.astimezone(UTC)
    return start_utc, start_utc + timedelta(days=7)


def period_for_offset(
    now: datetime,
    offset: int,
    day_of_week: str,
    hour: int,
    minute: int,
    tz_name: str,
) -> tuple[datetime, datetime]:
    """Return the period *offset* weeks from the current one (negative = past)."""
    start, _ = current_period(now, day_of_week, hour, minute, tz_name)
    shifted = start + timedelta(days=7 * offset)
    return shifted, shifted + timedelta(days=7)
