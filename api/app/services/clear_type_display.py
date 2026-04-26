"""Presentation helpers for clear type values."""


def display_clear_type(
    clear_type: int | None,
    *,
    exscore: int | None = None,
    rate: float | None = None,
) -> int | None:
    """Return the frontend-facing clear type without mutating stored data."""
    if clear_type != 9:
        return clear_type
    if exscore == 0:
        return 7
    if rate is not None and rate != 100.0:
        return 8
    return clear_type
