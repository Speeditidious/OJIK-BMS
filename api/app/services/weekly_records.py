"""Live aggregation of weekly player records from append-only user_scores."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.score import UserScore


def _effective_ts(row) -> datetime | None:
    return row.recorded_at or row.synced_at


@dataclass
class RecordSnapshot:
    clear_type: int | None
    exscore: int | None
    min_bp: int | None
    rate: float | None
    rank: str | None
    effective_ts: datetime | None


@dataclass
class RecordImprovement:
    is_first_record: bool
    clear_type_changed: bool
    exscore_delta: int | None
    min_bp_delta: int | None
    rate_delta: float | None
    rank_changed: bool

    @property
    def has_changes(self) -> bool:
        return (
            self.is_first_record
            or self.clear_type_changed
            or (self.exscore_delta is not None and self.exscore_delta > 0)
            or (self.min_bp_delta is not None and self.min_bp_delta < 0)
            or (self.rate_delta is not None and self.rate_delta > 0)
            or self.rank_changed
        )


@dataclass
class UserRecord:
    best_score_id: str | None
    best_clear_type: int | None
    best_exscore: int | None
    best_min_bp: int | None
    best_rate: float | None
    best_rank: str | None
    best_play_count: int | None
    best_options: dict | None
    best_client_type: str | None
    baseline: RecordSnapshot | None
    weekly_best: RecordSnapshot
    improvement: RecordImprovement
    improved: bool


_RANK_ORDER = {"F": 0, "E": 1, "D": 2, "C": 3, "B": 4, "A": 5, "AA": 6, "AAA": 7, "MAX": 8}


def _score_key(row) -> tuple:
    ts = _effective_ts(row) or datetime.min.replace(tzinfo=UTC)
    bp_score = -(row.min_bp if row.min_bp is not None else 999999)
    return (
        row.clear_type if row.clear_type is not None else -1,
        row.exscore if row.exscore is not None else -1,
        bp_score,
        row.rate if row.rate is not None else -1.0,
        ts,
    )


def _best_row(rows):
    if not rows:
        return None
    return max(rows, key=_score_key)


def _snapshot(row) -> RecordSnapshot:
    return RecordSnapshot(
        clear_type=row.clear_type,
        exscore=row.exscore,
        min_bp=getattr(row, "min_bp", None),
        rate=getattr(row, "rate", None),
        rank=getattr(row, "rank", None),
        effective_ts=_effective_ts(row),
    )


def _rank_value(rank: str | None) -> int:
    return _RANK_ORDER.get((rank or "").upper(), -1)


def _build_improvement(
    baseline: RecordSnapshot | None,
    weekly_best: RecordSnapshot,
) -> RecordImprovement:
    if baseline is None:
        return RecordImprovement(
            is_first_record=True,
            clear_type_changed=False,
            exscore_delta=None,
            min_bp_delta=None,
            rate_delta=None,
            rank_changed=False,
        )

    ex_delta = (
        weekly_best.exscore - baseline.exscore
        if weekly_best.exscore is not None and baseline.exscore is not None
        else None
    )
    bp_delta = (
        weekly_best.min_bp - baseline.min_bp
        if weekly_best.min_bp is not None and baseline.min_bp is not None
        else None
    )
    rate_delta = (
        weekly_best.rate - baseline.rate
        if weekly_best.rate is not None and baseline.rate is not None
        else None
    )
    return RecordImprovement(
        is_first_record=False,
        clear_type_changed=(
            weekly_best.clear_type is not None
            and baseline.clear_type is not None
            and weekly_best.clear_type > baseline.clear_type
        ),
        exscore_delta=ex_delta if ex_delta is not None and ex_delta > 0 else None,
        min_bp_delta=bp_delta if bp_delta is not None and bp_delta < 0 else None,
        rate_delta=rate_delta if rate_delta is not None and rate_delta > 0 else None,
        rank_changed=_rank_value(weekly_best.rank) > _rank_value(baseline.rank),
    )


def evaluate_user_records(
    rows_by_user: dict[str, list],
    start: datetime,
    end: datetime,
) -> dict[str, UserRecord]:
    """Compute display record + improvement flag for users who played in [start, end).

    Users with no in-window row are excluded.
    """
    out: dict[str, UserRecord] = {}
    for user_id, rows in rows_by_user.items():
        in_window = [r for r in rows if _effective_ts(r) is not None and start <= _effective_ts(r) < end]
        if not in_window:
            continue
        pre_window = [r for r in rows if _effective_ts(r) is not None and _effective_ts(r) < start]

        best_row = _best_row(rows)
        weekly_best_row = _best_row(in_window)
        if best_row is None or weekly_best_row is None:
            continue
        latest_pre_row = max(pre_window, key=_effective_ts) if pre_window else None
        baseline = _snapshot(latest_pre_row) if latest_pre_row is not None else None
        weekly_best = _snapshot(weekly_best_row)
        improvement = _build_improvement(baseline, weekly_best)

        out[user_id] = UserRecord(
            best_score_id=str(best_row.id) if getattr(best_row, "id", None) is not None else None,
            best_clear_type=best_row.clear_type,
            best_exscore=best_row.exscore,
            best_min_bp=getattr(best_row, "min_bp", None),
            best_rate=getattr(best_row, "rate", None),
            best_rank=getattr(best_row, "rank", None),
            best_play_count=getattr(best_row, "play_count", None),
            best_options=getattr(best_row, "options", None),
            best_client_type=getattr(best_row, "client_type", None),
            baseline=baseline,
            weekly_best=weekly_best,
            improvement=improvement,
            improved=improvement.has_changes,
        )
    return out


def _fumen_identity_conditions(
    fumen_sha256: str | None,
    fumen_md5: str | None,
    fumen_id: uuid.UUID | None,
):
    identity = []
    if fumen_id is not None:
        identity.append(UserScore.fumen_id == fumen_id)
    if fumen_sha256:
        identity.append(UserScore.fumen_sha256 == fumen_sha256)
    if fumen_md5:
        identity.append(and_(UserScore.fumen_md5 == fumen_md5, UserScore.fumen_sha256.is_(None)))
    return identity


async def fetch_fumen_candidate_user_ids(
    db: AsyncSession,
    fumen_sha256: str | None,
    fumen_md5: str | None,
    fumen_id: uuid.UUID | None,
    start: datetime,
    end: datetime,
    *,
    limit: int,
    offset: int,
) -> list[uuid.UUID]:
    """Fetch a leaderboard page of users who played this fumen in [start, end)."""
    identity = _fumen_identity_conditions(fumen_sha256, fumen_md5, fumen_id)
    if not identity:
        return []

    effective_ts = func.coalesce(UserScore.recorded_at, UserScore.synced_at)
    eligible_users = (
        select(UserScore.user_id)
        .where(
            UserScore.fumen_hash_others.is_(None),
            or_(*identity),
            effective_ts >= start,
            effective_ts < end,
        )
        .group_by(UserScore.user_id)
        .cte("eligible_weekly_users")
    )

    ranked_scores = (
        select(
            UserScore.user_id.label("user_id"),
            UserScore.clear_type.label("best_clear_type"),
            UserScore.exscore.label("best_exscore"),
            func.row_number()
            .over(
                partition_by=UserScore.user_id,
                order_by=(
                    UserScore.clear_type.desc().nullslast(),
                    UserScore.exscore.desc().nullslast(),
                ),
            )
            .label("rn"),
        )
        .join(eligible_users, eligible_users.c.user_id == UserScore.user_id)
        .where(UserScore.fumen_hash_others.is_(None), or_(*identity))
        .cte("ranked_scores")
    )

    query = (
        select(ranked_scores.c.user_id)
        .where(ranked_scores.c.rn == 1)
        .order_by(
            ranked_scores.c.best_clear_type.desc().nullslast(),
            ranked_scores.c.best_exscore.desc().nullslast(),
            ranked_scores.c.user_id,
        )
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    return [row.user_id for row in result.all()]


async def fetch_fumen_score_rows(
    db: AsyncSession,
    fumen_sha256: str | None,
    fumen_md5: str | None,
    fumen_id: uuid.UUID | None,
    *,
    only_user_id: uuid.UUID | None = None,
    user_ids: list[uuid.UUID] | None = None,
) -> dict[str, list]:
    """Fetch non-course score rows for a fumen, grouped by user_id (str)."""
    identity = _fumen_identity_conditions(fumen_sha256, fumen_md5, fumen_id)
    if not identity:
        return {}

    query = select(UserScore).where(
        UserScore.fumen_hash_others.is_(None),
        or_(*identity),
    )
    if only_user_id is not None:
        query = query.where(UserScore.user_id == only_user_id)
    if user_ids is not None:
        if not user_ids:
            return {}
        query = query.where(UserScore.user_id.in_(user_ids))

    result = await db.execute(query)
    grouped: dict[str, list] = {}
    for row in result.scalars().all():
        grouped.setdefault(str(row.user_id), []).append(row)
    return grouped
