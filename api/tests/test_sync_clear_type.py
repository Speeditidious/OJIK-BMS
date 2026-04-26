"""Tests for display clear type normalization."""

from app.services.clear_type_display import display_clear_type


def test_display_clear_type_zero_max_to_fc() -> None:
    """Zero-score MAX should be displayed as FC."""
    assert display_clear_type(9, exscore=0, rate=0.0) == 7


def test_display_clear_type_non_100_max_to_perfect() -> None:
    """Known non-100 MAX should be displayed as PERFECT."""
    assert display_clear_type(9, exscore=1998, rate=99.9) == 8


def test_display_clear_type_100_max_unchanged() -> None:
    """Known 100.00% MAX should stay MAX."""
    assert display_clear_type(9, exscore=2000, rate=100.0) == 9


def test_display_clear_type_non_max_unchanged() -> None:
    """Non-MAX clear types should pass through unchanged."""
    assert display_clear_type(7, exscore=0, rate=0.0) == 7
