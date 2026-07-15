"""Ranking dashboard helpers for contribution tables and rating update timelines."""
from __future__ import annotations

import heapq
import inspect
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from functools import cmp_to_key
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.score import UserScore
from app.services.clear_type_display import display_clear_type
from app.services.client_aggregation import PerClientBest, aggregate_source_client
from app.services.initial_sync import INITIAL_SYNC_SQL_INTERVAL
from app.services.ranking_calculator import (
    BestScore,
    _lamp_name,
    _merge_best_score_fields,
    _resolve_level,
    _song_rating,
    bulk_query_best_scores,
    compute_ranking,
    standardize_rating,
)
from app.services.ranking_config import TableRankingConfig
from app.utils.score_rank import max_minus_score
from app.utils.text_normalization import loose_text_matches

RANK_GRADE_ORDER = {
    "F": 0,
    "E": 1,
    "D": 2,
    "C": 3,
    "B": 4,
    "A": 5,
    "AA": 6,
    "AAA": 7,
    "MAX-": 8,
    "MAX": 9,
}


def _matches_contribution_query(row: dict[str, Any], query: str | None) -> bool:
    """Return whether a contribution row matches a loose title/artist query."""
    if not query:
        return True
    return loose_text_matches(row.get("title"), query) or loose_text_matches(row.get("artist"), query)


def compute_exp_progress_fields(
    exp: float,
    exp_level: int,
    exp_level_step: float,
    max_level: int,
) -> dict[str, float | bool]:
    """Return server-owned EXP progress metrics for the next level bar."""
    if exp_level >= max_level:
        return {
            "exp_to_next_level": 0.0,
            "exp_level_current_span": 1.0,
            "exp_level_progress_ratio": 1.0,
            "is_max_level": True,
        }

    current_floor = exp_level_step * exp_level * (exp_level + 1)
    next_threshold = exp_level_step * (exp_level + 1) * (exp_level + 2)
    current_span = max(next_threshold - current_floor, 1.0)
    progress = min(max((exp - current_floor) / current_span, 0.0), 1.0)
    return {
        "exp_to_next_level": max(next_threshold - exp, 0.0),
        "exp_level_current_span": current_span,
        "exp_level_progress_ratio": progress,
        "is_max_level": False,
    }


def _char_sort_group(ch: str) -> int:
    """Return the BMS title sort group for the first character."""
    code = ord(ch)
    if 0x21 <= code <= 0x7E:
        if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            return 1
        return 0
    if 0x3040 <= code <= 0x309F:
        return 3
    if 0x30A0 <= code <= 0x30FF:
        return 4
    if (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF):
        return 5
    return 2


def title_sort_key(title: str | None) -> tuple[int, str]:
    """Return a stable title sort key following the documented BMS convention."""
    normalized = (title or "").strip()
    if not normalized:
        return (6, "")
    return (_char_sort_group(normalized[0]), normalized.casefold())


async def get_user_ranking_version(
    user_id: uuid.UUID,
    table_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[str | None, str | None]:
    """Return `(max_synced_at, calculated_at)` strings used for cache keys."""
    ranking_row = await db.execute(
        text("""
            SELECT calculated_at
            FROM user_rankings
            WHERE user_id = :user_id AND table_id = :table_id
        """),
        {"user_id": str(user_id), "table_id": str(table_id)},
    )
    calculated_at = ranking_row.scalar_one_or_none()

    synced_row = await db.execute(
        select(func.max(UserScore.synced_at)).where(UserScore.user_id == user_id)
    )
    max_synced_at = synced_row.scalar_one_or_none()

    return (
        max_synced_at.isoformat() if max_synced_at else None,
        calculated_at.isoformat() if calculated_at else None,
    )


async def query_target_fumen_details(
    table_id: uuid.UUID,
    db: AsyncSession,
    include_metadata: bool = True,
) -> list[dict[str, Any]]:
    """Return target fumen metadata for one ranking-enabled table."""
    title_select = "f.title," if include_metadata else "NULL::text AS title,"
    artist_select = "f.artist," if include_metadata else "NULL::text AS artist,"
    result = await db.execute(
        text(f"""
            SELECT
                f.fumen_id,
                f.sha256,
                f.md5,
                {title_select}
                {artist_select}
                f.notes_total,
                fte.level AS level
            FROM fumen_table_entries fte
            JOIN fumens f ON f.fumen_id = fte.fumen_id
            WHERE fte.table_id = :table_id
        """),
        {"table_id": str(table_id)},
    )
    return [dict(row) for row in result.mappings().all()]


def _contribution_value(
    score: BestScore | None,
    target_level: str,
    table_cfg: TableRankingConfig,
    sha256: str | None,
    md5: str | None,
) -> tuple[float, str]:
    """Return `(raw_value, resolved_level)` for one chart."""
    if score is None:
        return 0.0, target_level

    lamp = _lamp_name(score.clear_type)
    resolved_level = _resolve_level(sha256, md5, lamp, target_level, table_cfg)
    rate_01 = (score.rate / 100.0) if score.rate is not None else None
    value = _song_rating(
        resolved_level,
        lamp,
        score.rank or "F",
        float(score.min_bp) if score.min_bp is not None else None,
        rate_01,
        table_cfg,
    )
    return value, resolved_level


def _max_minus_for_score(score: BestScore | None, target: dict[str, Any]) -> int | None:
    if score is None or score.rank != "MAX-":
        return None
    return max_minus_score(score.exscore, target.get("notes_total"))


def _display_whole_metric_value(value: float | None) -> int:
    """Return the integer-rounded value shown in the UI for EXP/rating."""
    return int(round(value or 0.0))


def _display_whole_metric_delta(previous_value: float | None, current_value: float | None) -> int:
    """Return the displayed EXP/rating delta using UI rounding semantics."""
    return _display_whole_metric_value(current_value) - _display_whole_metric_value(previous_value)


def _raw_top_n_contribution_value(value: float | None, is_in_top_n: bool) -> float:
    """Return the raw Top-N contribution value for update/card detection."""
    if not is_in_top_n:
        return 0.0
    return float(value or 0.0)


def _rating_update_countable_top_keys(
    previous_values: dict[tuple[str | None, str | None], float],
    current_values: dict[tuple[str | None, str | None], float],
    previous_top_keys: set[tuple[str | None, str | None]],
    current_top_keys: set[tuple[str | None, str | None]],
) -> set[tuple[str | None, str | None]]:
    """Return top-N entries with changed raw contribution, excluding pure drops."""
    return {
        key
        for key in current_top_keys
        if abs(
            _raw_top_n_contribution_value(
                previous_values.get(key, 0.0),
                key in previous_top_keys,
            )
            - _raw_top_n_contribution_value(
                current_values.get(key, 0.0),
                True,
            )
        ) > 1e-9
    }


def _top_n_contribution_changed(
    previous_value: float | None,
    current_value: float | None,
    was_in_top_n: bool,
    is_in_top_n: bool,
) -> bool:
    """Return whether a chart's raw Top-N contribution changed."""
    return abs(
        _raw_top_n_contribution_value(previous_value, was_in_top_n)
        - _raw_top_n_contribution_value(current_value, is_in_top_n)
    ) > 1e-9


def _display_rating_delta(previous_value: float | None, current_value: float | None) -> float:
    """Return the raw rating delta used by rating-change detail cards."""
    return float(current_value or 0.0) - float(previous_value or 0.0)


def _compare_nullable(a: Any, b: Any) -> int:
    if a is None and b is None:
        return 0
    if a is None:
        return 1
    if b is None:
        return -1
    return (a > b) - (a < b)


def _compare_sort_values(a: Any, b: Any, sort_dir: str) -> int:
    result = _compare_nullable(a, b)
    if result == 0 or a is None or b is None:
        return result
    return -result if sort_dir == "desc" else result


def _score_field_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, (float, int)) or isinstance(right, (float, int)):
        try:
            return abs(float(left) - float(right)) < 1e-9
        except (TypeError, ValueError):
            return left == right
    return left == right


