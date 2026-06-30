"""Score rank helpers shared by sync, migrations, and display code."""

from __future__ import annotations

import math
from typing import Any

RANK_THRESHOLDS: tuple[tuple[str, int], ...] = (
    ("MAX-", 17),
    ("AAA", 16),
    ("AA", 14),
    ("A", 12),
    ("B", 10),
    ("C", 8),
    ("D", 6),
    ("E", 4),
)


def rank_from_exscore(exscore: int, notes: int) -> str | None:
    """Return BMS score rank for an EX score and total notes."""
    if notes <= 0:
        return None
    for rank, threshold in RANK_THRESHOLDS:
        if exscore * 9 >= notes * threshold:
            return rank
    return "F"


def rate_from_exscore(exscore: int, notes: int) -> float | None:
    """Return floored score rate percentage for an EX score and total notes."""
    max_exscore = notes * 2
    if max_exscore <= 0:
        return None
    return math.floor(exscore / max_exscore * 10000) / 100


def max_minus_score(exscore: int | None, notes: int | None) -> int | None:
    """Return remaining EX score to theoretical MAX, if both values are known."""
    if exscore is None or notes is None or notes <= 0:
        return None
    return max(notes * 2 - exscore, 0)


def notes_from_judgments(client_type: str | None, judgments: dict[str, Any] | None) -> int | None:
    """Infer total notes from judgment counts when explicit chart notes are unavailable."""
    if not judgments:
        return None
    if client_type == "lr2":
        keys = ("perfect", "great", "good", "bad", "poor")
    elif client_type == "beatoraja":
        keys = ("epg", "lpg", "egr", "lgr", "egd", "lgd", "ebd", "lbd", "epr", "lpr", "ems", "lms")
    else:
        return None
    total = sum(int(judgments.get(key, 0) or 0) for key in keys)
    return total or None
