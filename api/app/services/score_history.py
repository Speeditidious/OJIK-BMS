"""Helpers for interpreting append-only score history rows."""

from app.models.score import UserScore
from app.services.clear_type_display import display_clear_type


def score_has_record_improvement(entry: UserScore, prev: UserScore | None) -> bool:
    """Return whether a score row improves gameplay record fields over ``prev``."""
    if prev is None:
        return True

    entry_clear = display_clear_type(entry.clear_type, exscore=entry.exscore, rate=entry.rate) or 0
    prev_clear = display_clear_type(prev.clear_type, exscore=prev.exscore, rate=prev.rate) or 0

    return (
        entry_clear > prev_clear
        or (entry.exscore or 0) > (prev.exscore or 0)
        or (
            entry.min_bp is not None
            and (prev.min_bp is None or entry.min_bp < prev.min_bp)
        )
        or (entry.max_combo or 0) > (prev.max_combo or 0)
    )


def is_play_count_only_update(entry: UserScore, prev: UserScore | None) -> bool:
    """Return True when only play_count changed compared with the prior row."""
    if prev is None:
        return False
    if score_has_record_improvement(entry, prev):
        return False
    return (entry.play_count or 0) != (prev.play_count or 0)
