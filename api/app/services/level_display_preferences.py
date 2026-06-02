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
    "favorite_show_non_regular": True,
    "server_default_show_non_regular": True,
    "user_added_show_non_regular": True,
    "ojik_custom_show_non_regular": True,
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
        nr_key = f"{key}_show_non_regular"
        nr_value = raw.get(nr_key)
        if isinstance(nr_value, bool):
            normalized[nr_key] = nr_value
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


async def resolve_non_regular_hidden_levels(
    db: AsyncSession,
    current_user: User | None,
) -> dict[uuid.UUID, set[str]]:
    """Return table_id → set[level] for non-regular levels that should be hidden.

    A table's non-regular levels are hidden only when every source scope the
    table belongs to has ``show_non_regular = False``.  If any scope says show,
    the non-regular levels remain visible (most-permissive wins).
    """
    prefs = normalize_level_display_preferences(
        (current_user.preferences or {}).get(LEVEL_DISPLAY_KEY) if current_user else None
    )

    if current_user is None:
        return {}

    # Early exit: nothing to hide when all scopes show non-regular
    if all(prefs[f"{s}_show_non_regular"] for s in LEVEL_DISPLAY_SCOPES):
        return {}

    # Collect user's favorite table IDs
    fav_ids: set[uuid.UUID] = set()
    if current_user:
        rows = await db.execute(
            select(UserFavoriteDifficultyTable.table_id).where(
                UserFavoriteDifficultyTable.user_id == current_user.id
            )
        )
        fav_ids = set(rows.scalars().all())

    # Fetch all tables that have non_regular_level_order set
    result = await db.execute(
        select(
            DifficultyTable.id,
            DifficultyTable.non_regular_level_order,
            DifficultyTable.is_default,
            DifficultyTable.source_url,
        ).where(DifficultyTable.non_regular_level_order.isnot(None))
    )

    hidden: dict[uuid.UUID, set[str]] = {}
    for row in result.all():
        if not row.non_regular_level_order:
            continue

        # A table may belong to multiple scopes (e.g. server_default + favorited).
        table_scopes: list[str] = []
        if row.id in fav_ids:
            table_scopes.append("favorite")
        if row.is_default:
            table_scopes.append("server_default")
        elif row.source_url:
            table_scopes.append("user_added")
        else:
            table_scopes.append("ojik_custom")

        # If table belongs to no known scope, treat as visible (don't hide non-regular).
        # Hide non-regular only when ALL applicable scopes say hide
        if table_scopes and all(not prefs[f"{s}_show_non_regular"] for s in table_scopes):
            hidden[row.id] = {str(lv) for lv in row.non_regular_level_order}

    return hidden
