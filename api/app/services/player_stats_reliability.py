"""Shared predicate for detecting unreliable LR2 player statistics.

LR2ALT (an IR service for BMS game LR2) has a known bug where it can produce
corrupted player statistics with ``playcount > 0`` but ``playtime = 0``.
These rows must be identified and filtered at read time using a self-consistency
check: if the total recorded playtime is implausibly short relative to playcount,
the row is considered unreliable.

This module is the single source of truth for that predicate.  Import it from
all read paths that consume ``user_player_stats`` rows.
"""

from sqlalchemy import and_

#: Minimum average seconds per play expected for a real LR2 session.
#: A single BMS chart takes well over 10 seconds; anything below this ratio
#: indicates a corrupted statistics row produced by the LR2ALT bug.
LR2_MIN_SECONDS_PER_PLAY = 10


def lr2_stats_unreliable_sql(model):
    """Return a SQLAlchemy boolean clause for unreliable LR2 player-stat rows.

    A row is considered unreliable when its client_type is ``"lr2"`` and the
    total playtime is implausibly low relative to playcount (i.e., less than
    :data:`LR2_MIN_SECONDS_PER_PLAY` seconds per play on average).

    Args:
        model: The SQLAlchemy mapped class (e.g. ``UserPlayerStats``).

    Returns:
        A SQLAlchemy ``BinaryExpression`` that evaluates to ``True`` for
        unreliable rows and ``False`` for reliable ones.
    """
    return and_(
        model.client_type == "lr2",
        model.playcount.isnot(None),
        model.playcount > 0,
        model.playtime.isnot(None),
        model.playtime < LR2_MIN_SECONDS_PER_PLAY * model.playcount,
    )


def is_lr2_stats_unreliable(client_type: str, playcount: int | None, playtime: int | None) -> bool:
    """Python mirror of :func:`lr2_stats_unreliable_sql` for unit tests and helpers.

    Args:
        client_type: The client type string (e.g. ``"lr2"`` or ``"beatoraja"``).
        playcount: Total number of plays recorded, or ``None`` if absent.
        playtime: Total playtime in seconds recorded, or ``None`` if absent.

    Returns:
        ``True`` if the stats row is self-inconsistent (unreliable),
        ``False`` otherwise.
    """
    return (
        client_type == "lr2"
        and playcount is not None and playcount > 0
        and playtime is not None
        and playtime < LR2_MIN_SECONDS_PER_PLAY * playcount
    )
