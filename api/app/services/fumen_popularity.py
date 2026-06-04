"""Derived fumen play popularity maintenance."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.fumen import (
    Fumen,
    FumenPlayPopularity,
    FumenPopularityDirty,
    FumenPopularityWindow,
)
from app.models.score import UserPlayerStats, UserScore
from app.services.initial_sync import INITIAL_SYNC_WINDOW_HOURS
from app.services.player_stats_reliability import lr2_stats_unreliable_sql

_WINDOW_DAYS = {"weekly": 7, "monthly": 30}
_TOP_N = 50


def _dialect_name(db: AsyncSession) -> str:
    bind = db.get_bind()
    return bind.dialect.name if bind is not None else "postgresql"


async def mark_fumens_dirty(db: AsyncSession, fumen_ids: Iterable[uuid.UUID | None]) -> None:
    """Queue fumens for later popularity recompute."""
    ids = [fid for fid in set(fumen_ids) if fid is not None]
    if not ids:
        return
    if _dialect_name(db) == "postgresql":
        stmt = (
            pg_insert(FumenPopularityDirty)
            .values([{"fumen_id": fid} for fid in ids])
            .on_conflict_do_nothing(index_elements=[FumenPopularityDirty.fumen_id])
        )
        await db.execute(stmt)
        return

    await db.execute(
        sqlite_insert(FumenPopularityDirty)
        .values([{"fumen_id": fid} for fid in ids])
        .on_conflict_do_nothing(index_elements=[FumenPopularityDirty.fumen_id])
    )


def _resolved_score_rows() -> Any:
    """Return score rows with a canonical resolved_fumen_id."""
    f_sha = aliased(Fumen)
    f_md5 = aliased(Fumen)
    return (
        sa.select(
            sa.func.coalesce(UserScore.fumen_id, f_sha.fumen_id, f_md5.fumen_id).label("resolved_fumen_id"),
            UserScore.user_id.label("user_id"),
            UserScore.client_type.label("client_type"),
            UserScore.play_count.label("play_count"),
            UserScore.synced_at.label("synced_at"),
        )
        .select_from(UserScore)
        .outerjoin(
            f_sha,
            sa.and_(
                UserScore.fumen_id.is_(None),
                UserScore.fumen_sha256.isnot(None),
                UserScore.fumen_sha256 == f_sha.sha256,
            ),
        )
        .outerjoin(
            f_md5,
            sa.and_(
                UserScore.fumen_id.is_(None),
                f_sha.fumen_id.is_(None),
                UserScore.fumen_md5.isnot(None),
                UserScore.fumen_md5 == f_md5.md5,
            ),
        )
        .where(UserScore.fumen_hash_others.is_(None))
        .subquery("resolved_scores")
    )


def _utc_date_expr(value: Any, dialect_name: str) -> Any:
    if dialect_name == "sqlite":
        return sa.func.date(value)
    return sa.cast(sa.func.timezone("UTC", value), sa.Date)


def _reliable_window_score_rows(dialect_name: str) -> Any:
    """Return resolved score rows excluding dates with unreliable LR2 stats."""
    resolved = _resolved_score_rows()
    stats_day = _utc_date_expr(UserPlayerStats.synced_at, dialect_name)

    unreliable_days = (
        sa.select(
            UserPlayerStats.user_id.label("user_id"),
            UserPlayerStats.client_type.label("client_type"),
            stats_day.label("sync_day"),
        )
        .where(lr2_stats_unreliable_sql(UserPlayerStats))
        .group_by(UserPlayerStats.user_id, UserPlayerStats.client_type, stats_day)
        .subquery("unreliable_lr2_days")
    )
    reliable_lr2_days = (
        sa.select(
            UserPlayerStats.user_id.label("user_id"),
            UserPlayerStats.client_type.label("client_type"),
            stats_day.label("sync_day"),
        )
        .where(
            UserPlayerStats.client_type == "lr2",
            sa.not_(lr2_stats_unreliable_sql(UserPlayerStats)),
        )
        .group_by(UserPlayerStats.user_id, UserPlayerStats.client_type, stats_day)
        .subquery("reliable_lr2_days")
    )
    unreliable_only_days = (
        sa.select(
            unreliable_days.c.user_id,
            unreliable_days.c.client_type,
            unreliable_days.c.sync_day,
        )
        .outerjoin(
            reliable_lr2_days,
            sa.and_(
                reliable_lr2_days.c.user_id == unreliable_days.c.user_id,
                reliable_lr2_days.c.client_type == unreliable_days.c.client_type,
                reliable_lr2_days.c.sync_day == unreliable_days.c.sync_day,
            ),
        )
        .where(reliable_lr2_days.c.user_id.is_(None))
        .subquery("unreliable_only_lr2_days")
    )

    score_day = _utc_date_expr(resolved.c.synced_at, dialect_name)
    return (
        sa.select(resolved)
        .outerjoin(
            unreliable_only_days,
            sa.and_(
                unreliable_only_days.c.user_id == resolved.c.user_id,
                unreliable_only_days.c.client_type == resolved.c.client_type,
                unreliable_only_days.c.sync_day == score_day,
            ),
        )
        .where(unreliable_only_days.c.user_id.is_(None))
        .subquery("reliable_resolved_scores")
    )


async def _upsert_all_time_popularity(
    db: AsyncSession,
    values: list[dict[str, Any]],
) -> None:
    if not values:
        return
    if _dialect_name(db) == "postgresql":
        upsert = pg_insert(FumenPlayPopularity).values(values)
        await db.execute(
            upsert.on_conflict_do_update(
                index_elements=[FumenPlayPopularity.fumen_id],
                set_={
                    "played_user_count": upsert.excluded.played_user_count,
                    "total_play_count": upsert.excluded.total_play_count,
                    "updated_at": sa.func.now(),
                },
            )
        )
        return

    now = datetime.now(UTC)
    for value in values:
        existing = await db.get(FumenPlayPopularity, value["fumen_id"])
        if existing is None:
            db.add(FumenPlayPopularity(**value, updated_at=now))
        else:
            existing.played_user_count = value["played_user_count"]
            existing.total_play_count = value["total_play_count"]
            existing.updated_at = now
    await db.flush()


async def refresh_dirty_fumen_popularity(db: AsyncSession, batch_size: int = 5000) -> int:
    """Recompute popularity for one batch of dirty fumens. Returns processed count."""
    dirty_ids = (
        await db.execute(sa.select(FumenPopularityDirty.fumen_id).limit(batch_size))
    ).scalars().all()
    if not dirty_ids:
        return 0

    resolved = _resolved_score_rows()
    per_user = (
        sa.select(
            resolved.c.resolved_fumen_id.label("fumen_id"),
            resolved.c.user_id.label("user_id"),
            sa.func.max(sa.func.coalesce(resolved.c.play_count, 0)).label("user_plays"),
        )
        .where(resolved.c.resolved_fumen_id.in_(dirty_ids))
        .group_by(resolved.c.resolved_fumen_id, resolved.c.user_id)
        .subquery("per_user")
    )
    rows = (
        await db.execute(
            sa.select(
                per_user.c.fumen_id,
                sa.func.count().label("played_user_count"),
                sa.func.coalesce(sa.func.sum(per_user.c.user_plays), 0).label("total_play_count"),
            ).group_by(per_user.c.fumen_id)
        )
    ).all()
    agg = {r.fumen_id: (int(r.played_user_count), int(r.total_play_count or 0)) for r in rows}
    await _upsert_all_time_popularity(
        db,
        [
            {
                "fumen_id": fid,
                "played_user_count": agg.get(fid, (0, 0))[0],
                "total_play_count": agg.get(fid, (0, 0))[1],
            }
            for fid in dirty_ids
        ],
    )
    await db.execute(sa.delete(FumenPopularityDirty).where(FumenPopularityDirty.fumen_id.in_(dirty_ids)))
    return len(dirty_ids)


def _window_cutoff(window: str) -> datetime:
    try:
        days = _WINDOW_DAYS[window]
    except KeyError as exc:
        raise ValueError(f"Unsupported popularity window: {window}") from exc
    return datetime.now(UTC) - timedelta(days=days)


async def _upsert_window_rows(db: AsyncSession, values: list[dict[str, Any]]) -> None:
    if not values:
        return
    if _dialect_name(db) == "postgresql":
        upsert = pg_insert(FumenPopularityWindow).values(values)
        await db.execute(
            upsert.on_conflict_do_update(
                index_elements=[FumenPopularityWindow.window, FumenPopularityWindow.fumen_id],
                set_={
                    "played_user_count": upsert.excluded.played_user_count,
                    "play_count": upsert.excluded.play_count,
                    "computed_at": sa.func.now(),
                },
            )
        )
        return

    now = datetime.now(UTC)
    for value in values:
        existing = await db.get(FumenPopularityWindow, (value["window"], value["fumen_id"]))
        if existing is None:
            db.add(FumenPopularityWindow(**value, computed_at=now))
        else:
            existing.played_user_count = value["played_user_count"]
            existing.play_count = value["play_count"]
            existing.computed_at = now
    await db.flush()


async def rerank_popularity_window(db: AsyncSession, window: str) -> None:
    """Recompute ranks for cached rows in one window."""
    if _dialect_name(db) == "postgresql":
        await db.execute(
            sa.text(
                """
                WITH ranked AS (
                    SELECT window, fumen_id,
                           ROW_NUMBER() OVER (
                               ORDER BY played_user_count DESC, play_count DESC, fumen_id
                           ) AS new_rank
                    FROM fumen_popularity_window
                    WHERE window = :window
                )
                UPDATE fumen_popularity_window fpw
                   SET rank = ranked.new_rank,
                       computed_at = now()
                  FROM ranked
                 WHERE fpw.window = ranked.window
                   AND fpw.fumen_id = ranked.fumen_id
                """
            ),
            {"window": window},
        )
        return

    rows = (
        await db.execute(
            sa.select(FumenPopularityWindow)
            .where(FumenPopularityWindow.window == window)
            .order_by(
                FumenPopularityWindow.played_user_count.desc(),
                FumenPopularityWindow.play_count.desc(),
                FumenPopularityWindow.fumen_id,
            )
        )
    ).scalars().all()
    now = datetime.now(UTC)
    for index, row in enumerate(rows, start=1):
        row.rank = index
        row.computed_at = now
    await db.flush()


def _window_delta_aggregate(
    window: str,
    *,
    fumen_ids: list[uuid.UUID] | None = None,
    dialect_name: str = "postgresql",
) -> Any:
    """Build per-fumen play deltas for a moving popularity window."""
    cutoff = _window_cutoff(window)
    resolved = _reliable_window_score_rows(dialect_name)

    base_filter = [
        resolved.c.resolved_fumen_id.isnot(None),
        resolved.c.synced_at.isnot(None),
    ]
    if fumen_ids is not None:
        base_filter.append(resolved.c.resolved_fumen_id.in_(fumen_ids))

    latest_ranked = (
        sa.select(
            resolved.c.resolved_fumen_id.label("fumen_id"),
            resolved.c.user_id.label("user_id"),
            resolved.c.client_type.label("client_type"),
            sa.func.coalesce(resolved.c.play_count, 0).label("play_count"),
            sa.func.row_number()
            .over(
                partition_by=(resolved.c.resolved_fumen_id, resolved.c.user_id, resolved.c.client_type),
                order_by=(resolved.c.synced_at.desc(), sa.func.coalesce(resolved.c.play_count, 0).desc()),
            )
            .label("rn"),
        )
        .where(*base_filter, resolved.c.synced_at >= cutoff)
        .subquery("latest_ranked")
    )
    latest_in_window = (
        sa.select(
            latest_ranked.c.fumen_id,
            latest_ranked.c.user_id,
            latest_ranked.c.client_type,
            latest_ranked.c.play_count.label("latest_play_count"),
        )
        .where(latest_ranked.c.rn == 1)
        .subquery("latest_in_window")
    )

    before_ranked = (
        sa.select(
            resolved.c.resolved_fumen_id.label("fumen_id"),
            resolved.c.user_id.label("user_id"),
            resolved.c.client_type.label("client_type"),
            sa.func.coalesce(resolved.c.play_count, 0).label("play_count"),
            sa.func.row_number()
            .over(
                partition_by=(resolved.c.resolved_fumen_id, resolved.c.user_id, resolved.c.client_type),
                order_by=(resolved.c.synced_at.desc(), sa.func.coalesce(resolved.c.play_count, 0).desc()),
            )
            .label("rn"),
        )
        .where(*base_filter, resolved.c.synced_at < cutoff)
        .subquery("before_ranked")
    )
    baseline_before_window = (
        sa.select(
            before_ranked.c.fumen_id,
            before_ranked.c.user_id,
            before_ranked.c.client_type,
            before_ranked.c.play_count.label("baseline_play_count"),
        )
        .where(before_ranked.c.rn == 1)
        .subquery("baseline_before_window")
    )

    first_sync = (
        sa.select(
            resolved.c.user_id.label("user_id"),
            resolved.c.client_type.label("client_type"),
            sa.func.min(resolved.c.synced_at).label("first_synced_at"),
        )
        .where(resolved.c.synced_at.isnot(None))
        .group_by(resolved.c.user_id, resolved.c.client_type)
        .subquery("first_sync")
    )
    first_sync_cutoff = (
        sa.func.datetime(first_sync.c.first_synced_at, f"+{INITIAL_SYNC_WINDOW_HOURS} hours")
        if dialect_name == "sqlite"
        else first_sync.c.first_synced_at + sa.text(f"interval '{INITIAL_SYNC_WINDOW_HOURS} hours'")
    )
    first_sync_baseline = (
        sa.select(
            resolved.c.resolved_fumen_id.label("fumen_id"),
            resolved.c.user_id.label("user_id"),
            resolved.c.client_type.label("client_type"),
            sa.func.max(sa.func.coalesce(resolved.c.play_count, 0)).label("baseline_play_count"),
        )
        .join(
            first_sync,
            sa.and_(
                first_sync.c.user_id == resolved.c.user_id,
                first_sync.c.client_type == resolved.c.client_type,
            ),
        )
        .where(
            *base_filter,
            first_sync.c.first_synced_at >= cutoff,
            resolved.c.synced_at <= first_sync_cutoff,
        )
        .group_by(resolved.c.resolved_fumen_id, resolved.c.user_id, resolved.c.client_type)
        .subquery("first_sync_baseline")
    )

    baseline_play_count = sa.func.coalesce(
        baseline_before_window.c.baseline_play_count,
        first_sync_baseline.c.baseline_play_count,
        0,
    )
    raw_delta = latest_in_window.c.latest_play_count - baseline_play_count
    per_client_delta = (
        sa.select(
            latest_in_window.c.fumen_id,
            latest_in_window.c.user_id,
            latest_in_window.c.client_type,
            sa.case((raw_delta > 0, raw_delta), else_=0).label("play_delta"),
        )
        .select_from(latest_in_window)
        .outerjoin(
            baseline_before_window,
            sa.and_(
                baseline_before_window.c.fumen_id == latest_in_window.c.fumen_id,
                baseline_before_window.c.user_id == latest_in_window.c.user_id,
                baseline_before_window.c.client_type == latest_in_window.c.client_type,
            ),
        )
        .outerjoin(
            first_sync_baseline,
            sa.and_(
                first_sync_baseline.c.fumen_id == latest_in_window.c.fumen_id,
                first_sync_baseline.c.user_id == latest_in_window.c.user_id,
                first_sync_baseline.c.client_type == latest_in_window.c.client_type,
            ),
        )
        .subquery("per_client_delta")
    )
    per_user_delta = (
        sa.select(
            per_client_delta.c.fumen_id,
            per_client_delta.c.user_id,
            sa.func.sum(per_client_delta.c.play_delta).label("play_delta"),
        )
        .where(per_client_delta.c.play_delta > 0)
        .group_by(per_client_delta.c.fumen_id, per_client_delta.c.user_id)
        .subquery("per_user_delta")
    )

    return (
        sa.select(
            per_user_delta.c.fumen_id,
            sa.func.count().label("played_user_count"),
            sa.func.coalesce(sa.func.sum(per_user_delta.c.play_delta), 0).label("play_count"),
        )
        .where(per_user_delta.c.play_delta > 0)
        .group_by(per_user_delta.c.fumen_id)
    )


async def refresh_popularity_window_for_fumens(
    db: AsyncSession,
    window: str,
    fumen_ids: Iterable[uuid.UUID | None],
) -> int:
    """Recompute one popularity window for touched fumens from a completed sync."""
    ids = [fid for fid in set(fumen_ids) if fid is not None]
    if not ids:
        return 0
    rows = (await db.execute(_window_delta_aggregate(window, fumen_ids=ids, dialect_name=_dialect_name(db)))).all()
    row_ids = {r.fumen_id for r in rows}
    aged_out_ids = [fid for fid in ids if fid not in row_ids]
    if aged_out_ids:
        await db.execute(
            sa.delete(FumenPopularityWindow).where(
                FumenPopularityWindow.window == window,
                FumenPopularityWindow.fumen_id.in_(aged_out_ids),
            )
        )
    await _upsert_window_rows(
        db,
        [
            {
                "window": window,
                "fumen_id": r.fumen_id,
                "rank": 0,
                "played_user_count": int(r.played_user_count),
                "play_count": int(r.play_count or 0),
            }
            for r in rows
        ],
    )
    await rerank_popularity_window(db, window)
    return len(ids)


async def rebuild_popularity_window(db: AsyncSession, window: str) -> int:
    """Full daily rebuild for one moving weekly/monthly window."""
    rows = (
        await db.execute(
            _window_delta_aggregate(window, dialect_name=_dialect_name(db))
            .order_by(sa.desc("played_user_count"), sa.desc("play_count"), sa.column("fumen_id"))
            .limit(_TOP_N)
        )
    ).all()
    await db.execute(sa.delete(FumenPopularityWindow).where(FumenPopularityWindow.window == window))
    if rows:
        db.add_all(
            FumenPopularityWindow(
                window=window,
                fumen_id=r.fumen_id,
                rank=index,
                played_user_count=int(r.played_user_count),
                play_count=int(r.play_count or 0),
            )
            for index, r in enumerate(rows, start=1)
        )
    await db.flush()
    return len(rows)
