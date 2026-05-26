"""Helpers for user-controlled level/table-entry display preferences."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.difficulty_table import DifficultyTable, UserFavoriteDifficultyTable
from app.models.user import User

LEVEL_DISPLAY_KEY = "level_display"
LEVEL_DISPLAY_SCOPES = ("favorite", "server_default", "user_added", "ojik_custom")
DEFAULT_LEVEL_DISPLAY_PREFERENCES: dict[str, bool] = {
    "favorite": True,
    "server_default": False,
    "user_added": False,
    "ojik_custom": False,
}


def normalize_level_display_preferences(raw: Any) -> dict[str, bool]:
    """Return a complete level-display preference map with safe defaults."""
    if not isinstance(raw, dict):
        return dict(DEFAULT_LEVEL_DISPLAY_PREFERENCES)

    normalized = dict(DEFAULT_LEVEL_DISPLAY_PREFERENCES)
    for key in LEVEL_DISPLAY_SCOPES:
        value = raw.get(key)
        if isinstance(value, bool):
            normalized[key] = value
    return normalized


def normalize_preferences_payload(preferences: dict[str, Any]) -> dict[str, Any]:
    """Normalize supported nested preference payloads before storing JSONB."""
    if LEVEL_DISPLAY_KEY not in preferences:
        return preferences
    return {
        **preferences,
        LEVEL_DISPLAY_KEY: normalize_level_display_preferences(preferences.get(LEVEL_DISPLAY_KEY)),
    }


async def resolve_visible_table_ids(
    db: AsyncSession,
    current_user: User | None,
) -> set[uuid.UUID] | None:
    """Return visible difficulty table ids, or None when all regular tables are visible."""
    prefs = normalize_level_display_preferences(
        (current_user.preferences or {}).get(LEVEL_DISPLAY_KEY) if current_user else None
    )

    if prefs["favorite"] and prefs["server_default"] and prefs["user_added"]:
        return None

    visible: set[uuid.UUID] = set()

    if current_user and prefs["favorite"]:
        rows = await db.execute(
            select(UserFavoriteDifficultyTable.table_id).where(
                UserFavoriteDifficultyTable.user_id == current_user.id
            )
        )
        visible.update(rows.scalars().all())

    table_conditions = []
    if prefs["server_default"]:
        table_conditions.append(DifficultyTable.is_default.is_(True))
    if prefs["user_added"]:
        table_conditions.append(
            DifficultyTable.is_default.is_(False) & DifficultyTable.source_url.is_not(None)
        )

    if table_conditions:
        rows = await db.execute(
            select(DifficultyTable.id).where(or_(*table_conditions))
        )
        visible.update(rows.scalars().all())

    return visible
