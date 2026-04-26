"""Tests for sync clear type normalization."""

from app.routers.sync import _normalize_synced_clear_type


def test_normalize_synced_clear_type_zero_max_to_fc() -> None:
    """Zero-score MAX should be stored as FC."""
    assert _normalize_synced_clear_type(9, exscore=0, rate=0.0) == 7


def test_normalize_synced_clear_type_non_100_max_to_perfect() -> None:
    """Known non-100 MAX should be stored as PERFECT."""
    assert _normalize_synced_clear_type(9, exscore=1998, rate=99.9) == 8


def test_normalize_synced_clear_type_100_max_unchanged() -> None:
    """Known 100.00% MAX should stay MAX."""
    assert _normalize_synced_clear_type(9, exscore=2000, rate=100.0) == 9
