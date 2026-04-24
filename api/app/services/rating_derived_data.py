"""Build and query sparse derived data for rating overview screens."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ranking import (
    UserRanking,
    UserRatingUpdateDaily,
    UserTableRatingCheckpoint,
    UserTableRatingUpdateDaily,
)
from app.models.score import UserScore
from app.models.user import User
from app.services.ranking_calculator import (
    RankingHistoryPoint,
    _exp_level,
    standardize_rating,
)
from app.services.ranking_config import RankingConfig, TableRankingConfig
from app.services.ranking_dashboard import (
    _apply_history_row,
    _canonical_key,
    _canonical_key_maps,
    _display_top_n_contribution_value,
    _query_table_score_history,
    _top_keys_from_values,
)

_INSERT_CHUNK_SIZE = 1000


def _rating_update_excluded_dates(first_synced_at: dict[str, str] | None) -> set[date]:
    """Return first-sync dates excluded from rating-update count materialization."""
    first_synced = first_synced_at or {}
    excluded_dates: set[date] = set()
    for client_type in ("lr2", "beatoraja"):
        ts_str = first_synced.get(client_type)
        if not ts_str:
            continue
        excluded_dates.add(datetime.fromisoformat(ts_str).date())
    return excluded_dates


def _is_stale(max_synced_at: datetime | None, calculated_at: datetime | None) -> bool:
    """Return whether derived data should be considered stale."""
    if max_synced_at is None:
        return False
    if calculated_at is None:
        return True
    return calculated_at < max_synced_at


async def _insert_chunked(
    db: AsyncSession,
    table,
    rows: list[dict[str, Any]],
) -> None:
    """Bulk insert rows in small chunks to limit memory pressure."""
    for start in range(0, len(rows), _INSERT_CHUNK_SIZE):
        await db.execute(table.insert(), rows[start : start + _INSERT_CHUNK_SIZE])


async def _build_user_table_rating_derived_rows(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    db: AsyncSession,
    excluded_dates: set[date],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[date, set[tuple[str | None, str | None]]]]:
    """Build sparse checkpoints and daily update counts for one ranking table."""
    targets, history_rows = await _query_table_score_history(
        user_id=user_id,
        table_cfg=table_cfg,
        db=db,
        until_date=date.max,
        include_metadata=False,
    )
    if not history_rows:
        return ([], [], {})

    sha256_to_md5, md5_to_sha256 = _canonical_key_maps(targets)
    targets_by_key = {
        _canonical_key(target["sha256"], target["md5"], sha256_to_md5, md5_to_sha256): target
        for target in targets
    }

    best_scores = {}
    current_values: dict[tuple[str | None, str | None], float] = {}
    current_exp = 0.0
    previous_exp = 0.0
    previous_rating = 0.0
    checkpoints: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    updated_keys_by_date: dict[date, set[tuple[str | None, str | None]]] = {}

    row_index = 0
    while row_index < len(history_rows):
        row = history_rows[row_index]
        effective_ts = row["effective_ts"]
        if effective_ts is None:
            row_index += 1
            continue

        effective_date = effective_ts.date()
        previous_values_snapshot = dict(current_values)
        previous_top_keys = _top_keys_from_values(
            previous_values_snapshot,
            targets_by_key,
            table_cfg.top_n,
        )

        while row_index < len(history_rows):
            row = history_rows[row_index]
            current_ts = row["effective_ts"]
            if current_ts is None or current_ts.date() != effective_date:
                break

            canonical_key = _canonical_key(
                row["fumen_sha256"],
                row["fumen_md5"],
                sha256_to_md5,
                md5_to_sha256,
            )
            previous_value = current_values.get(canonical_key, 0.0)
            canonical, changed = _apply_history_row(
                row,
                targets_by_key,
                sha256_to_md5,
                md5_to_sha256,
                best_scores,
                current_values,
                table_cfg,
            )
            if changed and canonical is not None:
                current_exp += current_values.get(canonical, 0.0) - previous_value
            row_index += 1

        current_top_keys = _top_keys_from_values(current_values, targets_by_key, table_cfg.top_n)
        current_rating = sum(current_values.get(key, 0.0) for key in current_top_keys)
        updated_top_keys = {
            key
            for key in (previous_top_keys | current_top_keys)
            if _display_top_n_contribution_value(
                previous_values_snapshot.get(key, 0.0),
                key in previous_top_keys,
            )
            != _display_top_n_contribution_value(
                current_values.get(key, 0.0),
                key in current_top_keys,
            )
        }

        if abs(current_exp - previous_exp) > 1e-9 or abs(current_rating - previous_rating) > 1e-9:
            checkpoints.append(
                {
                    "user_id": user_id,
                    "table_id": table_cfg.table_id,
                    "effective_date": effective_date,
                    "exp": current_exp,
                    "rating": current_rating,
                }
            )
            previous_exp = current_exp
            previous_rating = current_rating

        if effective_date not in excluded_dates and updated_top_keys:
            daily_rows.append(
                {
                    "user_id": user_id,
                    "table_id": table_cfg.table_id,
                    "effective_date": effective_date,
                    "update_count": len(updated_top_keys),
                }
            )
            updated_keys_by_date[effective_date] = set(updated_top_keys)

    return checkpoints, daily_rows, updated_keys_by_date


async def rebuild_user_rating_derived_data(
    user_id: uuid.UUID,
    config: RankingConfig,
    db: AsyncSession,
) -> None:
    """Rebuild every sparse rating-derived table for one user."""
    user = await db.get(User, user_id)
    excluded_dates = _rating_update_excluded_dates(user.first_synced_at if user is not None else None)

    checkpoint_rows: list[dict[str, Any]] = []
    table_daily_rows: list[dict[str, Any]] = []
    aggregated_sets: dict[date, set[tuple[str | None, str | None]]] = defaultdict(set)

    for table_cfg in config.tables:
        table_checkpoints, table_daily, updated_keys_by_date = await _build_user_table_rating_derived_rows(
            user_id=user_id,
            table_cfg=table_cfg,
            db=db,
            excluded_dates=excluded_dates,
        )
        checkpoint_rows.extend(table_checkpoints)
        table_daily_rows.extend(table_daily)
        for effective_date, keys in updated_keys_by_date.items():
            aggregated_sets[effective_date].update(keys)

    aggregated_daily_rows = [
        {
            "user_id": user_id,
            "effective_date": effective_date,
            "update_count": len(keys),
        }
        for effective_date, keys in sorted(aggregated_sets.items())
        if keys
    ]

    await db.execute(delete(UserTableRatingCheckpoint).where(UserTableRatingCheckpoint.user_id == user_id))
    await db.execute(delete(UserTableRatingUpdateDaily).where(UserTableRatingUpdateDaily.user_id == user_id))
    await db.execute(delete(UserRatingUpdateDaily).where(UserRatingUpdateDaily.user_id == user_id))

    await _insert_chunked(db, UserTableRatingCheckpoint.__table__, checkpoint_rows)
    await _insert_chunked(db, UserTableRatingUpdateDaily.__table__, table_daily_rows)
    await _insert_chunked(db, UserRatingUpdateDaily.__table__, aggregated_daily_rows)


async def has_fresh_user_table_rating_derived_data(
    user_id: uuid.UUID,
    table_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """Return whether table-scoped derived data is fresh enough to serve."""
    synced_row = await db.execute(
        select(func.max(UserScore.synced_at)).where(UserScore.user_id == user_id)
    )
    max_synced_at = synced_row.scalar_one_or_none()
    ranking_row = await db.execute(
        select(UserRanking.calculated_at).where(
            UserRanking.user_id == user_id,
            UserRanking.table_id == table_id,
        )
    )
    calculated_at = ranking_row.scalar_one_or_none()
    if _is_stale(max_synced_at, calculated_at):
        return False
    derived_exists = await db.execute(
        select(UserTableRatingCheckpoint.effective_date).where(
            UserTableRatingCheckpoint.user_id == user_id,
            UserTableRatingCheckpoint.table_id == table_id,
        ).limit(1)
    )
    return derived_exists.scalar_one_or_none() is not None


async def has_fresh_user_rating_derived_data(
    user_id: uuid.UUID,
    table_ids: list[uuid.UUID],
    db: AsyncSession,
) -> bool:
    """Return whether user-wide derived data is fresh across ranking tables."""
    synced_row = await db.execute(
        select(func.max(UserScore.synced_at)).where(UserScore.user_id == user_id)
    )
    max_synced_at = synced_row.scalar_one_or_none()
    if max_synced_at is None:
        return True

    ranking_rows = await db.execute(
        select(UserRanking.table_id, UserRanking.calculated_at).where(
            UserRanking.user_id == user_id,
            UserRanking.table_id.in_(table_ids),
        )
    )
    ranking_map = {row.table_id: row.calculated_at for row in ranking_rows.all()}
    if len(ranking_map) != len(table_ids):
        return False
    if not all(not _is_stale(max_synced_at, calculated_at) for calculated_at in ranking_map.values()):
        return False
    derived_exists = await db.execute(
        select(UserTableRatingCheckpoint.effective_date).where(
            UserTableRatingCheckpoint.user_id == user_id,
            UserTableRatingCheckpoint.table_id.in_(table_ids),
        ).limit(1)
    )
    return derived_exists.scalar_one_or_none() is not None


async def fetch_user_table_rating_history_points(
    user_id: uuid.UUID,
    table_id: uuid.UUID,
    from_date: date,
    to_date: date,
    exp_level_step: float,
    max_level: int,
    db: AsyncSession,
) -> list[RankingHistoryPoint]:
    """Return day-by-day history points by forward-filling sparse checkpoints."""
    anchor_result = await db.execute(
        select(UserTableRatingCheckpoint).where(
            UserTableRatingCheckpoint.user_id == user_id,
            UserTableRatingCheckpoint.table_id == table_id,
            UserTableRatingCheckpoint.effective_date < from_date,
        ).order_by(UserTableRatingCheckpoint.effective_date.desc()).limit(1)
    )
    anchor = anchor_result.scalar_one_or_none()

    rows_result = await db.execute(
        select(UserTableRatingCheckpoint).where(
            UserTableRatingCheckpoint.user_id == user_id,
            UserTableRatingCheckpoint.table_id == table_id,
            UserTableRatingCheckpoint.effective_date >= from_date,
            UserTableRatingCheckpoint.effective_date <= to_date,
        ).order_by(UserTableRatingCheckpoint.effective_date.asc())
    )
    checkpoints = list(rows_result.scalars().all())

    current_exp = float(anchor.exp) if anchor is not None else 0.0
    current_rating = float(anchor.rating) if anchor is not None else 0.0
    points: list[RankingHistoryPoint] = []
    checkpoint_index = 0
    current_date = from_date
    while current_date <= to_date:
        if checkpoint_index < len(checkpoints) and checkpoints[checkpoint_index].effective_date == current_date:
            current_exp = float(checkpoints[checkpoint_index].exp)
            current_rating = float(checkpoints[checkpoint_index].rating)
            checkpoint_index += 1
        exp_level = _exp_level(current_exp, exp_level_step, max_level)
        points.append(
            RankingHistoryPoint(
                date=current_date,
                exp=current_exp,
                exp_level=exp_level,
                rating=current_rating,
                rating_norm=standardize_rating(current_rating, exp_level),
            )
        )
        current_date += timedelta(days=1)
    return points


async def fetch_user_rating_update_daily(
    user_id: uuid.UUID,
    from_date: date,
    to_date: date,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Return aggregated rating-update counts for a date range."""
    result = await db.execute(
        select(UserRatingUpdateDaily).where(
            UserRatingUpdateDaily.user_id == user_id,
            UserRatingUpdateDaily.effective_date >= from_date,
            UserRatingUpdateDaily.effective_date <= to_date,
        ).order_by(UserRatingUpdateDaily.effective_date.asc())
    )
    return [
        {
            "date": row.effective_date.isoformat(),
            "count": int(row.update_count),
        }
        for row in result.scalars().all()
    ]


