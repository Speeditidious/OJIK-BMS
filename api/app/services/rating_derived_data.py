"""Build and query sparse derived data for rating overview screens."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ranking import (
    UserRanking,
    UserRatingDerivedState,
    UserRatingUpdateDaily,
    UserTableRatingCheckpoint,
    UserTableRatingUpdateDaily,
    UserTableRatingUpdateKey,
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
    _query_table_score_history,
    _rating_update_countable_top_keys,
    _top_keys_from_values,
)

_INSERT_CHUNK_SIZE = 1000
RATING_DERIVED_SCHEMA_VERSION = 1


def _ranking_config_fingerprint(config: RankingConfig) -> str:
    """Return a stable fingerprint for rating-derived calculation inputs."""
    payload = {
        "exp_level_step": config.exp_level_step,
        "tables": [
            {
                "slug": table.slug,
                "table_id": str(table.table_id),
                "top_n": table.top_n,
                "max_level": table.max_level,
                "level_weights": table.level_weights,
                "base_lamp_mult": table.base_lamp_mult,
                "upper_lamp_bonus": table.upper_lamp_bonus,
                "rank_mult": table.rank_mult,
                "bonus": getattr(table.bonus, "__dict__", str(table.bonus)),
                "level_overrides": [getattr(override, "__dict__", str(override)) for override in table.level_overrides],
                "c_table": table.c_table,
            }
            for table in config.tables
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _requires_full_rating_derived_rebuild(
    state: UserRatingDerivedState | Any | None,
    *,
    schema_version: int,
    config_fingerprint: str,
) -> bool:
    """Return whether stored rating-derived rows cannot be incrementally trusted."""
    if state is None:
        return True
    return (
        getattr(state, "schema_version", None) != schema_version
        or getattr(state, "config_fingerprint", None) != config_fingerprint
    )


async def select_user_rating_derived_rebuild_scope(
    user_id: uuid.UUID,
    config: RankingConfig,
    db: AsyncSession,
) -> tuple[set[uuid.UUID] | None, date | None]:
    """Return affected table IDs and earliest effective date, or ``None`` for full rebuild."""
    config_fingerprint = _ranking_config_fingerprint(config)
    state_rows = await db.execute(
        select(UserRatingDerivedState).where(UserRatingDerivedState.user_id == user_id)
    )
    states_by_table = {row.table_id: row for row in state_rows.scalars().all()}
    if len(states_by_table) != len(config.tables):
        return None, None
    for table_cfg in config.tables:
        if _requires_full_rating_derived_rebuild(
            states_by_table.get(table_cfg.table_id),
            schema_version=RATING_DERIVED_SCHEMA_VERSION,
            config_fingerprint=config_fingerprint,
        ):
            return None, None

    affected_table_ids: set[uuid.UUID] = set()
    earliest: date | None = None
    for table_cfg in config.tables:
        state = states_by_table[table_cfg.table_id]
        result = await db.execute(
            text("""
                SELECT MIN(COALESCE(us.recorded_at, us.synced_at)::date) AS start_date
                FROM user_scores us
                JOIN fumen_table_entries fte ON fte.fumen_id = us.fumen_id
                WHERE us.user_id = :user_id
                  AND us.fumen_hash_others IS NULL
                  AND fte.table_id = :table_id
                  AND us.synced_at > :rebuilt_at
            """),
            {
                "user_id": str(user_id),
                "table_id": str(table_cfg.table_id),
                "rebuilt_at": state.rebuilt_at,
            },
        )
        table_start = result.scalar_one_or_none()
        if table_start is None:
            continue
        affected_table_ids.add(table_cfg.table_id)
        if earliest is None or table_start < earliest:
            earliest = table_start

    return affected_table_ids, earliest


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
        updated_top_keys = _rating_update_countable_top_keys(
            previous_values_snapshot,
            current_values,
            previous_top_keys,
            current_top_keys,
        )

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
    *,
    affected_table_ids: set[uuid.UUID] | None = None,
    start_date: date | None = None,
) -> None:
    """Rebuild sparse rating-derived tables for one user.

    When ``affected_table_ids`` and ``start_date`` are provided, only those
    table-scoped rows from ``start_date`` onward are replaced. Aggregated daily
    rows are then rebuilt from stored per-table fumen keys for the same date
    range, preserving cross-table dedupe.
    """
    user = await db.get(User, user_id)
    excluded_dates = _rating_update_excluded_dates(user.first_synced_at if user is not None else None)
    config_fingerprint = _ranking_config_fingerprint(config)

    state_rows = await db.execute(
        select(UserRatingDerivedState).where(UserRatingDerivedState.user_id == user_id)
    )
    states_by_table = {row.table_id: row for row in state_rows.scalars().all()}
    requested_partial = affected_table_ids is not None and start_date is not None
    if requested_partial:
        for table_cfg in config.tables:
            state = states_by_table.get(table_cfg.table_id)
            if _requires_full_rating_derived_rebuild(
                state,
                schema_version=RATING_DERIVED_SCHEMA_VERSION,
                config_fingerprint=config_fingerprint,
            ):
                requested_partial = False
                break

    target_tables = [
        table_cfg for table_cfg in config.tables
        if not requested_partial or table_cfg.table_id in (affected_table_ids or set())
    ]

    checkpoint_rows: list[dict[str, Any]] = []
    table_daily_rows: list[dict[str, Any]] = []
    table_key_rows: list[dict[str, Any]] = []
    aggregated_sets: dict[date, set[tuple[str | None, str | None]]] = defaultdict(set)

    for table_cfg in target_tables:
        table_checkpoints, table_daily, updated_keys_by_date = await _build_user_table_rating_derived_rows(
            user_id=user_id,
            table_cfg=table_cfg,
            db=db,
            excluded_dates=excluded_dates,
        )
        if requested_partial and start_date is not None:
            table_checkpoints = [
                row for row in table_checkpoints
                if row["effective_date"] >= start_date
            ]
            table_daily = [
                row for row in table_daily
                if row["effective_date"] >= start_date
            ]
            updated_keys_by_date = {
                effective_date: keys
                for effective_date, keys in updated_keys_by_date.items()
                if effective_date >= start_date
            }
        checkpoint_rows.extend(table_checkpoints)
        table_daily_rows.extend(table_daily)
        for effective_date, keys in updated_keys_by_date.items():
            aggregated_sets[effective_date].update(keys)
            for sha256, md5 in keys:
                table_key_rows.append(
                    {
                        "user_id": user_id,
                        "table_id": table_cfg.table_id,
                        "effective_date": effective_date,
                        "fumen_sha256": sha256 or "",
                        "fumen_md5": md5 or "",
                    }
                )

    aggregated_daily_rows = [
        {
            "user_id": user_id,
            "effective_date": effective_date,
            "update_count": len(keys),
        }
        for effective_date, keys in sorted(aggregated_sets.items())
        if keys
    ]

    if requested_partial and start_date is not None and affected_table_ids:
        await db.execute(
            delete(UserTableRatingCheckpoint).where(
                UserTableRatingCheckpoint.user_id == user_id,
                UserTableRatingCheckpoint.table_id.in_(affected_table_ids),
                UserTableRatingCheckpoint.effective_date >= start_date,
            )
        )
        await db.execute(
            delete(UserTableRatingUpdateDaily).where(
                UserTableRatingUpdateDaily.user_id == user_id,
                UserTableRatingUpdateDaily.table_id.in_(affected_table_ids),
                UserTableRatingUpdateDaily.effective_date >= start_date,
            )
        )
        await db.execute(
            delete(UserTableRatingUpdateKey).where(
                UserTableRatingUpdateKey.user_id == user_id,
                UserTableRatingUpdateKey.table_id.in_(affected_table_ids),
                UserTableRatingUpdateKey.effective_date >= start_date,
            )
        )
        await db.execute(
            delete(UserRatingUpdateDaily).where(
                UserRatingUpdateDaily.user_id == user_id,
                UserRatingUpdateDaily.effective_date >= start_date,
            )
        )
    else:
        await db.execute(delete(UserTableRatingCheckpoint).where(UserTableRatingCheckpoint.user_id == user_id))
        await db.execute(delete(UserTableRatingUpdateDaily).where(UserTableRatingUpdateDaily.user_id == user_id))
        await db.execute(delete(UserTableRatingUpdateKey).where(UserTableRatingUpdateKey.user_id == user_id))
        await db.execute(delete(UserRatingUpdateDaily).where(UserRatingUpdateDaily.user_id == user_id))
        await db.execute(delete(UserRatingDerivedState).where(UserRatingDerivedState.user_id == user_id))

    await _insert_chunked(db, UserTableRatingCheckpoint.__table__, checkpoint_rows)
    await _insert_chunked(db, UserTableRatingUpdateDaily.__table__, table_daily_rows)
    await _insert_chunked(db, UserTableRatingUpdateKey.__table__, table_key_rows)

    if requested_partial and start_date is not None:
        await db.execute(
            text("""
                INSERT INTO user_rating_update_daily (user_id, effective_date, update_count)
                SELECT user_id, effective_date, COUNT(DISTINCT (fumen_sha256, fumen_md5))::smallint
                FROM user_table_rating_update_keys
                WHERE user_id = :user_id
                  AND effective_date >= :start_date
                GROUP BY user_id, effective_date
            """),
            {"user_id": str(user_id), "start_date": start_date},
        )
    else:
        await _insert_chunked(db, UserRatingUpdateDaily.__table__, aggregated_daily_rows)

    state_rows_to_upsert = [
        {
            "user_id": user_id,
            "table_id": table_cfg.table_id,
            "schema_version": RATING_DERIVED_SCHEMA_VERSION,
            "config_fingerprint": config_fingerprint,
            "last_rebuilt_effective_date": date.max,
            "rebuilt_at": datetime.now(UTC),
        }
        for table_cfg in target_tables
    ]
    if state_rows_to_upsert:
        stmt = insert(UserRatingDerivedState).values(state_rows_to_upsert)
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["user_id", "table_id"],
                set_={
                    "schema_version": stmt.excluded.schema_version,
                    "config_fingerprint": stmt.excluded.config_fingerprint,
                    "last_rebuilt_effective_date": stmt.excluded.last_rebuilt_effective_date,
                    "rebuilt_at": stmt.excluded.rebuilt_at,
                },
            )
        )


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
