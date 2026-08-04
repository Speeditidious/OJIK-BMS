"""Canonical difficulty-table level ordering.

A table carries three admin-configurable ordering columns; resolving them
into a single displayable order is needed by both the analysis router
(clear distribution) and the goals router (filter chips), so it lives here
rather than in either router.
"""
from __future__ import annotations

from typing import Any


def normalize_level_order(value: list[Any] | None) -> list[str]:
    """Return non-empty level labels as strings while preserving order."""
    levels: list[str] = []
    seen: set[str] = set()
    for raw in value or []:
        level = str(raw).strip()
        if not level or level in seen:
            continue
        levels.append(level)
        seen.add(level)
    return levels


def split_table_level_order(
    level_order: list[Any] | None,
    display_level_order: list[Any] | None,
    non_regular_level_order: list[Any] | None,
) -> tuple[list[str], list[str]]:
    """Split display levels into regular and non-regular ordered groups.

    Stale admin-configured values are ignored so table syncs can change
    ``level_order`` without breaking dashboard rendering.
    """
    base_order = normalize_level_order(level_order)
    available = set(base_order)

    non_regular: list[str] = []
    for level in normalize_level_order(non_regular_level_order):
        if level in available:
            non_regular.append(level)
    non_regular_set = set(non_regular)

    regular: list[str] = []
    for level in normalize_level_order(display_level_order):
        if level in available and level not in non_regular_set:
            regular.append(level)

    regular_seen = set(regular)
    for level in base_order:
        if level not in non_regular_set and level not in regular_seen:
            regular.append(level)

    return regular, non_regular