def _best_state_criteria(
    best_score: BestScore,
) -> dict[str, Any]:
    criteria = {
        "clear_type": best_score.clear_type,
        "min_bp": best_score.min_bp,
        "exscore": best_score.exscore,
        "rate": best_score.rate,
        "rank": best_score.rank,
    }
    return {field: value for field, value in criteria.items() if value is not None}


def resolve_best_state_timestamps(
    history_rows: list[dict[str, Any]],
    best_score: BestScore,
) -> tuple[datetime | None, datetime | None]:
    """Return when the current displayed BEST state first appeared.

    Rating detail shows the current BEST state, not necessarily the most recent
    play. For append-only score snapshots, a later play can repeat the same
    clear/BP/rate/rank values, so the display timestamp should stay anchored to
    the first snapshot that already had those values.
    """
    row = resolve_best_state_row(history_rows, best_score)
    if row is None:
        return best_score.recorded_at, best_score.sort_recorded_at
    return row.get("display_recorded_at"), row.get("effective_ts")


_resolve_best_state_timestamps = resolve_best_state_timestamps


def resolve_best_state_row(
    history_rows: list[dict[str, Any]],
    best_score: BestScore,
) -> dict[str, Any] | None:
    """Return the real score row that last completed the displayed BEST state."""
    sorted_rows = sorted(
        history_rows,
        key=lambda row: (
            row.get("effective_ts") is None,
            row.get("effective_ts") or datetime.max.replace(tzinfo=UTC),
        ),
    )
    criteria = _best_state_criteria(best_score)

    def matches_all(row: dict[str, Any]) -> bool:
        return all(
            field in row and _score_field_equal(row.get(field), expected)
            for field, expected in criteria.items()
        )

    match = next((row for row in sorted_rows if matches_all(row)), None)
    if match is not None:
        return match

    component_rows = [
        match
        for field, expected in criteria.items()
        if (match := next(
            (
                row for row in sorted_rows
                if field in row and _score_field_equal(row.get(field), expected)
            ),
            None,
        )) is not None
    ]
    if component_rows:
        return max(
            component_rows,
            key=lambda row: row.get("effective_ts") or datetime.min.replace(tzinfo=UTC),
        )
    return None


def _env_rank(client_types: Iterable[str]) -> int:
    unique = {client_type for client_type in client_types if client_type}
    if not unique:
        return 3
    if len(unique) > 1:
        return 2
    only = next(iter(unique))
    if only == "lr2":
        return 0
    if only == "beatoraja":
        return 1
    return 2


def _compare_entries(
    left: dict[str, Any],
    right: dict[str, Any],
    sort_by: str,
    sort_dir: str,
    level_index: dict[str, int],
) -> int:
    if sort_by == "value":
        result = _compare_sort_values(left["value"], right["value"], sort_dir)
    elif sort_by == "rank":
        result = _compare_sort_values(left["rank"], right["rank"], sort_dir)
    elif sort_by == "level":
        result = _compare_sort_values(
            level_index.get(left["level"], -1),
            level_index.get(right["level"], -1),
            sort_dir,
        )
    elif sort_by == "title":
        result = _compare_sort_values(title_sort_key(left["title"]), title_sort_key(right["title"]), sort_dir)
    elif sort_by == "clear_type":
        result = _compare_sort_values(left["clear_type"], right["clear_type"], sort_dir)
    elif sort_by == "min_bp":
        result = _compare_sort_values(left["min_bp"], right["min_bp"], sort_dir)
    elif sort_by == "rate":
        result = _compare_sort_values(left["rate"], right["rate"], sort_dir)
    elif sort_by == "rank_grade":
        result = _compare_sort_values(
            RANK_GRADE_ORDER.get(left["rank_grade"]) if left["rank_grade"] else None,
            RANK_GRADE_ORDER.get(right["rank_grade"]) if right["rank_grade"] else None,
            sort_dir,
        )
    elif sort_by == "env":
        result = _compare_sort_values(_env_rank(left["client_types"]), _env_rank(right["client_types"]), sort_dir)
    elif sort_by == "recorded_at":
        result = _compare_sort_values(
            left.get("sort_recorded_at") or left.get("recorded_at"),
            right.get("sort_recorded_at") or right.get("recorded_at"),
            sort_dir,
        )
    else:
        result = 0

    if result == 0:
        result = _compare_nullable(title_sort_key(left["title"]), title_sort_key(right["title"]))
    if result == 0:
        result = _compare_nullable(left["sha256"] or left["md5"], right["sha256"] or right["md5"])
    return result


