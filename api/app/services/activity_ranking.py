"""30-day user activity leaderboard aggregation.

Recomputes the ``user_activity_ranking`` snapshot for 3 metrics
(attendance / plays / notes_hit) from ``UserSyncEvent`` and ``UserPlayerStats``.
Mirrors the delta math already used by ``api/app/routers/analysis.py``'s
``_get_daily_plays`` / ``_get_day_stats`` (LAG-style play/notes deltas), but
computed row-by-row in Python (see module docstring on ``rebuild_activity_ranking``
for why) instead of as a SQL window-function expression, to sidestep the
SQLite/Postgres portability gap for JSONB delta math.

Callers control the transaction boundary (mirrors ``fumen_popularity.py``'s
convention) — this module never calls ``db.commit()``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.score import UserActivityRanking, UserPlayerStats, UserSyncEvent
from app.models.user import User
from app.services.player_stats_reliability import lr2_stats_unreliable_sql

#: Inclusive window length in days (30 days total, including `today`).
_WINDOW_DAYS = 30

#: LR2 judgment keys counted as "notes hit" (poor excluded).
_LR2_NOTES_HIT_KEYS = ("perfect", "great", "good", "bad")

#: Beatoraja judgment keys counted as "notes hit" (poor/pr/ms excluded).
_BEATORAJA_NOTES_HIT_KEYS = ("epg", "lpg", "egr", "lgr", "egd", "lgd", "ebd", "lbd")


@dataclass
class _StatsRow:
    """One `UserPlayerStats` row's fields needed for delta computation."""

    user_id: UUID
    client_type: str
    synced_at: Any
    playcount: int | None
    judgments: dict | None
    in_window: bool


def _notes_hit_delta(client_type: str, current: dict | None, previous: dict | None) -> int:
    """Sum max(0, current[k] - previous[k]) over the client's notes-hit key set.

    Mirrors `analysis.py::_get_day_stats`'s key mapping and clamp behavior.
    """
    if previous is None:
        return 0
    keys = _LR2_NOTES_HIT_KEYS if client_type == "lr2" else _BEATORAJA_NOTES_HIT_KEYS
    cur = current or {}
    prev = previous or {}
    return sum(max(0, int(cur.get(k) or 0) - int(prev.get(k) or 0)) for k in keys)


def _playcount_delta(current: int | None, previous: int | None) -> int:
    """GREATEST(0, current - COALESCE(previous, current)), matching `_get_daily_plays`."""
    baseline = previous if previous is not None else current
    return max(0, int(current or 0) - int(baseline or 0))


def _dialect_name(db: AsyncSession) -> str:
    """Return the bound dialect's name, defaulting to postgresql (mirrors `fumen_popularity.py`)."""
    bind = db.get_bind()
    return bind.dialect.name if bind is not None else "postgresql"


def _utc_date_expr(value: Any, dialect_name: str) -> Any:
    """UTC calendar-day expression for a timestamp column, per dialect.

    Same helper shape as `app/services/fumen_popularity.py::_utc_date_expr`.
    The Postgres branch renders `CAST(timezone('UTC', <col>) AS DATE)`, which is
    exactly what `<col> AT TIME ZONE 'UTC')::date` normalizes to — that matches
    the expression of the functional index `ix_user_sync_events_sync_date_user`
    and so keeps that index usable by the planner. SQLite (this repo's test
    backend) has no `timezone()` function, hence the `date()` fallback.
    """
    if dialect_name == "sqlite":
        return sa.func.date(value)
    return sa.cast(sa.func.timezone("UTC", value), sa.Date)


async def _compute_attendance(
    db: AsyncSession, window_start: date, window_end_exclusive: date
) -> dict[UUID, int]:
    """COUNT(DISTINCT UTC day) of UserSyncEvent rows per active user_id in the window.

    Deactivated users are excluded outright (not merely hidden at display time),
    mirroring `ranking_calculator.select_ranking_user_ids`'s `is_active IS TRUE`.
    """
    sync_day = _utc_date_expr(UserSyncEvent.synced_at, _dialect_name(db))
    result = await db.execute(
        sa.select(
            UserSyncEvent.user_id,
            sa.func.count(sa.func.distinct(sync_day)).label("days"),
        )
        .join(User, User.id == UserSyncEvent.user_id)
        .where(
            UserSyncEvent.synced_at >= window_start,
            UserSyncEvent.synced_at < window_end_exclusive,
            User.is_active.is_(True),
        )
        .group_by(UserSyncEvent.user_id)
    )
    return {row.user_id: int(row.days) for row in result.all()}


