"""Tests for difficulty table synchronization."""
from __future__ import annotations

from app.services.table_sync import _normalize_db_level_order


def test_normalize_db_level_order_maps_only_gachimijoy_level_eight_to_unknown() -> None:
    """Gachimijoy's stale upstream level 8 should persist as its real ? group."""
    upstream_level_order = ["0", "7", "8"]

    assert _normalize_db_level_order("gachimijoy", upstream_level_order) == [
        "0",
        "7",
        "?",
    ]
    assert _normalize_db_level_order("another-table", upstream_level_order) == [
        "0",
        "7",
        "8",
    ]
    assert upstream_level_order == ["0", "7", "8"]