async def _query_per_client_bests(
    table_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict[tuple[str | None, str | None], list[PerClientBest]]:
    """Return per-client best scores keyed by canonical (sha256, md5) for a single user.

    Uses the same sha256/md5 JOIN paths as bulk_query_best_scores so LR2 records
    (fumen_sha256=NULL) are correctly grouped with Beatoraja records under the
    canonical fumen key.
    """
    result = await db.execute(
        text("""
            WITH target_fumens AS (
                SELECT f.fumen_id, f.sha256, f.md5
                FROM fumen_table_entries fte
                JOIN fumens f ON f.fumen_id = fte.fumen_id
                WHERE fte.table_id = :table_id
            ),
            latest_per_client AS (
                SELECT us.fumen_id, us.fumen_sha256, us.fumen_md5, us.client_type,
                       us.clear_type, us.exscore, us.rate, us.rank, us.min_bp,
                       ROW_NUMBER() OVER (
                           PARTITION BY us.fumen_id, us.client_type
                           ORDER BY COALESCE(us.recorded_at, us.synced_at) DESC NULLS LAST
                       ) AS rn
                FROM user_scores us
                WHERE us.user_id = :user_id
                  AND us.fumen_id IN (SELECT fumen_id FROM target_fumens)
            ),
            joined AS (
                SELECT tf.sha256 AS tf_sha256, tf.md5 AS tf_md5,
                       lpc.client_type, lpc.clear_type, lpc.exscore, lpc.rate, lpc.rank, lpc.min_bp
                FROM latest_per_client lpc
                JOIN target_fumens tf ON lpc.fumen_id = tf.fumen_id
                WHERE lpc.rn = 1
            )
            SELECT tf_sha256, tf_md5, client_type, clear_type, exscore, rate, rank, min_bp
            FROM joined
        """),
        {"table_id": str(table_id), "user_id": str(user_id)},
    )
    rows = result.mappings().all()

    per_client: dict[tuple[str | None, str | None], list[PerClientBest]] = {}
    for row in rows:
        key = (row["tf_sha256"], row["tf_md5"])
        per_client.setdefault(key, []).append(
            PerClientBest(
                client_type=row["client_type"],
                clear_type=row["clear_type"],
                exscore=row["exscore"],
                rate=float(row["rate"]) if row["rate"] is not None else None,
                rank=row["rank"],
                min_bp=row["min_bp"],
            )
        )
    return per_client


async def _query_best_state_times(
    table_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    targets: Iterable[dict[str, Any]],
    score_by_key: dict[tuple[str | None, str | None], BestScore],
) -> dict[tuple[str | None, str | None], tuple[datetime | None, datetime | None, str | None, str | None, dict | None]]:
    """Return contribution display metadata from exact BEST-state rows."""
    if not score_by_key:
        return {}

    sha256_to_md5, md5_to_sha256 = _canonical_key_maps(targets)
    result = await db.execute(
        text(f"""
            WITH target_fumens AS (
                SELECT f.fumen_id, f.sha256, f.md5
                FROM fumen_table_entries fte
                JOIN fumens f ON f.fumen_id = fte.fumen_id
                WHERE fte.table_id = :table_id
            )
            SELECT
                us.id AS score_id,
                tf.sha256 AS tf_sha256,
                tf.md5 AS tf_md5,
                us.fumen_sha256,
                us.fumen_md5,
                us.clear_type,
                us.exscore,
                us.rate,
                us.rank,
                us.min_bp,
                us.client_type,
                us.options,
                CASE
                    WHEN us.recorded_at IS NOT NULL THEN us.recorded_at
                    WHEN us.synced_at IS NULL THEN NULL
                    WHEN u.first_synced_at IS NULL THEN us.synced_at
                    WHEN u.first_synced_at->>us.client_type IS NULL THEN us.synced_at
                    WHEN us.synced_at <= ((u.first_synced_at->>us.client_type)::timestamptz + {INITIAL_SYNC_SQL_INTERVAL}) THEN NULL
                    ELSE us.synced_at
                END AS display_recorded_at,
                COALESCE(us.recorded_at, us.synced_at) AS effective_ts
            FROM user_scores us
            JOIN users u ON u.id = us.user_id
            JOIN target_fumens tf ON us.fumen_id = tf.fumen_id
            WHERE us.user_id = :user_id
              AND us.fumen_hash_others IS NULL
            ORDER BY effective_ts ASC NULLS LAST
        """),
        {"table_id": str(table_id), "user_id": str(user_id)},
    )

    history_by_key: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
    for row in result.mappings().all():
        key = _canonical_key(row["fumen_sha256"], row["fumen_md5"], sha256_to_md5, md5_to_sha256)
        if key not in score_by_key:
            key = (row["tf_sha256"], row["tf_md5"])
        if key in score_by_key:
            history_by_key.setdefault(key, []).append(dict(row))

    details = {}
    for key, rows in history_by_key.items():
        if key not in score_by_key:
            continue
        detail_row = resolve_best_state_row(rows, score_by_key[key])
        recorded_at = detail_row.get("display_recorded_at") if detail_row else score_by_key[key].recorded_at
        sort_recorded_at = detail_row.get("effective_ts") if detail_row else score_by_key[key].sort_recorded_at
        details[key] = (
            recorded_at,
            sort_recorded_at,
            str(detail_row["score_id"]) if detail_row and detail_row.get("score_id") else None,
            str(detail_row["client_type"]) if detail_row and detail_row.get("client_type") else None,
            detail_row.get("options") if detail_row else None,
        )
    return details


async def build_user_contribution_rows(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    db: AsyncSession,
    metric: str,
    scope: str,
    sort_by: str,
    sort_dir: str,
    page: int,
    limit: int,
    query: str | None,
    table_symbol: str,
) -> dict[str, Any]:
    """Build the contribution payload for the rating detail tables."""
    target_fumens = await query_target_fumen_details(table_cfg.table_id, db)
    score_map = (await bulk_query_best_scores(table_cfg.table_id, db, user_id=user_id)).get(user_id, [])
    score_by_key = {(score.sha256, score.md5): score for score in score_map}
    best_state_times = await _query_best_state_times(table_cfg.table_id, user_id, db, target_fumens, score_by_key)

    per_client_map = await _query_per_client_bests(table_cfg.table_id, user_id, db)

    rows: list[dict[str, Any]] = []
    for target in target_fumens:
        sha256 = target["sha256"]
        md5 = target["md5"]
        score = score_by_key.get((sha256, md5))
        raw_value, _resolved_level = _contribution_value(score, target["level"], table_cfg, sha256, md5)
        per_client_list = per_client_map.get((sha256, md5), [])
        source_client, source_client_detail = aggregate_source_client(per_client_list) if per_client_list else (None, None)
        recorded_at, sort_recorded_at, detail_score_id, detail_client_type, detail_options = (
            best_state_times.get(
                (sha256, md5),
                (
                    score.recorded_at,
                    score.sort_recorded_at,
                    str(score.detail_score_id) if score.detail_score_id else None,
                    score.detail_client_type,
                    score.detail_options,
                ),
            )
            if score is not None
            else (None, None, None, None, None)
        )
        rows.append(
            {
                "sha256": sha256,
                "md5": md5,
                "title": target.get("title") or "(Unknown Title)",
                "artist": target.get("artist"),
                "level": target["level"],
                "symbol": table_symbol,
                "clear_type": display_clear_type(
                    score.clear_type,
                    exscore=score.exscore,
                    rate=score.rate,
                ) if score is not None and score.clear_type is not None else 0,
                "client_types": list(score.client_types) if score is not None else [],
                "min_bp": score.min_bp if score is not None else None,
                "rate": score.rate if score is not None else None,
                "rank_grade": score.rank if score is not None else None,
                "max_minus_score": _max_minus_for_score(score, target),
                "exscore": score.exscore if score is not None else None,
                "raw_value": raw_value,
                "recorded_at": recorded_at,
                "sort_recorded_at": sort_recorded_at,
                "detail_score_id": detail_score_id,
                "client_type": detail_client_type,
                "options": detail_options,
                "source_client": source_client,
                "source_client_detail": source_client_detail,
            }
        )

    value_sorted = sorted(
        rows,
        key=lambda row: (
            -row["raw_value"],
            title_sort_key(row["title"]),
            row["sha256"] or row["md5"] or "",
        ),
    )
    top_keys: set[tuple[str | None, str | None]] = set()
    for row in value_sorted:
        if row["raw_value"] <= 0:
            continue
        if len(top_keys) >= table_cfg.top_n:
            break
        top_keys.add((row["sha256"], row["md5"]))

    rank_by_key = {
        (row["sha256"], row["md5"]): idx
        for idx, row in enumerate(value_sorted, start=1)
    }

    for row in rows:
        key = (row["sha256"], row["md5"])
        row["rank"] = rank_by_key[key]
        row["is_in_top_n"] = key in top_keys
        row["value"] = row["raw_value"]

    if scope == "top":
        filtered = [row for row in value_sorted if (row["sha256"], row["md5"]) in top_keys]
        total_count = len(filtered)
        entries = filtered
        page_out = 1
        limit_out = total_count
    else:
        filtered = rows
        if query:
            filtered = [row for row in filtered if _matches_contribution_query(row, query)]
        level_index = {level: idx for idx, level in enumerate(table_cfg.level_order)}
        filtered = sorted(
            filtered,
            key=cmp_to_key(
                lambda left, right: _compare_entries(left, right, sort_by, sort_dir, level_index)
            ),
        )
        total_count = len(filtered)
        entries = filtered
        page_out = 1
        limit_out = total_count

    return {
        "top_n": table_cfg.top_n,
        "total_count": total_count,
        "page": page_out,
        "limit": limit_out,
        "entries": [
            {
                "rank": row["rank"],
                "sha256": row["sha256"],
                "md5": row["md5"],
                "title": row["title"],
                "artist": row["artist"],
                "level": row["level"],
                "symbol": row["symbol"],
                "clear_type": row["clear_type"],
                "client_types": row["client_types"],
                "min_bp": row["min_bp"],
                "rate": row["rate"],
                "rank_grade": row["rank_grade"],
                "max_minus_score": row.get("max_minus_score"),
                "exscore": row["exscore"],
                "value": round(row["value"], 3),
                "is_in_top_n": row["is_in_top_n"],
                "recorded_at": row["recorded_at"].isoformat() if row.get("recorded_at") else None,
                "sort_recorded_at": row["sort_recorded_at"].isoformat() if row.get("sort_recorded_at") else None,
                "source_client": row.get("source_client"),
                "source_client_detail": row.get("source_client_detail"),
                "detail_score_id": row.get("detail_score_id"),
                "client_type": row.get("client_type"),
                "options": row.get("options"),
            }
            for row in entries
        ],
    }


async def build_user_contribution_rows_at_date(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    db: AsyncSession,
    metric: str,
    scope: str,
    sort_by: str,
    sort_dir: str,
    page: int,
    limit: int,
    query: str | None,
    table_symbol: str,
    as_of: date,
    exp_level_step: float,
) -> dict[str, Any]:
    """Build contribution rows for the rating detail tables at the end of one date.

    Replays all score rows up to ``as_of`` (inclusive) to reconstruct the user's
    best-score state on that date, then formats the result exactly like
    ``build_user_contribution_rows``.
    """
    targets, history_rows = await _query_table_score_history(user_id, table_cfg, db, as_of)
    sha256_to_md5, md5_to_sha256 = _canonical_key_maps(targets)
    targets_by_key: dict[tuple[str | None, str | None], dict[str, Any]] = {
        _canonical_key(target["sha256"], target["md5"], sha256_to_md5, md5_to_sha256): target
        for target in targets
    }

    best_curr: dict[tuple[str | None, str | None], BestScore] = {}
    curr_values: dict[tuple[str | None, str | None], float] = {}
    per_client_scores: dict[tuple[str | None, str | None], dict[str, PerClientBest]] = {}

    for row in history_rows:
        _apply_history_row(
            row,
            targets_by_key,
            sha256_to_md5,
            md5_to_sha256,
            best_curr,
            curr_values,
            table_cfg,
            per_client_scores,
        )

    top_keys = _top_keys_from_values(curr_values, targets_by_key, table_cfg.top_n)

    value_sorted_keys = sorted(
        targets_by_key.keys(),
        key=lambda key: (
            -curr_values.get(key, 0.0),
            title_sort_key(targets_by_key[key].get("title") or ""),
            key[0] or key[1] or "",
        ),
    )
    rank_by_key = {key: idx for idx, key in enumerate(value_sorted_keys, start=1)}

    rows: list[dict[str, Any]] = []
    for target in targets:
        sha256 = target["sha256"]
        md5 = target["md5"]
        canonical = _canonical_key(sha256, md5, sha256_to_md5, md5_to_sha256)
        score = best_curr.get(canonical)
        raw_value = curr_values.get(canonical, 0.0)
        per_client_list = list(per_client_scores.get(canonical, {}).values())
        source_client, source_client_detail = aggregate_source_client(per_client_list) if per_client_list else (None, None)
        recorded_at = score.recorded_at if score is not None else None
        sort_recorded_at = score.sort_recorded_at if score is not None else None
        detail_score_id = str(score.detail_score_id) if score is not None and score.detail_score_id else None
        rank = rank_by_key.get(canonical, len(targets_by_key))
        is_in_top_n = canonical in top_keys
        rows.append(
            {
                "sha256": sha256,
                "md5": md5,
                "title": target.get("title") or "(Unknown Title)",
                "artist": target.get("artist"),
                "level": target["level"],
                "symbol": table_symbol,
                "clear_type": display_clear_type(
                    score.clear_type,
                    exscore=score.exscore,
                    rate=score.rate,
                ) if score is not None and score.clear_type is not None else 0,
                "client_types": list(score.client_types) if score is not None else [],
                "min_bp": score.min_bp if score is not None else None,
                "rate": score.rate if score is not None else None,
                "rank_grade": score.rank if score is not None else None,
                "max_minus_score": _max_minus_for_score(score, target),
                "exscore": score.exscore if score is not None else None,
                "raw_value": raw_value,
                "value": raw_value,
                "rank": rank,
                "is_in_top_n": is_in_top_n,
                "recorded_at": recorded_at,
                "sort_recorded_at": sort_recorded_at,
                "detail_score_id": detail_score_id,
                "client_type": score.detail_client_type if score is not None else None,
                "options": score.detail_options if score is not None else None,
                "source_client": source_client,
                "source_client_detail": source_client_detail,
            }
        )

    if scope == "top":
        value_sorted_rows = sorted(
            rows,
            key=lambda row: (
                -row["raw_value"],
                title_sort_key(row["title"]),
                row["sha256"] or row["md5"] or "",
            ),
        )
        filtered = [row for row in value_sorted_rows if (row["sha256"], row["md5"]) in
                    {(k[0], k[1]) for k in top_keys}]
        total_count = len(filtered)
        entries = filtered
        page_out = 1
        limit_out = total_count
    else:
        filtered = rows
        if query:
            filtered = [row for row in filtered if _matches_contribution_query(row, query)]
        level_index = {level: idx for idx, level in enumerate(table_cfg.level_order)}
        filtered = sorted(
            filtered,
            key=cmp_to_key(
                lambda left, right: _compare_entries(left, right, sort_by, sort_dir, level_index)
            ),
        )
        total_count = len(filtered)
        entries = filtered
        page_out = 1
        limit_out = total_count

    ranking_result = compute_ranking(table_cfg, exp_level_step, list(best_curr.values()))
    summary = {
        "exp": round(ranking_result.exp, 2),
        "rating": round(ranking_result.rating, 2),
        "rating_norm": round(ranking_result.rating_norm, 3),
        "top_n": table_cfg.top_n,
    }

    return {
        "top_n": table_cfg.top_n,
        "total_count": total_count,
        "page": page_out,
        "limit": limit_out,
        "summary": summary,
        "entries": [
            {
                "rank": row["rank"],
                "sha256": row["sha256"],
                "md5": row["md5"],
                "title": row["title"],
                "artist": row["artist"],
                "level": row["level"],
                "symbol": row["symbol"],
                "clear_type": row["clear_type"],
                "client_types": row["client_types"],
                "min_bp": row["min_bp"],
                "rate": row["rate"],
                "rank_grade": row["rank_grade"],
                "max_minus_score": row.get("max_minus_score"),
                "exscore": row["exscore"],
                "value": round(row["value"], 3),
                "is_in_top_n": row["is_in_top_n"],
                "recorded_at": row["recorded_at"].isoformat() if row.get("recorded_at") else None,
                "sort_recorded_at": row["sort_recorded_at"].isoformat() if row.get("sort_recorded_at") else None,
                "source_client": row.get("source_client"),
                "source_client_detail": row.get("source_client_detail"),
                "detail_score_id": row.get("detail_score_id"),
                "client_type": row.get("client_type"),
                "options": row.get("options"),
            }
            for row in entries
        ],
    }


async def _query_table_score_history(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    db: AsyncSession,
    until_date: date,
    include_metadata: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return `(targets, score_rows)` ordered for the rating-update sweep."""
    target_fumen_params = inspect.signature(query_target_fumen_details).parameters
    if "include_metadata" in target_fumen_params:
        target_fumens = await query_target_fumen_details(
            table_cfg.table_id,
            db,
            include_metadata=include_metadata,
        )
    else:
        target_fumens = await query_target_fumen_details(table_cfg.table_id, db)
    result = await db.execute(
        text("""
            SELECT
                us.id AS score_id,
                us.fumen_id,
                us.fumen_sha256,
                us.fumen_md5,
                us.clear_type,
                us.exscore,
                us.rate,
                us.rank,
                us.min_bp,
                us.client_type,
                us.options,
                COALESCE(us.recorded_at, us.synced_at) AS effective_ts
            FROM user_scores us
            WHERE us.user_id = :user_id
              AND us.fumen_hash_others IS NULL
              AND COALESCE(us.recorded_at, us.synced_at)::date <= :until_date
              AND us.fumen_id IN (
                  SELECT fte.fumen_id
                  FROM fumen_table_entries fte
                  WHERE fte.table_id = :table_id
              )
            ORDER BY effective_ts ASC NULLS LAST
        """),
        {
            "user_id": str(user_id),
            "table_id": str(table_cfg.table_id),
            "until_date": until_date,
        },
    )
    return target_fumens, [dict(row) for row in result.mappings().all()]


def _canonical_key_maps(
    targets: Iterable[dict[str, Any]],
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    sha256_to_md5: dict[str, str | None] = {}
    md5_to_sha256: dict[str, str | None] = {}
    for target in targets:
        sha256 = target["sha256"]
        md5 = target["md5"]
        if sha256:
            sha256_to_md5[sha256] = md5
        if md5:
            md5_to_sha256[md5] = sha256
    return sha256_to_md5, md5_to_sha256


def _canonical_key(
    sha256: str | None,
    md5: str | None,
    sha256_to_md5: dict[str, str | None],
    md5_to_sha256: dict[str, str | None],
) -> tuple[str | None, str | None]:
    if sha256 is not None:
        return (sha256, sha256_to_md5.get(sha256))
    if md5 is not None:
        return (md5_to_sha256.get(md5), md5)
    return (None, None)


def _promote_top_n(
    key: tuple[str | None, str | None],
    value: float,
    top_n: int,
    top_set: set[tuple[str | None, str | None]],
    top_heap: list[tuple[float, tuple[str | None, str | None]]],
    current_values: dict[tuple[str | None, str | None], float],
) -> None:
    """Maintain the current top-N membership using a lazy min-heap."""
    if value <= 0:
        return

    def pop_invalid() -> tuple[float, tuple[str | None, str | None]] | None:
        while top_heap:
            heap_value, heap_key = top_heap[0]
            current_value = current_values.get(heap_key, 0.0)
            if heap_key not in top_set or abs(heap_value - current_value) > 1e-9:
                heapq.heappop(top_heap)
                continue
            return (heap_value, heap_key)
        return None

    if key in top_set:
        heapq.heappush(top_heap, (value, key))
        return

    if len(top_set) < top_n:
        top_set.add(key)
        heapq.heappush(top_heap, (value, key))
        return

    smallest = pop_invalid()
    if smallest is None or value > smallest[0]:
        if smallest is not None:
            _popped_value, popped_key = heapq.heappop(top_heap)
            top_set.discard(popped_key)
        top_set.add(key)
        heapq.heappush(top_heap, (value, key))


def _build_rating_update_detail_entry(
    rank: int,
    key: tuple[str | None, str | None],
    targets_by_key: dict[tuple[str | None, str | None], dict[str, Any]],
    best_scores: dict[tuple[str | None, str | None], BestScore],
    table_cfg: TableRankingConfig,
    table_symbol: str,
    value: float,
) -> dict[str, Any]:
    target = targets_by_key[key]
    score = best_scores.get(key)
    return {
        "rank": rank,
        "sha256": key[0],
        "md5": key[1],
        "title": target.get("title") or "(Unknown Title)",
        "artist": target.get("artist"),
        "level": target["level"],
        "symbol": table_symbol,
        "clear_type": display_clear_type(
            score.clear_type,
            exscore=score.exscore,
            rate=score.rate,
        ) if score is not None and score.clear_type is not None else 0,
        "client_types": list(score.client_types) if score is not None else [],
        "min_bp": score.min_bp if score is not None else None,
        "rate": score.rate if score is not None else None,
        "rank_grade": score.rank if score is not None else None,
        "exscore": score.exscore if score is not None else None,
        "value": round(value, 3),
        "is_in_top_n": True,
        "client_type": score.detail_client_type if score is not None else None,
        "options": score.detail_options if score is not None else None,
    }


def _clone_best_score(score: BestScore) -> BestScore:
    return BestScore(
        fumen_id=score.fumen_id,
        sha256=score.sha256,
        md5=score.md5,
        level=score.level,
        clear_type=score.clear_type,
        exscore=score.exscore,
        rate=score.rate,
        rank=score.rank,
        min_bp=score.min_bp,
        client_types=tuple(score.client_types),
        recorded_at=score.recorded_at,
        sort_recorded_at=score.sort_recorded_at,
        detail_score_id=score.detail_score_id,
        detail_client_type=score.detail_client_type,
        detail_options=score.detail_options,
    )


def _resolve_date_window(
    year: int | None = None,
    days: int | None = None,
    target_date: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    if from_date is not None or to_date is not None:
        if from_date is None or to_date is None:
            raise ValueError("Both from_date and to_date must be provided together")
        return (from_date, to_date)
    now = datetime.now(UTC).date()
    if target_date is not None:
        return (target_date, target_date)
    if year is not None:
        return (date(year, 1, 1), date(year, 12, 31))
    if days is not None:
        return (now - timedelta(days=max(days - 1, 0)), now)
    raise ValueError("One of year, days, or target_date must be provided")


def _ordered_positive_keys(
    current_values: dict[tuple[str | None, str | None], float],
    targets_by_key: dict[tuple[str | None, str | None], dict[str, Any]],
) -> list[tuple[str | None, str | None]]:
    return sorted(
        [
            key for key, value in current_values.items()
            if value > 0 and key in targets_by_key
        ],
        key=lambda key: (
            -current_values.get(key, 0.0),
            title_sort_key(targets_by_key[key].get("title")),
            key[0] or key[1] or "",
        ),
    )


def _rating_order_key(
    key: tuple[str | None, str | None],
    current_values: dict[tuple[str | None, str | None], float],
    targets_by_key: dict[tuple[str | None, str | None], dict[str, Any]],
) -> tuple[float, Any, str]:
    """Return the stable rating contribution order key used by dashboard displays."""
    return (
        -current_values.get(key, 0.0),
        title_sort_key(targets_by_key[key].get("title")),
        key[0] or key[1] or "",
    )


def _ordered_top_keys_from_values(
    current_values: dict[tuple[str | None, str | None], float],
    targets_by_key: dict[tuple[str | None, str | None], dict[str, Any]],
    top_n: int,
) -> list[tuple[str | None, str | None]]:
    """Return top-N positive keys without sorting every positive contribution."""
    if top_n <= 0:
        return []
    candidates = [
        key for key, value in current_values.items()
        if value > 0 and key in targets_by_key
    ]
    if len(candidates) <= top_n:
        return sorted(candidates, key=lambda key: _rating_order_key(key, current_values, targets_by_key))
    return heapq.nsmallest(
        top_n,
        candidates,
        key=lambda key: _rating_order_key(key, current_values, targets_by_key),
    )


def _top_keys_from_values(
    current_values: dict[tuple[str | None, str | None], float],
    targets_by_key: dict[tuple[str | None, str | None], dict[str, Any]],
    top_n: int,
) -> set[tuple[str | None, str | None]]:
    return set(_ordered_top_keys_from_values(current_values, targets_by_key, top_n))


def _capture_ranks_for_targets(
    values: dict[tuple[str | None, str | None], float],
    targets_by_key: dict[tuple[str | None, str | None], dict[str, Any]],
    required_keys: set[tuple[str | None, str | None]],
) -> tuple[dict[tuple[str | None, str | None], int], int]:
    sortable = sorted(
        targets_by_key,
        key=lambda key: (
            -float(values.get(key, 0.0)),
            title_sort_key(targets_by_key[key].get("title")),
            key[0] or key[1] or "",
        ),
    )
    captured: dict[tuple[str | None, str | None], int] = {}
    for index, key in enumerate(sortable, start=1):
        if key in required_keys:
            captured[key] = index
    return captured, len(sortable)


def _apply_history_row(
    row: dict[str, Any],
    targets_by_key: dict[tuple[str | None, str | None], dict[str, Any]],
    sha256_to_md5: dict[str, str | None],
    md5_to_sha256: dict[str, str | None],
    best_scores: dict[tuple[str | None, str | None], BestScore],
    current_values: dict[tuple[str | None, str | None], float],
    table_cfg: TableRankingConfig,
    per_client_scores: dict[tuple[str | None, str | None], dict[str, PerClientBest]] | None = None,
) -> tuple[tuple[str | None, str | None] | None, bool]:
    canonical = _canonical_key(
        row["fumen_sha256"],
        row["fumen_md5"],
        sha256_to_md5,
        md5_to_sha256,
    )
    if canonical == (None, None) or canonical not in targets_by_key:
        return (None, False)

    target = targets_by_key[canonical]
    client_type = row.get("client_type")
    if per_client_scores is not None and client_type:
        current_client = per_client_scores.setdefault(canonical, {}).get(client_type)
        merged_client = PerClientBest(
            client_type=str(client_type),
            clear_type=current_client.clear_type if current_client is not None else None,
            exscore=current_client.exscore if current_client is not None else None,
            rate=current_client.rate if current_client is not None else None,
            rank=current_client.rank if current_client is not None else None,
            min_bp=current_client.min_bp if current_client is not None else None,
        )
        if row["clear_type"] is not None and (
            merged_client.clear_type is None or row["clear_type"] > merged_client.clear_type
        ):
            merged_client.clear_type = row["clear_type"]
        if row["exscore"] is not None and (
            merged_client.exscore is None or row["exscore"] > merged_client.exscore
        ):
            merged_client.exscore = row["exscore"]
            merged_client.rate = float(row["rate"]) if row["rate"] is not None else None
            merged_client.rank = row["rank"]
        if row["min_bp"] is not None and (
            merged_client.min_bp is None or row["min_bp"] < merged_client.min_bp
        ):
            merged_client.min_bp = row["min_bp"]
        per_client_scores[canonical][str(client_type)] = merged_client

    merged, changed = _merge_best_score_fields(
        best_scores.get(canonical),
        row,
        target["level"],
        canonical[0],
        canonical[1],
    )
    if not changed or merged is None:
        return (canonical, False)

    best_scores[canonical] = merged
    value, _resolved_level = _contribution_value(
        merged,
        target["level"],
        table_cfg,
        canonical[0],
        canonical[1],
    )
    current_values[canonical] = value
    return (canonical, True)


async def _compute_rating_update_sweep(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    db: AsyncSession,
    table_symbol: str,
    start_date: date,
    end_date: date,
    target_date: date | None = None,
    excluded_dates: set[date] | None = None,
    include_updated_keys: bool = False,
    include_detail_entries: bool = False,
) -> dict[str, Any]:
    """Compute rating-update counts with optional per-day updated-key output."""
    query_history_params = inspect.signature(_query_table_score_history).parameters
    if "include_metadata" in query_history_params:
        targets, history_rows = await _query_table_score_history(
            user_id,
            table_cfg,
            db,
            end_date,
            include_metadata=include_detail_entries,
        )
    else:
        targets, history_rows = await _query_table_score_history(user_id, table_cfg, db, end_date)
    sha256_to_md5, md5_to_sha256 = _canonical_key_maps(targets)
    targets_by_key = {
        _canonical_key(target["sha256"], target["md5"], sha256_to_md5, md5_to_sha256): target
        for target in targets
    }

    best_scores: dict[tuple[str | None, str | None], BestScore] = {}
    current_values: dict[tuple[str | None, str | None], float] = {}
    top_set: set[tuple[str | None, str | None]] = set()
    top_heap: list[tuple[float, tuple[str | None, str | None]]] = []
    counts_by_date: dict[str, int] = {}
    updated_keys_by_date: dict[str, set[tuple[str | None, str | None]]] = {}
    detail_entries: list[dict[str, Any]] = []
    excluded_dates = excluded_dates or set()

    row_index = 0
    while row_index < len(history_rows):
        row = history_rows[row_index]
        effective_ts = row["effective_ts"]
        if effective_ts is None or effective_ts.date() >= start_date:
            break
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
            _promote_top_n(canonical, current_values.get(canonical, 0.0), table_cfg.top_n, top_set, top_heap, current_values)
        row_index += 1

    current_date = start_date
    while current_date <= end_date:
        is_excluded_date = current_date in excluded_dates
        previous_values_snapshot: dict[tuple[str | None, str | None], float] | None = None
        previous_top_keys_snapshot: set[tuple[str | None, str | None]] = set()
        day_updated_keys: set[tuple[str | None, str | None]] = set()

        if not is_excluded_date:
            previous_values_snapshot = dict(current_values)
            previous_top_keys_snapshot = _top_keys_from_values(
                previous_values_snapshot,
                targets_by_key,
                table_cfg.top_n,
            )

        while row_index < len(history_rows):
            row = history_rows[row_index]
            effective_ts = row["effective_ts"]
            if effective_ts is None or effective_ts.date() != current_date:
                break

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
                _promote_top_n(canonical, current_values.get(canonical, 0.0), table_cfg.top_n, top_set, top_heap, current_values)
                day_updated_keys.add(canonical)
            row_index += 1

        if is_excluded_date:
            counts_by_date[current_date.isoformat()] = 0
            current_date += timedelta(days=1)
            continue

        assert previous_values_snapshot is not None
        current_top_keys = _top_keys_from_values(current_values, targets_by_key, table_cfg.top_n)
        updated_top_keys = _rating_update_countable_top_keys(
            previous_values_snapshot,
            current_values,
            previous_top_keys_snapshot,
            current_top_keys,
        )
        date_key = current_date.isoformat()
        counts_by_date[date_key] = len(updated_top_keys)

        if include_updated_keys and updated_top_keys:
            updated_keys_by_date[date_key] = set(updated_top_keys)

        if include_detail_entries and target_date is not None and current_date == target_date:
            ordered_top_keys = _ordered_positive_keys(current_values, targets_by_key)
            rank_by_key = {
                key: index
                for index, key in enumerate(ordered_top_keys, start=1)
            }
            detail_entries = [
                _build_rating_update_detail_entry(
                    rank=rank_by_key[key],
                    key=key,
                    targets_by_key=targets_by_key,
                    best_scores=best_scores,
                    table_cfg=table_cfg,
                    table_symbol=table_symbol,
                    value=current_values.get(key, 0.0),
                )
                for key in ordered_top_keys
                if key in updated_top_keys and key in current_top_keys
            ]

        current_date += timedelta(days=1)

    return {
        "counts_by_date": counts_by_date,
        "updated_keys_by_date": updated_keys_by_date,
        "entries": detail_entries,
        "top_n": table_cfg.top_n,
    }


async def compute_rating_updates(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    db: AsyncSession,
    table_symbol: str,
    year: int | None = None,
    days: int | None = None,
    target_date: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    excluded_dates: set[date] | None = None,
) -> dict[str, Any]:
    """Compute rating-update counts via a single chronological sweep."""
    start_date, end_date = _resolve_date_window(
        year=year,
        days=days,
        target_date=target_date,
        from_date=from_date,
        to_date=to_date,
    )
    sweep = await _compute_rating_update_sweep(
        user_id=user_id,
        table_cfg=table_cfg,
        db=db,
        table_symbol=table_symbol,
        start_date=start_date,
        end_date=end_date,
        target_date=target_date,
        excluded_dates=excluded_dates,
        include_detail_entries=target_date is not None,
    )
    counts_by_date = sweep["counts_by_date"]
    return {
        "dates": [{"date": key, "count": value} for key, value in counts_by_date.items() if value > 0],
        "date": target_date.isoformat() if target_date else None,
        "count": counts_by_date.get(target_date.isoformat(), 0) if target_date else None,
        "entries": sweep["entries"],
        "top_n": table_cfg.top_n,
    }


async def compute_rating_updates_aggregated(
    user_id: uuid.UUID,
    ranking_tables: list[TableRankingConfig],
    db: AsyncSession,
    year: int | None = None,
    days: int | None = None,
    target_date: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    excluded_dates: set[date] | None = None,
) -> dict[str, Any]:
    """Aggregate rating-update counts across every ranking-enabled table with key dedupe."""
    start_date, end_date = _resolve_date_window(
        year=year,
        days=days,
        target_date=target_date,
        from_date=from_date,
        to_date=to_date,
    )
    aggregated_by_date: dict[str, set[tuple[str | None, str | None]]] = {}
    target_tables: list[dict[str, Any]] = []
    target_date_key = target_date.isoformat() if target_date is not None else None

    for table_cfg in sorted(ranking_tables, key=lambda table: table.display_order):
        sweep = await _compute_rating_update_sweep(
            user_id=user_id,
            table_cfg=table_cfg,
            db=db,
            table_symbol="",
            start_date=start_date,
            end_date=end_date,
            target_date=target_date,
            excluded_dates=excluded_dates,
            include_updated_keys=True,
        )

        for date_key, keys in sweep["updated_keys_by_date"].items():
            aggregated_by_date.setdefault(date_key, set()).update(keys)

        if target_date_key is not None:
            table_count = sweep["counts_by_date"].get(target_date_key, 0)
            if table_count > 0:
                target_tables.append(
                    {
                        "table_slug": table_cfg.slug,
                        "display_name": table_cfg.display_name,
                        "count": table_count,
                        "display_order": table_cfg.display_order,
                    }
                )

    if target_date_key is not None:
        return {
            "date": target_date_key,
            "count": len(aggregated_by_date.get(target_date_key, set())),
            "tables": target_tables,
        }

    return {
        "dates": [
            {"date": date_key, "count": len(keys)}
            for date_key, keys in sorted(aggregated_by_date.items())
            if keys
        ],
    }


def _build_breakdown_entry(
    key: tuple[str | None, str | None],
    current_score: BestScore | None,
    previous_score: BestScore | None,
    target: dict[str, Any],
    table_cfg: TableRankingConfig,
    table_symbol: str,
    value: float,
    previous_value: float | None,
    rank: int,
    previous_rank: int | None,
    source_client: str | None,
    source_client_detail: dict[str, str] | None,
    extra: dict[str, float],
    updated_today: bool = True,
    detail_score_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    preferred_score = current_score or previous_score
    detail_score = (
        previous_score
        if previous_score is not None and previous_score.detail_score_id == detail_score_id
        else current_score
        if current_score is not None and current_score.detail_score_id == detail_score_id
        else preferred_score
    )
    return {
        "rank": rank,
        "previous_rank": previous_rank,
        "fumen_id": str(target["fumen_id"]) if target.get("fumen_id") else None,
        "sha256": key[0],
        "md5": key[1],
        "title": target.get("title") or "(Unknown Title)",
        "artist": target.get("artist"),
        "level": target["level"],
        "symbol": table_symbol,
        "clear_type": display_clear_type(
            current_score.clear_type,
            exscore=current_score.exscore,
            rate=current_score.rate,
        ) if current_score is not None and current_score.clear_type is not None else 0,
        "previous_clear_type": display_clear_type(
            previous_score.clear_type,
            exscore=previous_score.exscore,
            rate=previous_score.rate,
        ) if previous_score is not None else None,
        "client_types": list(preferred_score.client_types) if preferred_score is not None else [],
        "min_bp": current_score.min_bp if current_score is not None else None,
        "previous_min_bp": previous_score.min_bp if previous_score is not None else None,
        "rate": current_score.rate if current_score is not None else None,
        "previous_rate": previous_score.rate if previous_score is not None else None,
        "rank_grade": current_score.rank if current_score is not None else None,
        "previous_rank_grade": previous_score.rank if previous_score is not None else None,
        "max_minus_score": _max_minus_for_score(current_score, target),
        "previous_max_minus_score": _max_minus_for_score(previous_score, target),
        "exscore": current_score.exscore if current_score is not None else None,
        "previous_exscore": previous_score.exscore if previous_score is not None else None,
        "value": round(value, 3),
        "previous_value": round(previous_value, 3) if previous_value is not None else None,
        "is_in_top_n": False,
        "source_client": source_client,
        "source_client_detail": source_client_detail,
        "updated_today": updated_today,
        "detail_score_id": str(detail_score_id) if detail_score_id else None,
        "client_type": detail_score.detail_client_type if detail_score is not None else None,
        "options": detail_score.detail_options if detail_score is not None else None,
        **{name: round(delta, 3) for name, delta in extra.items()},
    }


async def compute_rating_breakdown(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    db: AsyncSession,
    table_symbol: str,
    exp_level_step: float,
    target_date: date,
    excluded_dates: set[date] | None = None,
) -> dict[str, Any]:
    """Return per-day EXP/Rating/BMSFORCE breakdown for one ranking table."""
    excluded_dates = excluded_dates or set()
    targets, history_rows = await _query_table_score_history(user_id, table_cfg, db, target_date)
    sha256_to_md5, md5_to_sha256 = _canonical_key_maps(targets)
    targets_by_key = {
        _canonical_key(target["sha256"], target["md5"], sha256_to_md5, md5_to_sha256): target
        for target in targets
    }

    best_prev: dict[tuple[str | None, str | None], BestScore] = {}
    prev_values: dict[tuple[str | None, str | None], float] = {}
    per_client_prev: dict[tuple[str | None, str | None], dict[str, PerClientBest]] = {}
    row_index = 0
    while row_index < len(history_rows):
        row = history_rows[row_index]
        effective_ts = row["effective_ts"]
        if effective_ts is None or effective_ts.date() >= target_date:
            break
        _apply_history_row(
            row,
            targets_by_key,
            sha256_to_md5,
            md5_to_sha256,
            best_prev,
            prev_values,
            table_cfg,
            per_client_prev,
        )
        row_index += 1

    best_curr = {key: _clone_best_score(score) for key, score in best_prev.items()}
    curr_values = dict(prev_values)
    per_client_curr = {
        key: {
            client_type: PerClientBest(
                client_type=value.client_type,
                clear_type=value.clear_type,
                exscore=value.exscore,
                rate=value.rate,
                rank=value.rank,
                min_bp=value.min_bp,
            )
            for client_type, value in per_client_map.items()
        }
        for key, per_client_map in per_client_prev.items()
    }
    day_updated_keys: set[tuple[str | None, str | None]] = set()
    day_rows_by_key: dict[tuple[str | None, str | None], list[PerClientBest]] = {}

    while row_index < len(history_rows):
        row = history_rows[row_index]
        effective_ts = row["effective_ts"]
        if effective_ts is None or effective_ts.date() != target_date:
            break
        canonical, changed = _apply_history_row(
            row,
            targets_by_key,
            sha256_to_md5,
            md5_to_sha256,
            best_curr,
            curr_values,
            table_cfg,
            per_client_curr,
        )
        if changed and canonical is not None:
            day_updated_keys.add(canonical)
        # Collect per-client rows for this day regardless of whether best-score changed
        canon = _canonical_key(row["fumen_sha256"], row["fumen_md5"], sha256_to_md5, md5_to_sha256)
        if canon != (None, None) and canon in targets_by_key and row.get("client_type"):
            day_rows_by_key.setdefault(canon, []).append(
                PerClientBest(
                    client_type=str(row["client_type"]),
                    clear_type=row.get("clear_type"),
                    exscore=row.get("exscore"),
                    rate=float(row["rate"]) if row.get("rate") is not None else None,
                    rank=row.get("rank"),
                    min_bp=row.get("min_bp"),
                )
            )
        row_index += 1

    target_date_excluded = target_date in excluded_dates
    if target_date_excluded:
        day_updated_keys.clear()
        day_rows_by_key.clear()

    previous_top_keys = _top_keys_from_values(prev_values, targets_by_key, table_cfg.top_n)
    current_top_keys = _top_keys_from_values(curr_values, targets_by_key, table_cfg.top_n)
    exp_candidate_keys: set[tuple[str | None, str | None]] = set()
    candidate_keys = day_updated_keys | previous_top_keys | current_top_keys
    if target_date_excluded:
        previous_top_keys = set()
        current_top_keys = set()
        candidate_keys = set()
    exp_rank_map, exp_total_entries = _capture_ranks_for_targets(curr_values, targets_by_key, day_updated_keys)
    exp_previous_rank_map, _ = _capture_ranks_for_targets(prev_values, targets_by_key, day_updated_keys)
    rating_rank_map, rating_total_entries = _capture_ranks_for_targets(curr_values, targets_by_key, candidate_keys)
    rating_previous_rank_map, _ = _capture_ranks_for_targets(prev_values, targets_by_key, candidate_keys)

    exp_contributions: list[dict[str, Any]] = []
    for key in day_updated_keys:
        target = targets_by_key.get(key)
        if target is None:
            continue
        exp_prev = prev_values.get(key, 0.0)
        exp_curr = curr_values.get(key, 0.0)
        delta_exp = _display_whole_metric_delta(exp_prev, exp_curr)
        if delta_exp == 0:
            continue
        exp_candidate_keys.add(key)
        day_rows = day_rows_by_key.get(key, [])
        if day_rows:
            source_client, source_client_detail = aggregate_source_client(day_rows)
        else:
            source_client, source_client_detail = None, None
        exp_contributions.append(
            _build_breakdown_entry(
                key=key,
                current_score=best_curr.get(key),
                previous_score=best_prev.get(key),
                target=target,
                table_cfg=table_cfg,
                table_symbol=table_symbol,
                value=exp_curr,
                previous_value=exp_prev,
                rank=exp_rank_map.get(key, 0),
                previous_rank=exp_previous_rank_map.get(key),
                source_client=source_client,
                source_client_detail=source_client_detail,
                extra={"delta_exp": float(delta_exp)},
                updated_today=bool(day_rows),
                detail_score_id=best_curr.get(key).detail_score_id if best_curr.get(key) else None,
            )
        )

    exp_contributions.sort(
        key=lambda entry: (
            -entry["delta_exp"],
            title_sort_key(entry["title"]),
            entry["sha256"] or entry["md5"] or "",
        ),
    )

    rating_contributions: list[dict[str, Any]] = []
    for key in candidate_keys:
        target = targets_by_key.get(key)
        if target is None:
            continue
        prev_rating_value = prev_values.get(key, 0.0)
        curr_rating_value = curr_values.get(key, 0.0)
        if not _top_n_contribution_changed(
            previous_value=prev_rating_value,
            current_value=curr_rating_value,
            was_in_top_n=key in previous_top_keys,
            is_in_top_n=key in current_top_keys,
        ):
            continue
        delta_rating = _display_rating_delta(prev_rating_value, curr_rating_value)
        rating_day_rows = day_rows_by_key.get(key, [])
        if rating_day_rows:
            source_client, source_client_detail = aggregate_source_client(rating_day_rows)
        else:
            source_client, source_client_detail = None, None
        rating_contributions.append(
            _build_breakdown_entry(
                key=key,
                current_score=best_curr.get(key),
                previous_score=best_prev.get(key),
                target=target,
                table_cfg=table_cfg,
                table_symbol=table_symbol,
                value=curr_values.get(key, 0.0),
                previous_value=prev_values.get(key, 0.0),
                rank=rating_rank_map.get(key, 0),
                previous_rank=rating_previous_rank_map.get(key),
                source_client=source_client,
                source_client_detail=source_client_detail,
                extra={"delta_rating": float(delta_rating)},
                updated_today=bool(rating_day_rows),
                detail_score_id=(
                    best_prev.get(key).detail_score_id
                    if key in previous_top_keys and key not in current_top_keys and best_prev.get(key)
                    else best_curr.get(key).detail_score_id if best_curr.get(key) else None
                ),
            )
        )

    rating_contributions.sort(
        key=lambda entry: (
            -abs(entry["delta_rating"]),
            title_sort_key(entry["title"]),
            entry["sha256"] or entry["md5"] or "",
        ),
    )
    for entry in rating_contributions:
        key = (entry["sha256"], entry["md5"])
        entry["was_in_top_n"] = key in previous_top_keys
        entry["is_in_top_n"] = key in current_top_keys

    exp_rank_map, exp_total_entries = _capture_ranks_for_targets(curr_values, targets_by_key, exp_candidate_keys)
    for entry in exp_contributions:
        key = (entry["sha256"], entry["md5"])
        entry["rank"] = exp_rank_map.get(key, 0)

    previous_result = compute_ranking(table_cfg, exp_level_step, list(best_prev.values()))
    current_result = compute_ranking(table_cfg, exp_level_step, list(best_curr.values()))
    rating_only_norm = standardize_rating(current_result.rating, previous_result.exp_level)
    rating_component = rating_only_norm - previous_result.rating_norm
    level_component = current_result.rating_norm - previous_result.rating_norm - rating_component

    def _snapshot_from_result(result: Any) -> dict[str, Any]:
        progress = compute_exp_progress_fields(
            exp=result.exp,
            exp_level=result.exp_level,
            exp_level_step=exp_level_step,
            max_level=table_cfg.max_level,
        )
        return {
            "exp": round(result.exp, 2),
            "exp_level": result.exp_level,
            "exp_level_progress_ratio": progress["exp_level_progress_ratio"],
            "exp_to_next_level": progress["exp_to_next_level"],
            "exp_level_current_span": progress["exp_level_current_span"],
            "is_max_level": progress["is_max_level"],
            "max_level": table_cfg.max_level,
            "rating": round(result.rating, 2),
            "rating_norm": round(result.rating_norm, 3),
        }

    return {
        "date": target_date.isoformat(),
        "previous": _snapshot_from_result(previous_result),
        "current": _snapshot_from_result(current_result),
        "exp_contributions": exp_contributions,
        "exp_total_entries": exp_total_entries,
        "rating_contributions": rating_contributions,
        "rating_total_entries": rating_total_entries,
        "bmsforce_breakdown": {
            "rating_component": round(rating_component, 3),
            "level_component": round(level_component, 3),
            "total": round(current_result.rating_norm - previous_result.rating_norm, 3),
        },
    }