async def _compute_plays_and_notes_hit(
    db: AsyncSession, window_start: date, window_end_exclusive: date
) -> tuple[dict[UUID, int], dict[UUID, int]]:
    """Sum per-(user_id, client_type) LAG-style deltas for plays and notes_hit.

    Query shape (avoids N+1 and Postgres-only syntax):
      1. distinct (user_id, client_type) pairs, for *active* users only, with
         >=1 reliable row in the window.
      2. the single most-recent row before window_start per pair, via ROW_NUMBER().
      3. all in-window rows for those pairs, ordered by synced_at.
      4. walk consecutive pairs in Python to compute deltas.
    """
    h = UserPlayerStats
    reliable = sa.not_(lr2_stats_unreliable_sql(h))

    pairs_result = await db.execute(
        sa.select(h.user_id, h.client_type)
        .join(User, User.id == h.user_id)
        .where(
            h.synced_at >= window_start,
            h.synced_at < window_end_exclusive,
            reliable,
            # Deactivated users are excluded from the candidate set entirely, so
            # they are never counted or ranked (not merely hidden at display time).
            User.is_active.is_(True),
        )
        .distinct()
    )
    pairs = [(row.user_id, row.client_type) for row in pairs_result.all()]
    if not pairs:
        return {}, {}

    pair_filter = sa.tuple_(h.user_id, h.client_type).in_(pairs)

    # Step 2: most-recent baseline row before window_start, per pair.
    baseline_ranked = (
        sa.select(
            h.user_id,
            h.client_type,
            h.synced_at,
            h.playcount,
            h.judgments,
            sa.func.row_number()
            .over(
                partition_by=(h.user_id, h.client_type),
                order_by=h.synced_at.desc(),
            )
            .label("rn"),
        )
        .where(pair_filter, h.synced_at < window_start, reliable)
        .subquery("baseline_ranked")
    )
    baseline_result = await db.execute(
        sa.select(
            baseline_ranked.c.user_id,
            baseline_ranked.c.client_type,
            baseline_ranked.c.synced_at,
            baseline_ranked.c.playcount,
            baseline_ranked.c.judgments,
        ).where(baseline_ranked.c.rn == 1)
    )

    # Step 3: all in-window rows for those pairs.
    window_result = await db.execute(
        sa.select(h.user_id, h.client_type, h.synced_at, h.playcount, h.judgments)
        .where(
            pair_filter,
            h.synced_at >= window_start,
            h.synced_at < window_end_exclusive,
            reliable,
        )
        .order_by(h.user_id, h.client_type, h.synced_at)
    )

    grouped: dict[tuple[UUID, str], list[_StatsRow]] = defaultdict(list)
    for r in baseline_result.all():
        key = (r.user_id, r.client_type)
        grouped[key].append(
            _StatsRow(r.user_id, r.client_type, r.synced_at, r.playcount, r.judgments, in_window=False)
        )
    for r in window_result.all():
        key = (r.user_id, r.client_type)
        grouped[key].append(
            _StatsRow(r.user_id, r.client_type, r.synced_at, r.playcount, r.judgments, in_window=True)
        )

    plays: dict[UUID, int] = defaultdict(int)
    notes_hit: dict[UUID, int] = defaultdict(int)

    for (user_id, _client_type), rows in grouped.items():
        rows.sort(key=lambda r: r.synced_at)
        previous: _StatsRow | None = None
        for row in rows:
            if row.in_window:
                plays[user_id] += _playcount_delta(row.playcount, previous.playcount if previous else None)
                notes_hit[user_id] += _notes_hit_delta(
                    row.client_type, row.judgments, previous.judgments if previous else None
                )
            previous = row

    return dict(plays), dict(notes_hit)


def _rank_rows(
    values: dict[UUID, int], usernames: dict[UUID, str]
) -> list[tuple[UUID, int, int]]:
    """Drop zero values, sort by (value DESC, username ASC), assign rank 1..N.

    Returns a list of (user_id, rank, value) tuples.
    """
    nonzero = [(uid, v) for uid, v in values.items() if v != 0]
    nonzero.sort(key=lambda item: (-item[1], usernames.get(item[0], "")))
    return [(uid, rank, value) for rank, (uid, value) in enumerate(nonzero, start=1)]


async def rebuild_activity_ranking(db: AsyncSession, *, today: date | None = None) -> dict[str, int]:
    """Recompute the 3 activity metrics and replace the user_activity_ranking snapshot.

    window_end = today (UTC) if not given; window_start = window_end - 29 days (30-day
    inclusive window). Deletes all existing rows per metric and inserts the freshly
    computed ranking rows, so the two operations must happen inside the same transaction
    that the caller controls (does not commit internally — mirrors the
    fumen_popularity.py convention of leaving transaction control to the caller).

    Returns {"attendance": <n rows written>, "plays": <n rows written>, "notes_hit": <n rows written>}.
    """
    window_end = today if today is not None else date.today()
    window_start = window_end - timedelta(days=_WINDOW_DAYS - 1)
    window_end_exclusive = window_end + timedelta(days=1)

    attendance = await _compute_attendance(db, window_start, window_end_exclusive)
    plays, notes_hit = await _compute_plays_and_notes_hit(db, window_start, window_end_exclusive)

    all_user_ids = set(attendance) | set(plays) | set(notes_hit)
    usernames: dict[UUID, str] = {}
    if all_user_ids:
        username_result = await db.execute(
            sa.select(User.id, User.username).where(User.id.in_(all_user_ids))
        )
        usernames = {row.id: row.username for row in username_result.all()}

    written: dict[str, int] = {}
    metric_values = {"attendance": attendance, "plays": plays, "notes_hit": notes_hit}
    for metric, values in metric_values.items():
        ranked = _rank_rows(values, usernames)
        await db.execute(sa.delete(UserActivityRanking).where(UserActivityRanking.metric == metric))
        if ranked:
            db.add_all(
                [
                    UserActivityRanking(
                        metric=metric,
                        user_id=user_id,
                        rank=rank,
                        value=value,
                        window_start=window_start,
                        window_end=window_end,
                    )
                    for user_id, rank, value in ranked
                ]
            )
        written[metric] = len(ranked)

    await db.flush()
    return written