async def fetch_user_table_rating_update_daily(
    user_id: uuid.UUID,
    table_id: uuid.UUID,
    from_date: date,
    to_date: date,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Return per-table rating-update counts for a date range."""
    result = await db.execute(
        select(UserTableRatingUpdateDaily).where(
            UserTableRatingUpdateDaily.user_id == user_id,
            UserTableRatingUpdateDaily.table_id == table_id,
            UserTableRatingUpdateDaily.effective_date >= from_date,
            UserTableRatingUpdateDaily.effective_date <= to_date,
        ).order_by(UserTableRatingUpdateDaily.effective_date.asc())
    )
    return [
        {
            "date": row.effective_date.isoformat(),
            "count": int(row.update_count),
        }
        for row in result.scalars().all()
    ]


async def fetch_user_rating_update_count_for_date(
    user_id: uuid.UUID,
    target_date: date,
    db: AsyncSession,
) -> int:
    """Return aggregated rating-update count for one date."""
    result = await db.execute(
        select(UserRatingUpdateDaily.update_count).where(
            UserRatingUpdateDaily.user_id == user_id,
            UserRatingUpdateDaily.effective_date == target_date,
        )
    )
    return int(result.scalar_one_or_none() or 0)


async def fetch_user_rating_update_tables_for_date(
    user_id: uuid.UUID,
    target_date: date,
    ranking_tables: list[TableRankingConfig],
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Return per-table update counts for one date."""
    result = await db.execute(
        select(
            UserTableRatingUpdateDaily.table_id,
            UserTableRatingUpdateDaily.update_count,
        ).where(
            UserTableRatingUpdateDaily.user_id == user_id,
            UserTableRatingUpdateDaily.effective_date == target_date,
        )
    )
    table_meta = {
        table.table_id: {
            "table_slug": table.slug,
            "display_name": table.display_name,
            "display_order": table.display_order,
        }
        for table in ranking_tables
    }
    rows = []
    for table_id, update_count in result.all():
        meta = table_meta.get(table_id)
        if meta is None:
            continue
        rows.append(
            {
                **meta,
                "count": int(update_count),
            }
        )
    rows.sort(key=lambda row: row["display_order"])
    return rows
