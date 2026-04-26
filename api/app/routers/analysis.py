"""Play analysis data endpoints."""
import uuid
from datetime import UTC, datetime, timedelta
from datetime import date as date_cls
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, and_, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.models.course import Course
from app.models.difficulty_table import DifficultyTable, UserFavoriteDifficultyTable
from app.models.fumen import Fumen
from app.models.score import UserPlayerStats, UserScore
from app.models.user import User
from app.services.clear_type_display import display_clear_type
from app.services.client_aggregation import (
    CLIENT_LABEL,
    PerClientBest,
    aggregate_source_client,
)
from app.services.ranking_config import get_ranking_config
from app.services.ranking_dashboard import (
    compute_rating_breakdown,
    compute_rating_updates,
    compute_rating_updates_aggregated,
    get_user_ranking_version,
)
from app.services.rating_derived_data import (
    fetch_user_rating_update_count_for_date,
    fetch_user_rating_update_daily,
    fetch_user_rating_update_tables_for_date,
    fetch_user_table_rating_update_daily,
    has_fresh_user_rating_derived_data,
    has_fresh_user_table_rating_derived_data,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])
_RATING_UPDATES_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_RATING_UPDATES_AGG_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_RATING_BREAKDOWN_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_CUSTOM_RANGE_MAX_DAYS = 730


def _rating_count_map(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Return a `date -> count` map from stored or fallback daily rows."""
    return {
        str(row["date"]): int(row["count"])
        for row in rows
    }


async def _fetch_aggregated_rating_update_rows(
    target_user: User,
    ranking_tables,
    from_date: date_cls,
    to_date: date_cls,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Return overview rating-update rows from derived data or legacy fallback."""
    table_ids = [table.table_id for table in ranking_tables]
    use_derived = await has_fresh_user_rating_derived_data(target_user.id, table_ids, db)
    if use_derived:
        return await fetch_user_rating_update_daily(target_user.id, from_date, to_date, db)

    legacy = await compute_rating_updates_aggregated(
        user_id=target_user.id,
        ranking_tables=ranking_tables,
        db=db,
        from_date=from_date,
        to_date=to_date,
        excluded_dates=_rating_update_excluded_dates(target_user),
    )
    return legacy.get("dates", [])


async def _resolve_target_user(
    user_id: uuid.UUID | None,
    current_user: User | None,
    db: AsyncSession,
) -> User:
    """Resolve the requested dashboard target user."""
    if user_id is None:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return current_user

    if current_user is not None and current_user.id == user_id:
        return current_user

    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if target_user is None or not target_user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    return target_user


def _initial_sync_exclusion_filters(user: User) -> list:
    """Return SQLAlchemy filters that exclude scores imported during the initial
    bulk sync (synced_at <= first_synced_at[client_type] + 1 hour).
    Currently applied to LR2 only.
    """
    first_synced = user.first_synced_at or {}
    conditions = []
    for ct in ("lr2",):
        ts_str = first_synced.get(ct)
        if ts_str:
            cutoff = datetime.fromisoformat(ts_str) + timedelta(hours=1)
            conditions.append(
                or_(
                    UserScore.client_type != ct,
                    UserScore.synced_at > cutoff,
                )
            )
    return conditions


def _rating_update_excluded_dates(user: User) -> set[date_cls]:
    """Return first-sync calendar dates that should skip rating-update aggregation."""
    first_synced = user.first_synced_at or {}
    excluded_dates: set[date_cls] = set()
    for client_type in ("lr2", "beatoraja"):
        ts_str = first_synced.get(client_type)
        if not ts_str:
            continue
        excluded_dates.add(datetime.fromisoformat(ts_str).date())
    return excluded_dates


def _find_prev_row(
    target: UserScore,
    rows_map: dict[tuple, list],
) -> "UserScore | None":
    """Return the row immediately before target in timeline for the same fumen+client."""
    hash_key = target.fumen_sha256 or target.fumen_md5
    key = (hash_key, target.client_type)
    target_ts = target.recorded_at or target.synced_at
    if not target_ts:
        return None
    prev = None
    for r in rows_map.get(key, []):
        if r.id == target.id:
            continue
        r_ts = r.recorded_at or r.synced_at
        if r_ts and r_ts < target_ts:
            prev = r
    return prev


def _is_stat_only(entry: UserScore, prev: "UserScore | None") -> bool:
    """True if only play_count changed — no clear_type/exscore/min_bp/max_combo improvement."""
    if prev is None:
        return False  # 신규 fumen은 갱신으로 간주
    improved = (
        (entry.clear_type or 0) > (prev.clear_type or 0)
        or (entry.exscore or 0) > (prev.exscore or 0)
        or (
            entry.min_bp is not None
            and (prev.min_bp is None or entry.min_bp < prev.min_bp)
        )
        or (entry.max_combo or 0) > (prev.max_combo or 0)
    )
    if improved:
        return False
    return (entry.play_count or 0) != (prev.play_count or 0)


def _is_initial_sync_record(entry: UserScore, user: User) -> bool:
    """True if this score was synced during the initial bulk sync window (first_synced_at + 1h)."""
    first_synced = user.first_synced_at or {}
    ts_str = first_synced.get(entry.client_type)
    if not ts_str:
        return False
    cutoff = datetime.fromisoformat(ts_str) + timedelta(hours=1)
    return entry.synced_at is not None and entry.synced_at <= cutoff


def _find_course_prev_row(
    target: UserScore,
    rows_map: dict[tuple, list],
) -> "UserScore | None":
    """Return the row immediately before target for the same course (fumen_hash_others) + client."""
    key = (target.fumen_hash_others, target.client_type)
    target_ts = target.recorded_at or target.synced_at
    if not target_ts:
        return None
    prev = None
    for r in rows_map.get(key, []):
        if r.id == target.id:
            continue
        r_ts = r.recorded_at or r.synced_at
        if r_ts and r_ts < target_ts:
            prev = r
    return prev


def _canonical_fumen_key(
    sha256: str | None,
    md5: str | None,
    md5_to_sha256: dict[str, str],
) -> tuple[str | None, str | None]:
    if sha256:
        return (sha256, None)
    if md5 and md5 in md5_to_sha256:
        return (md5_to_sha256[md5], None)
    if md5:
        return (None, md5)
    return (None, None)


def _build_fumen_aggregate(
    rows: list[Any],
    md5_to_sha256: dict[str, str],
) -> dict[tuple[str | None, str | None], dict[str, Any]]:
    aggregated: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    per_fumen_client: dict[tuple[str | None, str | None], dict[str, dict[str, Any]]] = {}

    for row in rows:
        key = _canonical_fumen_key(row.fumen_sha256, row.fumen_md5, md5_to_sha256)
        if key == (None, None) or not row.client_type:
            continue
        per_client = per_fumen_client.setdefault(key, {})
        entry = per_client.setdefault(
            row.client_type,
            {
                "clear_type": None,
                "exscore": None,
                "rate": None,
                "rank": None,
                "min_bp": None,
                "max_combo": None,
                "options": None,
                "play_count": None,
            },
        )
        clear_type = display_clear_type(row.clear_type, exscore=row.exscore, rate=row.rate)
        if clear_type is not None and (
            entry["clear_type"] is None or clear_type > entry["clear_type"]
        ):
            entry["clear_type"] = clear_type
            entry["options"] = row.options
        if row.exscore is not None and (
            entry["exscore"] is None or row.exscore > entry["exscore"]
        ):
            entry["exscore"] = row.exscore
            entry["rate"] = row.rate
            entry["rank"] = row.rank
        if row.min_bp is not None and (
            entry["min_bp"] is None or row.min_bp < entry["min_bp"]
        ):
            entry["min_bp"] = row.min_bp
        if row.max_combo is not None and (
            entry["max_combo"] is None or row.max_combo > entry["max_combo"]
        ):
            entry["max_combo"] = row.max_combo
        if row.play_count is not None:
            entry["play_count"] = max(entry["play_count"] or 0, row.play_count)

    for key, per_client in per_fumen_client.items():
        best_clear_type = None
        best_exscore = None
        best_rate = None
        best_rank = None
        best_min_bp = None
        best_max_combo = None
        best_client_type = None
        options = None
        play_count = None

        for client_type, entry in per_client.items():
            if entry["clear_type"] is not None and (
                best_clear_type is None or entry["clear_type"] > best_clear_type
            ):
                best_clear_type = entry["clear_type"]
                best_client_type = client_type
                options = entry["options"]
            if entry["exscore"] is not None and (
                best_exscore is None or entry["exscore"] > best_exscore
            ):
                best_exscore = entry["exscore"]
                best_rate = entry["rate"]
                best_rank = entry["rank"]
            if entry["min_bp"] is not None and (
                best_min_bp is None or entry["min_bp"] < best_min_bp
            ):
                best_min_bp = entry["min_bp"]
            if entry["max_combo"] is not None and (
                best_max_combo is None or entry["max_combo"] > best_max_combo
            ):
                best_max_combo = entry["max_combo"]
            play_count = max(play_count or 0, entry["play_count"] or 0)

        source_client, source_client_detail = aggregate_source_client(
            PerClientBest(
                client_type=client_type,
                clear_type=entry["clear_type"],
                exscore=entry["exscore"],
                rate=entry["rate"],
                rank=entry["rank"],
                min_bp=entry["min_bp"],
            )
            for client_type, entry in per_client.items()
        )
        aggregated[key] = {
            "current_state": {
                "clear_type": best_clear_type,
                "exscore": best_exscore,
                "rate": best_rate,
                "rank": best_rank,
                "min_bp": best_min_bp,
                "max_combo": best_max_combo,
            },
            "client_type": best_client_type,
            "options": options,
            "play_count": play_count or None,
            "source_client": source_client,
            "source_client_detail": source_client_detail,
        }
    return aggregated


async def _get_ranking_aggregate_version(
    user: User,
    db: AsyncSession,
) -> tuple[str | None, str | None]:
    """Return `(max_synced_at, max_calculated_at)` across ranking tables for cache keys."""
    synced_row = await db.execute(
        select(func.max(UserScore.synced_at)).where(UserScore.user_id == user.id)
    )
    max_synced_at = synced_row.scalar_one_or_none()

    calculated_row = await db.execute(
        text("""
            SELECT MAX(calculated_at)
            FROM user_rankings
            WHERE user_id = :user_id
        """),
        {"user_id": str(user.id)},
    )
    max_calculated_at = calculated_row.scalar_one_or_none()

    return (
        max_synced_at.isoformat() if max_synced_at else None,
        max_calculated_at.isoformat() if max_calculated_at else None,
    )


@router.get("/summary")
async def get_play_summary(
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a summary of the current user's play statistics.

    Pass client_type=lr2 or client_type=beatoraja to filter by game client.
    Omit client_type to get combined stats across all clients.
    """
    target_user = await _resolve_target_user(user_id, current_user, db)

    base_filter = [UserScore.user_id == target_user.id]
    if client_type:
        base_filter.append(UserScore.client_type == client_type)

    result = await db.execute(
        select(
            func.count(UserScore.id).label("total_scores"),
            func.sum(UserScore.play_count).label("total_play_count"),
        ).where(*base_filter)
    )
    row = result.one()

    # Use player table totals (exact) when available; fall back to per-song sum.
    # user_player_stats is now append-only, so take the latest row per client_type
    # via DISTINCT ON before summing.
    stats_latest_filter = [UserPlayerStats.user_id == target_user.id]
    if client_type:
        stats_latest_filter.append(UserPlayerStats.client_type == client_type)
    latest_subq = (
        select(UserPlayerStats)
        .distinct(UserPlayerStats.client_type)
        .where(*stats_latest_filter)
        .order_by(UserPlayerStats.client_type, UserPlayerStats.synced_at.desc())
    ).subquery()
    pstats_result = await db.execute(
        select(
            func.sum(latest_subq.c.playcount),
            func.sum(latest_subq.c.playtime),
            func.max(latest_subq.c.synced_at),
        )
    )
    pstats = pstats_result.one()

    total_play_count = int(pstats[0] or 0) or int(row.total_play_count or 0)
    total_playtime = int(pstats[1] or 0)
    last_synced_at = pstats[2]

    lr2_hit_keys = {"perfect", "great", "good", "bad"}
    bea_hit_keys = {"epg", "lpg", "egr", "lgr", "egd", "lgd", "ebd", "lbd"}
    judgments_result = await db.execute(
        select(latest_subq.c.client_type, latest_subq.c.judgments)
    )
    total_notes_hit = 0
    for ct, j in judgments_result.all():
        if not j:
            continue
        keys = lr2_hit_keys if ct == "lr2" else bea_hit_keys
        total_notes_hit += sum(j.get(k, 0) for k in keys)

    # First sync date per client type — stored on the user object (set on first sync)
    first_synced_by_client = target_user.first_synced_at or {}

    return {
        "total_scores": row.total_scores or 0,
        "total_play_count": total_play_count,
        "total_playtime": total_playtime,
        "total_notes_hit": total_notes_hit,
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        "first_synced_by_client": first_synced_by_client,
    }


def _build_activity_subquery(user: User, client_type: str | None = None):
    """Build a subquery over user_scores (fumens + courses) with LAG window
    functions to enable per-item improvement detection.

    Aggregation rules:
    - Courses (fumen_hash_others) are included.
    - client_type is excluded from the partition key → LR2 and Beatoraja records
      for the same fumen are treated as one item (unified basis).
    - rn_in_day: row_number descending within (user, hash, day); rn_in_day == 1
      selects the single latest record per item per day, preventing double-counting
      when the same fumen is played multiple times on the same day.

    Returns a subquery with columns:
        day (DATE), synced_at, client_type,
        clear_type, exscore, min_bp, max_combo,
        prev_ct, prev_ex, prev_bp, prev_mc, rn, rn_in_day
    """
    effective_ts = func.coalesce(UserScore.recorded_at, UserScore.synced_at)
    day_col = cast(func.timezone("UTC", effective_ts), Date)
    # Courses identified by fumen_hash_others; fallback to sha256/md5 for fumens
    hash_col = func.coalesce(
        UserScore.fumen_sha256, UserScore.fumen_md5, UserScore.fumen_hash_others
    )
    # Unified window: no client_type — LR2/Beatoraja share the same timeline
    window_spec = dict(
        partition_by=[UserScore.user_id, hash_col],
        order_by=[effective_ts],
    )
    # Day-level window: latest record per (item, day); desc order → rn_in_day=1 is newest
    window_day = dict(
        partition_by=[UserScore.user_id, hash_col, day_col],
        order_by=[effective_ts.desc()],
    )

    inner_filters: list = [UserScore.user_id == user.id]
    if client_type:
        inner_filters.append(UserScore.client_type == client_type)

    return (
        select(
            day_col.label("day"),
            UserScore.synced_at,
            UserScore.client_type,
            UserScore.clear_type,
            UserScore.exscore,
            UserScore.min_bp,
            UserScore.max_combo,
            func.lag(UserScore.clear_type).over(**window_spec).label("prev_ct"),
            func.lag(UserScore.exscore).over(**window_spec).label("prev_ex"),
            func.lag(UserScore.min_bp).over(**window_spec).label("prev_bp"),
            func.lag(UserScore.max_combo).over(**window_spec).label("prev_mc"),
            func.row_number().over(**window_spec).label("rn"),
            func.row_number().over(**window_day).label("rn_in_day"),
        )
        .where(*inner_filters)
    ).subquery()


def _improvement_filter(subq):
    """Return a SQLAlchemy expression that is True when the row improved at least one
    of the four tracked metrics compared with the immediately preceding play.
    First plays (rn == 1) are excluded — they are counted separately as new_plays.
    """
    return and_(
        subq.c.rn > 1,
        or_(
            subq.c.clear_type > func.coalesce(subq.c.prev_ct, 0),
            subq.c.exscore > func.coalesce(subq.c.prev_ex, 0),
            and_(
                subq.c.min_bp.is_not(None),
                or_(subq.c.prev_bp.is_(None), subq.c.min_bp < subq.c.prev_bp),
            ),
            subq.c.max_combo > func.coalesce(subq.c.prev_mc, 0),
        )
    )


def _initial_sync_exclusion_for_subq(user: User, subq) -> list:
    """Like _initial_sync_exclusion_filters but operates on a subquery's columns."""
    first_synced = user.first_synced_at or {}
    conditions = []
    for ct in ("lr2",):
        ts_str = first_synced.get(ct)
        if ts_str:
            cutoff = datetime.fromisoformat(ts_str) + timedelta(hours=1)
            conditions.append(
                or_(
                    subq.c.client_type != ct,
                    subq.c.synced_at > cutoff,
                )
            )
    return conditions


async def _get_daily_plays(
    user: User,
    client_type: str | None,
    from_date,
    until_date,
    db: AsyncSession,
) -> dict[str, int]:
    """Return {date_str: total_plays} from UserPlayerStats LAG deltas.

    Uses the playcount column from player_stats to compute how many plays
    occurred between consecutive syncs.  First-sync rows produce delta=0
    automatically because LAG=NULL → COALESCE(lag, playcount) = playcount.
    """
    h = UserPlayerStats
    lag_pc = func.lag(h.playcount).over(
        partition_by=[h.user_id, h.client_type],
        order_by=h.synced_at,
    )
    delta = func.greatest(0, h.playcount - func.coalesce(lag_pc, h.playcount))

    filters: list = [h.user_id == user.id]
    if client_type:
        filters.append(h.client_type == client_type)

    inner = (
        select(
            cast(func.timezone("UTC", h.synced_at), Date).label("day"),
            delta.label("delta"),
        ).where(*filters)
    ).subquery()

    result = await db.execute(
        select(inner.c.day, func.sum(inner.c.delta).label("plays"))
        .where(inner.c.day >= from_date, inner.c.day < until_date)
        .group_by(inner.c.day)
    )
    return {str(r.day): int(r.plays or 0) for r in result.all()}


def _resolve_activity_window(
    days: int | None,
    from_: date_cls | None,
    to: date_cls | None,
) -> tuple[date_cls, date_cls, dict[str, Any]]:
    """Resolve activity window into an inclusive start and exclusive end date."""
    if (from_ is None) != (to is None):
        raise HTTPException(status_code=400, detail="both 'from' and 'to' must be provided")

    if from_ is not None and to is not None:
        if days is not None:
            raise HTTPException(status_code=400, detail="specify either days or from+to")
        if to < from_:
            raise HTTPException(status_code=400, detail="'from' must be <= 'to'")
        if (to - from_).days > _CUSTOM_RANGE_MAX_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"Date range too large (max {_CUSTOM_RANGE_MAX_DAYS} days)",
            )
        return (
            from_,
            to + timedelta(days=1),
            {"from": from_.isoformat(), "to": to.isoformat()},
        )

    resolved_days = days or 30
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=max(resolved_days - 1, 0))
    return (start_date, end_date + timedelta(days=1), {"days": resolved_days})


def _resolve_rating_update_window(
    year: int | None,
    days: int | None,
    target_date: date_cls | None,
    from_: date_cls | None,
    to: date_cls | None,
) -> tuple[date_cls | None, date_cls | None]:
    """Validate rating-update query modes and return explicit range values if used."""
    explicit_range_supplied = from_ is not None or to is not None
    if explicit_range_supplied and (from_ is None or to is None):
        raise HTTPException(status_code=400, detail="both 'from' and 'to' must be provided")

    supplied_modes = sum(
        value is not None
        for value in (
            year,
            days,
            target_date,
            from_ if from_ is not None and to is not None else None,
        )
    )
    if supplied_modes != 1:
        raise HTTPException(status_code=400, detail="Specify exactly one of year, days, date, or from+to")

    if from_ is not None and to is not None:
        if to < from_:
            raise HTTPException(status_code=400, detail="'from' must be <= 'to'")
        if (to - from_).days > _CUSTOM_RANGE_MAX_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"Date range too large (max {_CUSTOM_RANGE_MAX_DAYS} days)",
            )

    return (from_, to)


async def _get_day_stats(
    user: User,
    client_type: str | None,
    date_str: str,
    db: AsyncSession,
) -> dict:
    """Return {playcount, playtime, notes_hit} deltas for a specific date from PlayerStats.

    Uses LAG window function to compute per-sync deltas.
    First-sync rows produce delta=0 for all metrics:
      playcount: GREATEST(0, pc - COALESCE(lag_pc, pc)) → 0 when LAG=NULL
      playtime:  GREATEST(0, pt - COALESCE(lag_pt, pt)) → 0 when LAG=NULL
      notes_hit: skipped when prev_judgments is None
    """
    target_date = date_cls.fromisoformat(date_str)
    next_date = target_date + timedelta(days=1)

    h = UserPlayerStats
    lag_pc = func.lag(h.playcount).over(
        partition_by=[h.user_id, h.client_type],
        order_by=h.synced_at,
    )
    lag_pt = func.lag(h.playtime).over(
        partition_by=[h.user_id, h.client_type],
        order_by=h.synced_at,
    )
    lag_j = func.lag(h.judgments).over(
        partition_by=[h.user_id, h.client_type],
        order_by=h.synced_at,
    )
    delta_pc = func.greatest(0, h.playcount - func.coalesce(lag_pc, h.playcount))
    delta_pt = func.greatest(0, h.playtime - func.coalesce(lag_pt, h.playtime))

    filters: list = [h.user_id == user.id]
    if client_type:
        filters.append(h.client_type == client_type)

    inner = select(
        h.client_type.label("client_type"),
        cast(func.timezone("UTC", h.synced_at), Date).label("day"),
        delta_pc.label("delta_pc"),
        delta_pt.label("delta_pt"),
        h.judgments.label("judgments"),
        lag_j.label("prev_judgments"),
    ).where(*filters).subquery()

    result = await db.execute(
        select(inner).where(inner.c.day >= target_date, inner.c.day < next_date)
    )
    rows = result.all()

    total_playcount = sum(int(r.delta_pc or 0) for r in rows)
    total_playtime = sum(int(r.delta_pt or 0) for r in rows)
    total_notes_hit = 0
    for r in rows:
        j = r.judgments or {}
        pj = r.prev_judgments  # None on first sync → skip
        if pj is None:
            continue
        if r.client_type == "lr2":
            keys = ["perfect", "great", "good", "bad"]
        else:  # beatoraja
            keys = ["epg", "lpg", "egr", "lgr", "egd", "lgd", "ebd", "lbd"]
        for k in keys:
            total_notes_hit += max(0, int(j.get(k) or 0) - int(pj.get(k) or 0))

    # Uncertain when PlayerStats rows exist but delta is 0 — covers first-sync rows
    # (LAG=NULL) and clients that don't provide playtime/judgments (e.g. LR2 without
    # a player table).  If rows is empty the date predates PlayerStats tracking;
    # uncertainty in that case depends on whether score records exist (checked by
    # the caller).
    playcount_uncertain = bool(rows) and total_playcount == 0
    playtime_uncertain = bool(rows) and total_playtime == 0
    notes_hit_uncertain = bool(rows) and total_notes_hit == 0

    return {
        "playcount": total_playcount,
        "playcount_uncertain": playcount_uncertain,
        "playtime": total_playtime,
        "notes_hit": total_notes_hit,
        "playtime_uncertain": playtime_uncertain,
        "notes_hit_uncertain": notes_hit_uncertain,
        "has_rows": bool(rows),
    }


@router.get("/heatmap")
async def get_activity_heatmap(
    year: int = Query(default=0, description="Year (0 = current year)"),
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return per-day record-update, new-play, and play counts for the given year.

    updates   = rows where any metric improved vs the previous play (rn > 1).
    new_plays = first-ever plays for a fumen (rn == 1), counted separately from updates.
    plays     = user_scores.play_count LAG delta sum per day (mirrors day_summary logic).
    """
    target_user = await _resolve_target_user(user_id, current_user, db)
    target_year = year if year > 0 else datetime.now(UTC).year
    start = datetime(target_year, 1, 1, tzinfo=UTC)
    end = datetime(target_year + 1, 1, 1, tzinfo=UTC)

    subq = _build_activity_subquery(target_user, client_type)
    is_improvement = _improvement_filter(subq)

    outer_filters = [
        subq.c.day >= start.date(),
        subq.c.day < end.date(),
    ]
    outer_filters.extend(_initial_sync_exclusion_for_subq(target_user, subq))

    result = await db.execute(
        select(
            subq.c.day,
            func.count().filter(is_improvement & (subq.c.rn_in_day == 1)).label("updates"),
            func.count().filter(subq.c.rn == 1).label("new_plays"),
        )
        .where(*outer_filters)
        .group_by(subq.c.day)
        .order_by(subq.c.day)
    )
    updates_by_day: dict[str, int] = {}
    new_plays_by_day: dict[str, int] = {}
    for r in result.all():
        updates_by_day[str(r.day)] = r.updates
        new_plays_by_day[str(r.day)] = r.new_plays

    plays_by_day = await _get_daily_plays(
        target_user, client_type, start.date(), end.date(), db
    )
    try:
        ranking_cfg = get_ranking_config()
        rating_rows = await _fetch_aggregated_rating_update_rows(
            target_user,
            ranking_cfg.tables,
            start.date(),
            (end - timedelta(days=1)).date(),
            db,
        )
    except RuntimeError:
        rating_rows = []
    rating_map = _rating_count_map(rating_rows)

    all_dates = sorted(set(updates_by_day) | set(new_plays_by_day) | set(plays_by_day) | set(rating_map))
    return {
        "year": target_year,
        "data": [
            {
                "date": d,
                "updates": updates_by_day.get(d, 0),
                "new_plays": new_plays_by_day.get(d, 0),
                "plays": plays_by_day.get(d, 0),
                "rating_updates": rating_map.get(d, 0),
            }
            for d in all_dates
        ],
    }


@router.get("/activity")
async def get_activity_bar(
    days: int | None = Query(default=None, ge=7, le=365, description="Number of recent days"),
    from_: date_cls | None = Query(None, alias="from", description="Inclusive start date"),
    to: date_cls | None = Query(None, description="Inclusive end date"),
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return daily record-update, new-play, and play counts for the last N days.

    updates   = rows where any metric improved vs the previous play (rn > 1).
    new_plays = first-ever plays for a fumen (rn == 1), counted separately from updates.
    plays     = user_scores.play_count LAG delta sum per day (mirrors day_summary logic).
    """
    target_user = await _resolve_target_user(user_id, current_user, db)
    from_date, until_date, window_meta = _resolve_activity_window(days, from_, to)

    subq = _build_activity_subquery(target_user, client_type)
    is_improvement = _improvement_filter(subq)

    outer_filters = [
        subq.c.day >= from_date,
        subq.c.day < until_date,
    ]
    outer_filters.extend(_initial_sync_exclusion_for_subq(target_user, subq))

    result = await db.execute(
        select(
            subq.c.day,
            func.count().filter(is_improvement & (subq.c.rn_in_day == 1)).label("updates"),
            func.count().filter(subq.c.rn == 1).label("new_plays"),
        )
        .where(*outer_filters)
        .group_by(subq.c.day)
        .order_by(subq.c.day)
    )
    updates_by_day: dict[str, int] = {}
    new_plays_by_day: dict[str, int] = {}
    for r in result.all():
        updates_by_day[str(r.day)] = r.updates
        new_plays_by_day[str(r.day)] = r.new_plays

    plays_by_day = await _get_daily_plays(
        target_user, client_type, from_date, until_date, db
    )
    try:
        ranking_cfg = get_ranking_config()
        rating_rows = await _fetch_aggregated_rating_update_rows(
            target_user,
            ranking_cfg.tables,
            from_date,
            until_date - timedelta(days=1),
            db,
        )
    except RuntimeError:
        rating_rows = []
    rating_map = _rating_count_map(rating_rows)

    all_dates = sorted(set(updates_by_day) | set(new_plays_by_day) | set(plays_by_day) | set(rating_map))
    return {
        **window_meta,
        "data": [
            {
                "date": d,
                "updates": updates_by_day.get(d, 0),
                "new_plays": new_plays_by_day.get(d, 0),
                "plays": plays_by_day.get(d, 0),
                "rating_updates": rating_map.get(d, 0),
            }
            for d in all_dates
        ],
    }


@router.get("/rating-updates")
async def get_rating_updates(
    table_slug: str = Query(..., description="Ranking-enabled table slug"),
    year: int | None = Query(None, description="Whole-year heatmap mode"),
    days: int | None = Query(None, ge=1, le=365, description="Recent N days mode"),
    date: date_cls | None = Query(None, description="YYYY-MM-DD detail mode"),
    from_: date_cls | None = Query(None, alias="from", description="Inclusive start date"),
    to: date_cls | None = Query(None, description="Inclusive end date"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return rating-update counts or date detail rows for one ranking table."""
    from_date, to_date = _resolve_rating_update_window(year, days, date, from_, to)

    target_user = await _resolve_target_user(user_id, current_user, db)

    try:
        config = get_ranking_config()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Ranking config not initialised") from exc

    table_cfg = config.get_table_by_slug(table_slug)
    if table_cfg is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_slug}' not found")

    max_synced_at, calculated_at = await get_user_ranking_version(target_user.id, table_cfg.table_id, db)
    excluded_dates = _rating_update_excluded_dates(target_user)
    excluded_dates_key = tuple(sorted(day.isoformat() for day in excluded_dates))
    cache_key = (
        str(target_user.id),
        table_slug,
        year,
        days,
        date,
        from_date,
        to_date,
        excluded_dates_key,
        max_synced_at,
        calculated_at,
    )
    cached = _RATING_UPDATES_CACHE.get(cache_key)
    if cached is not None:
        return cached

    use_derived = await has_fresh_user_table_rating_derived_data(target_user.id, table_cfg.table_id, db)
    if use_derived:
        stored_rows = await fetch_user_table_rating_update_daily(
            target_user.id,
            table_cfg.table_id,
            from_date,
            to_date,
            db,
        )
        payload = {
            "dates": stored_rows,
            "date": date.isoformat() if date else None,
            "count": None,
            "entries": [],
            "top_n": table_cfg.top_n,
        }
        if date is not None:
            payload["count"] = next((row["count"] for row in stored_rows if row["date"] == date.isoformat()), 0)
            table_row = await db.execute(
                select(DifficultyTable.symbol).where(DifficultyTable.id == table_cfg.table_id)
            )
            table_symbol = table_row.scalar_one_or_none() or ""
            detail_payload = await compute_rating_updates(
                user_id=target_user.id,
                table_cfg=table_cfg,
                db=db,
                table_symbol=table_symbol,
                target_date=date,
                excluded_dates=excluded_dates,
            )
            payload["entries"] = detail_payload["entries"]
    else:
        table_row = await db.execute(
            select(DifficultyTable.symbol).where(DifficultyTable.id == table_cfg.table_id)
        )
        table_symbol = table_row.scalar_one_or_none() or ""
        payload = await compute_rating_updates(
            user_id=target_user.id,
            table_cfg=table_cfg,
            db=db,
            table_symbol=table_symbol,
            year=year,
            days=days,
            target_date=date,
            from_date=from_date,
            to_date=to_date,
            excluded_dates=excluded_dates,
        )
    response = {
        "table_slug": table_slug,
        "calculated_at": calculated_at,
        **payload,
    }
    _RATING_UPDATES_CACHE[cache_key] = response
    return response


@router.get("/rating-updates/aggregated")
async def get_rating_updates_aggregated(
    year: int | None = Query(None, description="Whole-year heatmap mode"),
    days: int | None = Query(None, ge=1, le=365, description="Recent N days mode"),
    date: date_cls | None = Query(None, description="YYYY-MM-DD detail mode"),
    from_: date_cls | None = Query(None, alias="from", description="Inclusive start date"),
    to: date_cls | None = Query(None, description="Inclusive end date"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return rating-update counts aggregated across all ranking-enabled tables."""
    from_date, to_date = _resolve_rating_update_window(year, days, date, from_, to)

    target_user = await _resolve_target_user(user_id, current_user, db)

    try:
        config = get_ranking_config()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Ranking config not initialised") from exc

    max_synced_at, max_calculated_at = await _get_ranking_aggregate_version(target_user, db)
    excluded_dates = _rating_update_excluded_dates(target_user)
    excluded_dates_key = tuple(sorted(day.isoformat() for day in excluded_dates))
    cache_key = (
        str(target_user.id),
        year,
        days,
        date,
        from_date,
        to_date,
        excluded_dates_key,
        max_synced_at,
        max_calculated_at,
    )
    cached = _RATING_UPDATES_AGG_CACHE.get(cache_key)
    if cached is not None:
        return cached

    use_derived = await has_fresh_user_rating_derived_data(
        target_user.id,
        [table.table_id for table in config.tables],
        db,
    )
    if use_derived:
        if date is not None:
            response = {
                "date": date.isoformat(),
                "count": await fetch_user_rating_update_count_for_date(target_user.id, date, db),
                "tables": await fetch_user_rating_update_tables_for_date(target_user.id, date, config.tables, db),
            }
        else:
            response = {
                "dates": await fetch_user_rating_update_daily(target_user.id, from_date, to_date, db),
            }
    else:
        response = await compute_rating_updates_aggregated(
            user_id=target_user.id,
            ranking_tables=config.tables,
            db=db,
            year=year,
            days=days,
            target_date=date,
            from_date=from_date,
            to_date=to_date,
            excluded_dates=excluded_dates,
        )
    _RATING_UPDATES_AGG_CACHE[cache_key] = response
    return response


@router.get("/rating-breakdown")
async def get_rating_breakdown(
    table_slug: str = Query(..., description="Ranking-enabled table slug"),
    date: str = Query(..., description="YYYY-MM-DD detail mode"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return EXP/Rating/BMSFORCE breakdown for one date and ranking table."""
    target_user = await _resolve_target_user(user_id, current_user, db)

    try:
        config = get_ranking_config()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Ranking config not initialised") from exc

    table_cfg = config.get_table_by_slug(table_slug)
    if table_cfg is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_slug}' not found")

    table_row = await db.execute(
        select(DifficultyTable.symbol).where(DifficultyTable.id == table_cfg.table_id)
    )
    table_symbol = table_row.scalar_one_or_none() or ""

    max_synced_at, calculated_at = await get_user_ranking_version(target_user.id, table_cfg.table_id, db)
    excluded_dates = _rating_update_excluded_dates(target_user)
    excluded_dates_key = tuple(sorted(day.isoformat() for day in excluded_dates))
    cache_key = (
        str(target_user.id),
        table_slug,
        date,
        excluded_dates_key,
        max_synced_at,
        calculated_at,
    )
    cached = _RATING_BREAKDOWN_CACHE.get(cache_key)
    if cached is not None:
        return cached

    response = await compute_rating_breakdown(
        user_id=target_user.id,
        table_cfg=table_cfg,
        db=db,
        table_symbol=table_symbol,
        exp_level_step=config.exp_level_step,
        target_date=date_cls.fromisoformat(date),
        excluded_dates=excluded_dates,
    )
    _RATING_BREAKDOWN_CACHE[cache_key] = response
    return response


@router.get("/recent-updates")
async def get_recent_updates(
    limit: int = Query(default=20, ge=1, le=100),
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    date: str | None = Query(None, description="YYYY-MM-DD — filter by recorded_at date"),
    table_slug: str | None = Query(None, description="Optional ranking table for day summary"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return recent score entries ordered by effective play time.

    Includes song title/subtitle/artist and difficulty level badges from the user's
    favorite tables.
    Pass date=YYYY-MM-DD to filter by recorded_at date (returns up to 200 entries).
    """
    target_user = await _resolve_target_user(user_id, current_user, db)
    effective_ts = func.coalesce(UserScore.recorded_at, UserScore.synced_at)
    recent_filter = [UserScore.user_id == target_user.id]
    if client_type:
        recent_filter.append(UserScore.client_type == client_type)
    recent_filter.extend(_initial_sync_exclusion_filters(target_user))
    if date:
        effective_date = cast(func.timezone("UTC", effective_ts), Date)
        recent_filter.append(effective_date == date_cls.fromisoformat(date))
        effective_limit = 200
    else:
        effective_limit = limit

    result = await db.execute(
        select(UserScore)
        .where(*recent_filter)
        .order_by(effective_ts.desc())
        .limit(effective_limit)
    )
    entries = result.scalars().all()

    # Collect hashes to look up song metadata (sha256 preferred, md5 as fallback for LR2)
    sha256s = [e.fumen_sha256 for e in entries if e.fumen_sha256]
    md5s = [e.fumen_md5 for e in entries if e.fumen_md5]

    song_map: dict[str, Any] = {}
    md5_song_map: dict[str, Any] = {}
    if sha256s:
        songs_result = await db.execute(
            select(Fumen.sha256, Fumen.title, Fumen.artist).where(
                Fumen.sha256.in_(sha256s)
            )
        )
        for row in songs_result.all():
            song_map[row.sha256] = {
                "title": row.title,
                "artist": row.artist,
            }
    if md5s:
        md5_songs_result = await db.execute(
            select(Fumen.md5, Fumen.title, Fumen.artist).where(
                Fumen.md5.in_(md5s)
            )
        )
        for row in md5_songs_result.all():
            md5_song_map[row.md5] = {
                "title": row.title,
                "artist": row.artist,
            }

    # Build sha256 → [{symbol, level}] map from user's favorite tables via fumens.table_entries
    sha256_to_levels: dict[str, list[dict[str, str]]] = {}
    sha256_to_levels_seen: dict[str, set] = {}
    if sha256s:
        fav_result = await db.execute(
                select(UserFavoriteDifficultyTable.table_id).where(
                    UserFavoriteDifficultyTable.user_id == target_user.id
                )
        )
        fav_table_ids = [r[0] for r in fav_result.all()]
        if fav_table_ids:
            tables_result = await db.execute(
                select(DifficultyTable.id, DifficultyTable.symbol).where(
                    DifficultyTable.id.in_(fav_table_ids)
                )
            )
            table_symbols: dict[str, str] = {str(row.id): row.symbol or "" for row in tables_result.all()}
            fav_table_ids_str = set(table_symbols.keys())

            fumens_result = await db.execute(
                select(Fumen.sha256, Fumen.table_entries).where(
                    Fumen.sha256.in_(sha256s),
                    Fumen.table_entries.isnot(None),
                )
            )
            for fumen_row in fumens_result.all():
                s256 = fumen_row.sha256
                if not s256:
                    continue
                for entry in (fumen_row.table_entries or []):
                    tid_str = str(entry.get("table_id", ""))
                    if tid_str not in fav_table_ids_str:
                        continue
                    symbol = table_symbols.get(tid_str, "")
                    level = str(entry.get("level", ""))
                    key = (symbol, level)
                    if key not in sha256_to_levels_seen.setdefault(s256, set()):
                        sha256_to_levels_seen[s256].add(key)
                        sha256_to_levels.setdefault(s256, []).append({"symbol": symbol, "level": level})

    # ── Day-specific summary (only when date filter is active) ───────────────
    stat_only_ids: set[str] = set()
    day_summary_out: dict | None = None
    rating_update_tables_out: list[dict[str, Any]] | None = None

    if date:
        # Dedup entries by hash key (unified basis: client_type ignored).
        # entries is already sorted by effective_ts desc → first occurrence = latest record.
        seen_hashes: set[str] = set()
        deduped_entries: list[UserScore] = []
        for e in entries:
            hash_key = e.fumen_sha256 or e.fumen_md5 or e.fumen_hash_others
            if hash_key and hash_key not in seen_hashes:
                seen_hashes.add(hash_key)
                deduped_entries.append(e)

        fumen_entries = [e for e in deduped_entries if e.fumen_hash_others is None]
        sha256s_h = [e.fumen_sha256 for e in fumen_entries if e.fumen_sha256]
        md5s_h = [
            e.fumen_md5
            for e in fumen_entries
            if e.fumen_md5 and not e.fumen_sha256
        ]

        # Batch-fetch history for all affected fumens (same pattern as get_score_updates)
        history_map: dict[tuple, list] = {}
        if sha256s_h or md5s_h:
            prev_conds = []
            if sha256s_h:
                prev_conds.append(UserScore.fumen_sha256.in_(sha256s_h))
            if md5s_h:
                prev_conds.append(
                    (UserScore.fumen_md5.in_(md5s_h)) & UserScore.fumen_sha256.is_(None)
                )
            combined_cond = prev_conds[0]
            for c in prev_conds[1:]:
                combined_cond = combined_cond | c
            hist_result = await db.execute(
                select(UserScore)
                .where(
                    UserScore.user_id == target_user.id,
                    UserScore.fumen_hash_others.is_(None),
                    combined_cond,
                )
                .order_by(effective_ts.asc())
            )
            for r in hist_result.scalars().all():
                k = (r.fumen_sha256 or r.fumen_md5, r.client_type)
                history_map.setdefault(k, []).append(r)

        # Per-entry previous row mapping
        entry_prev: dict[str, UserScore | None] = {
            str(e.id): _find_prev_row(e, history_map) for e in fumen_entries
        }

        # stat_only: play_count-only increase, no real performance improvement
        stat_only_ids = {
            str(e.id)
            for e in fumen_entries
            if _is_stat_only(e, entry_prev.get(str(e.id)))
        }

        day_stats = await _get_day_stats(target_user, client_type, date, db)

        # Score records exist but no PlayerStats rows → date predates PlayerStats
        # tracking (e.g. Beatoraja recorded_at before first sync) → uncertain.
        no_stats_but_has_records = not day_stats["has_rows"] and len(entries) > 0

        # play_count: use PlayerStats LAG delta (same source as heatmap/activity).
        # None when PlayerStats has no rows for this date (predates tracking).
        if no_stats_but_has_records:
            total_play_count_out: int | None = None
        else:
            total_play_count_out = day_stats["playcount"] if day_stats["has_rows"] else None

        # Compute total_updates using the same _build_activity_subquery logic as the
        # heatmap/activity endpoints — this is the single authoritative source so that
        # all frontend widgets (calendar, bar chart, stat card) always show the same number.
        subq_day = _build_activity_subquery(target_user, client_type)
        is_imp_day = _improvement_filter(subq_day)
        target_date_obj = date_cls.fromisoformat(date)
        excl_day = _initial_sync_exclusion_for_subq(target_user, subq_day)
        counts_res = await db.execute(
            select(
                func.count().filter(is_imp_day & (subq_day.c.rn_in_day == 1)).label("updates"),
                func.count().filter(subq_day.c.rn == 1).label("new_plays"),
            )
            .where(subq_day.c.day == target_date_obj, *excl_day)
        )
        counts_row = counts_res.one()
        total_updates_authoritative: int = counts_row.updates or 0
        total_new_plays_authoritative: int = counts_row.new_plays or 0

        day_summary_out = {
            "total_updates": total_updates_authoritative,
            "new_plays": total_new_plays_authoritative,
            "total_play_count": total_play_count_out,
            "play_count_uncertain": day_stats["playcount_uncertain"] or no_stats_but_has_records,
            "stat_only_count": len(stat_only_ids),
            "total_playtime": day_stats["playtime"],
            "total_notes_hit": day_stats["notes_hit"],
            "playtime_uncertain": day_stats["playtime_uncertain"] or no_stats_but_has_records,
            "notes_hit_uncertain": day_stats["notes_hit_uncertain"] or no_stats_but_has_records,
            "rating_updates": 0,
        }
        try:
            ranking_cfg = get_ranking_config()
        except RuntimeError:
            ranking_cfg = None
        if ranking_cfg is not None:
            use_derived = await has_fresh_user_rating_derived_data(
                target_user.id,
                [table.table_id for table in ranking_cfg.tables],
                db,
            )
            if use_derived:
                day_summary_out["rating_updates"] = await fetch_user_rating_update_count_for_date(
                    target_user.id,
                    target_date_obj,
                    db,
                )
                rating_update_tables_out = await fetch_user_rating_update_tables_for_date(
                    target_user.id,
                    target_date_obj,
                    ranking_cfg.tables,
                    db,
                )
            else:
                aggregated_rating_payload = await compute_rating_updates_aggregated(
                    user_id=target_user.id,
                    ranking_tables=ranking_cfg.tables,
                    db=db,
                    target_date=target_date_obj,
                    excluded_dates=_rating_update_excluded_dates(target_user),
                )
                day_summary_out["rating_updates"] = aggregated_rating_payload.get("count") or 0
                rating_update_tables_out = aggregated_rating_payload.get("tables") or []

    return {
        "updates": [
            {
                "id": str(e.id),
                "fumen_sha256": e.fumen_sha256,
                "fumen_md5": e.fumen_md5,
                "fumen_hash_others": e.fumen_hash_others,
                "client_type": e.client_type,
                "clear_type": display_clear_type(e.clear_type, exscore=e.exscore, rate=e.rate),
                "rate": e.rate,
                "rank": e.rank,
                "min_bp": e.min_bp,
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
                "synced_at": e.synced_at.isoformat() if e.synced_at else None,
                "title": (
                    song_map.get(e.fumen_sha256 or "", {}).get("title")
                    or md5_song_map.get(e.fumen_md5 or "", {}).get("title")
                    or None
                ),
                "artist": (
                    song_map.get(e.fumen_sha256 or "", {}).get("artist")
                    or md5_song_map.get(e.fumen_md5 or "", {}).get("artist")
                    or None
                ),
                "difficulty_levels": sha256_to_levels.get(e.fumen_sha256 or "", []) if e.fumen_sha256 else [],
                "play_count": e.play_count,
                "is_stat_only": str(e.id) in stat_only_ids,
                "is_initial_sync": _is_initial_sync_record(e, target_user),
                "prev_play_count": (
                    (entry_prev.get(str(e.id)).play_count if entry_prev.get(str(e.id)) else None)
                    if date else None
                ),
            }
            for e in entries
        ],
        "day_summary": day_summary_out,
        "rating_update_tables": rating_update_tables_out,
    }


@router.get("/course-activity")
async def get_course_activity(
    year: int | None = Query(None, description="Year filter (mutually exclusive with days)"),
    days: int | None = Query(None, ge=1, le=730, description="Recent N days (mutually exclusive with year)"),
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    date: str | None = Query(None, description="YYYY-MM-DD — filter by a specific date"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return course clearing events for visualization overlays.

    Uses user_scores WHERE fumen_hash_others IS NOT NULL (course records merged in Phase 5).
    Provide year= for the whole year, days= for recent N days, or date=YYYY-MM-DD for a specific day.
    """
    target_user = await _resolve_target_user(user_id, current_user, db)
    effective_ts = func.coalesce(UserScore.recorded_at, UserScore.synced_at)

    # "First clear" = earliest record with clear_type >= 3 for a given (user, course, client_type).
    # Checks ALL records without sync exclusion so bulk-imported prior clears are not re-shown.
    earlier = aliased(UserScore)
    earlier_effective_ts = func.coalesce(earlier.recorded_at, earlier.synced_at)
    earlier_clear_exists = (
        select(earlier.id)
        .where(
            earlier.user_id == target_user.id,
            earlier.fumen_hash_others == UserScore.fumen_hash_others,
            earlier.client_type == UserScore.client_type,
            earlier.clear_type >= 3,
            earlier_effective_ts < effective_ts,
        )
        .correlate(UserScore)
        .exists()
    )

    filters = [
        UserScore.user_id == target_user.id,
        UserScore.fumen_hash_others.is_not(None),
        UserScore.clear_type >= 3,  # exclude NO PLAY / FAILED / ASSIST EASY
        ~earlier_clear_exists,      # only the first clear (not re-clears or record updates)
    ]

    if date:
        effective_date = cast(effective_ts, Date)
        filters.append(effective_date == date_cls.fromisoformat(date))
    elif year:
        start = datetime(year, 1, 1, tzinfo=UTC)
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
        filters.append(effective_ts >= start)
        filters.append(effective_ts < end)
    elif days:
        since = datetime.now(UTC) - timedelta(days=days)
        filters.append(effective_ts >= since)

    if client_type:
        filters.append(UserScore.client_type == client_type)
    filters.extend(_initial_sync_exclusion_filters(target_user))

    result = await db.execute(
        select(UserScore)
        .where(*filters)
        .order_by(effective_ts.asc())
    )
    rows = result.scalars().all()

    # Build course lookup indexes from active courses for hash matching.
    # LR2:       fumen_hash_others endswith concat(md5_list)
    # Beatoraja: fumen_hash_others == concat(sha256_list)  (only when sha256_list has no nulls)
    courses_result = await db.execute(
        select(Course).where(Course.is_active.is_(True))
    )
    all_courses = courses_result.scalars().all()

    # md5_concat → course (for LR2 suffix matching)
    lr2_course_index: dict[str, Course] = {}
    # sha256_concat → course (for Beatoraja exact matching)
    bea_course_index: dict[str, Course] = {}
    for c in all_courses:
        md5_list: list = c.md5_list or []
        if md5_list:
            joined_md5 = "".join(m for m in md5_list if m)
            if joined_md5:
                lr2_course_index[joined_md5] = c
        sha256_list: list = c.sha256_list or []
        # Only index when sha256_list is complete (no nulls) and matches md5_list length
        if sha256_list and None not in sha256_list and len(sha256_list) == len(md5_list):
            joined_sha256 = "".join(sha256_list)
            if joined_sha256:
                bea_course_index[joined_sha256] = c

    def _match_course(hash_val: str, client: str) -> Course | None:
        if not hash_val:
            return None
        if client == "lr2":
            for joined_md5, course in lr2_course_index.items():
                if hash_val.endswith(joined_md5):
                    return course
        elif client == "beatoraja":
            return bea_course_index.get(hash_val)
        return None

    out = []
    for e in rows:
        ts = e.recorded_at or e.synced_at
        if ts is None:
            continue
        course = _match_course(e.fumen_hash_others or "", e.client_type or "")
        if course is None:
            continue
        out.append({
            "date": ts.strftime("%Y-%m-%d"),
            "course_hash": e.fumen_hash_others,
            "clear_type": display_clear_type(e.clear_type, exscore=e.exscore, rate=e.rate),
            "client_type": e.client_type,
            "course_name": course.name,
            "dan_title": course.dan_title,
            "song_count": len(course.md5_list),
        })
    return out


@router.get("/grade-distribution")
async def get_grade_distribution(
    client_type: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get grade/clear type distribution for chart rendering.

    Uses best clear_type per unique fumen (sha256 or md5) to avoid counting
    multiple history rows for the same chart.
    """
    target_user = await _resolve_target_user(user_id, current_user, db)
    filters = [
        UserScore.user_id == target_user.id,
        UserScore.fumen_hash_others.is_(None),  # exclude course records
        or_(UserScore.fumen_sha256.is_not(None), UserScore.fumen_md5.is_not(None)),
    ]
    if client_type:
        filters.append(UserScore.client_type == client_type)

    result = await db.execute(
        select(
            func.coalesce(UserScore.fumen_sha256, UserScore.fumen_md5).label("fumen_key"),
            UserScore.clear_type,
            UserScore.exscore,
            UserScore.rate,
        ).where(*filters)
    )
    best_by_fumen: dict[str, int | None] = {}
    for row in result.mappings().all():
        clear_type = display_clear_type(row["clear_type"], exscore=row["exscore"], rate=row["rate"])
        key = row["fumen_key"]
        if key is None:
            continue
        current = best_by_fumen.get(key)
        if clear_type is None and key not in best_by_fumen:
            best_by_fumen[key] = None
        elif clear_type is not None and (current is None or clear_type > current):
            best_by_fumen[key] = clear_type

    counts: dict[int | None, int] = {}
    for clear_type in best_by_fumen.values():
        counts[clear_type] = counts.get(clear_type, 0) + 1

    distribution = [
        {"clear_type": clear_type, "count": count}
        for clear_type, count in sorted(counts.items(), key=lambda item: -1 if item[0] is None else item[0])
    ]

    return {"distribution": distribution}


@router.get("/score-trend")
async def get_score_trend(
    fumen_sha256: str = Query(..., description="SHA256 of the fumen"),
    client_type: str | None = Query(None),
    limit: int = Query(30, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get score trend for a specific fumen over time using user_scores history rows."""
    effective_ts = func.coalesce(UserScore.recorded_at, UserScore.synced_at)
    query = (
        select(UserScore)
        .where(
            UserScore.user_id == current_user.id,
            UserScore.fumen_sha256 == fumen_sha256,
        )
        .order_by(effective_ts.desc())
        .limit(limit)
    )
    if client_type:
        query = query.where(UserScore.client_type == client_type)

    result = await db.execute(query)
    histories = result.scalars().all()

    trend = [
        {
            "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None,
            "synced_at": h.synced_at.isoformat() if h.synced_at else None,
            "rate": h.rate,
            "rank": h.rank,
            "clear_type": display_clear_type(h.clear_type, exscore=h.exscore, rate=h.rate),
            "min_bp": h.min_bp,
        }
        for h in reversed(histories)
    ]

    return {"fumen_sha256": fumen_sha256, "trend": trend}


@router.get("/notes-activity")
async def get_notes_activity(
    days: int = Query(default=90, ge=7, le=730, description="Number of recent days"),
    date: str | None = Query(None, description="YYYY-MM-DD — return data for a single day only"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return per-day delta of play count from player_stats history.

    Uses LAG window function to compute sync-to-sync deltas per client_type,
    then aggregates across clients per day.

    Pass date=YYYY-MM-DD to return data for a specific sync day instead of recent N days.
    Response: [{"date": "YYYY-MM-DD", "plays": int}, ...]
    """
    h = UserPlayerStats
    lag_plays = func.lag(h.playcount).over(
        partition_by=[h.user_id, h.client_type],
        order_by=h.synced_at,
    )
    delta_plays = func.greatest(
        0, h.playcount - func.coalesce(lag_plays, h.playcount)
    )

    now = datetime.now(UTC).date()
    since = now - timedelta(days=days)

    subq = (
        select(
            cast(func.timezone("UTC", h.synced_at), Date).label("sync_date"),
            delta_plays.label("delta_plays"),
        )
        .where(
            h.user_id == current_user.id,
        )
        .subquery()
    )

    if date:
        date_filter = subq.c.sync_date == date_cls.fromisoformat(date)
    else:
        date_filter = subq.c.sync_date >= since

    result = await db.execute(
        select(
            subq.c.sync_date,
            func.sum(subq.c.delta_plays).label("plays"),
        )
        .where(date_filter)
        .group_by(subq.c.sync_date)
        .order_by(subq.c.sync_date)
    )
    return [
        {"date": str(row.sync_date), "plays": int(row.plays or 0)}
        for row in result.all()
    ]


@router.get("/table/{table_id}/clear-distribution")
async def get_table_clear_distribution(
    table_id: uuid.UUID,
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get per-level clear type distribution and per-song scores for a difficulty table.

    Returns:
        levels: per-level histogram data (clear_type → count)
        songs: per-song score data (title, level, clear_type, score_rate, min_bp)
        level_order: ordered list of level names from the table header
    """
    target_user = await _resolve_target_user(user_id, current_user, db)

    table_result = await db.execute(
        select(DifficultyTable).where(DifficultyTable.id == table_id)
    )
    table = table_result.scalar_one_or_none()
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")

    level_order: list[str] = table.level_order or []
    table_id_str = str(table_id)

    # Get fumens for this table via table_entries JSONB
    fumen_result = await db.execute(
        select(Fumen).where(
            Fumen.table_entries.contains([{"table_id": table_id_str}])
        )
    )
    fumens = fumen_result.scalars().all()

    if not fumens:
        return {
            "table_id": table_id_str,
            "table_name": table.name,
            "table_symbol": table.symbol or "",
            "client_type": client_type,
            "levels": [],
            "songs": [],
            "level_order": level_order,
        }

    # Build song list from fumens with their levels
    sha256_list, md5_list = [], []
    songs_data: list[dict[str, Any]] = []
    for f in fumens:
        level = ""
        for entry in (f.table_entries or []):
            if str(entry.get("table_id")) == table_id_str:
                level = str(entry.get("level", "")).strip()
                break
        songs_data.append({
            "sha256": f.sha256 or "",
            "md5": f.md5 or "",
            "title": f.title or "",
            "artist": f.artist or "",
            "level": level,
        })
        if f.sha256:
            sha256_list.append(f.sha256)
        if f.md5:
            md5_list.append(f.md5)

    # Build OR filter across both hash types
    hash_filter = []
    if sha256_list:
        hash_filter.append(UserScore.fumen_sha256.in_(sha256_list))
    if md5_list:
        hash_filter.append(UserScore.fumen_md5.in_(md5_list))

    if not hash_filter:
        return {
            "table_id": table_id_str,
            "table_name": table.name,
            "table_symbol": table.symbol or "",
            "client_type": client_type,
            "levels": [],
            "songs": [],
            "level_order": level_order,
        }

    score_filter = [
        UserScore.user_id == target_user.id,
        or_(*hash_filter),
        UserScore.fumen_hash_others.is_(None),  # exclude course records
    ]
    if client_type:
        score_filter.append(UserScore.client_type == client_type)

    scores_result = await db.execute(
        select(
            UserScore.fumen_sha256,
            UserScore.fumen_md5,
            UserScore.client_type,
            UserScore.clear_type,
            UserScore.exscore,
            UserScore.rate,
            UserScore.rank,
            UserScore.min_bp,
            UserScore.max_combo,
            UserScore.play_count,
            UserScore.options,
        ).where(*score_filter)
    )
    score_rows = scores_result.all()

    md5_to_sha256 = {
        fumen["md5"]: fumen["sha256"]
        for fumen in songs_data
        if fumen["md5"] and fumen["sha256"]
    }
    aggregate_map = _build_fumen_aggregate(
        list(score_rows),
        md5_to_sha256,
    )

    # Build song list and level histogram simultaneously
    songs_out: list[dict[str, Any]] = []
    level_counts: dict[str, dict[int, int]] = {}

    for s in songs_data:
        sha256 = s["sha256"]
        md5 = s["md5"]
        level = s["level"]
        score_data = aggregate_map.get(_canonical_fumen_key(sha256 or None, md5 or None, md5_to_sha256))
        clear_type: int = (
            score_data["current_state"]["clear_type"]
            if score_data and score_data["current_state"]["clear_type"] is not None
            else 0
        )

        if level not in level_counts:
            level_counts[level] = {}
        level_counts[level][clear_type] = level_counts[level].get(clear_type, 0) + 1

        ex_score = score_data["current_state"]["exscore"] if score_data else None
        play_count = score_data["play_count"] if score_data else None

        songs_out.append({
            "sha256": sha256,
            "title": s["title"],
            "artist": s["artist"],
            "level": level,
            "clear_type": clear_type,
            "rate": score_data["current_state"]["rate"] if score_data else None,
            "rank": score_data["current_state"]["rank"] if score_data else None,
            "min_bp": score_data["current_state"]["min_bp"] if score_data else None,
            "client_type": score_data["client_type"] if score_data else None,
            "source_client": score_data["source_client"] if score_data else None,
            "source_client_detail": score_data["source_client_detail"] if score_data else None,
            "ex_score": ex_score,
            "play_count": play_count,
            "options": score_data["options"] if score_data else None,
        })

    # Sort levels by level_order, then alphabetically for unknowns
    if level_order:
        sorted_levels = [lv for lv in level_order if lv in level_counts]
        sorted_levels += sorted(lv for lv in level_counts if lv not in level_order)
    else:
        sorted_levels = sorted(level_counts.keys())

    levels_out = [
        {"level": lv, "counts": {str(k): v for k, v in level_counts[lv].items()}}
        for lv in sorted_levels
    ]

    return {
        "table_id": table_id_str,
        "table_name": table.name,
        "table_symbol": table.symbol or "",
        "client_type": client_type,
        "levels": levels_out,
        "songs": songs_out,
        "level_order": level_order,
    }


# ── Shared helper: build course lookup indexes from active courses ─────────────

async def _build_course_indexes(db: AsyncSession) -> tuple[dict, dict, list]:
    """Build md5-concat and sha256-concat lookup indexes for course matching."""
    from app.models.course import Course
    courses_result = await db.execute(select(Course).where(Course.is_active.is_(True)))
    all_courses = courses_result.scalars().all()
    lr2_index: dict[str, Any] = {}
    bea_index: dict[str, Any] = {}
    for c in all_courses:
        md5_list: list = c.md5_list or []
        if md5_list:
            joined = "".join(m for m in md5_list if m)
            if joined:
                lr2_index[joined] = c
        sha256_list: list = c.sha256_list or []
        if sha256_list and None not in sha256_list and len(sha256_list) == len(md5_list):
            joined = "".join(sha256_list)
            if joined:
                bea_index[joined] = c
    return lr2_index, bea_index, all_courses


def _match_course_from_indexes(hash_val: str, client: str, lr2_idx: dict, bea_idx: dict) -> Any:
    if not hash_val:
        return None
    if client == "lr2":
        for joined_md5, course in lr2_idx.items():
            if hash_val.endswith(joined_md5):
                return course
    elif client == "beatoraja":
        return bea_idx.get(hash_val)
    return None


@router.get("/score-updates")
async def get_score_updates(
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    date: str | None = Query(None, description="YYYY-MM-DD — filter by effective date"),
    limit: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return per-field best score updates for visualization.

    Returns structured lists:
    - course_updates: course record bests
    - clear_type_updates: fumen clear_type improvements
    - exscore_updates: fumen exscore improvements
    - other_updates: max_combo / min_bp / play_count improvements

    For each update, the 'previous best' is determined by finding the most
    recent prior row for the same (fumen, client_type) with a lower/worse value.
    """
    target_user = await _resolve_target_user(user_id, current_user, db)
    effective_ts = func.coalesce(UserScore.recorded_at, UserScore.synced_at)
    hash_expr = func.coalesce(
        UserScore.fumen_sha256, UserScore.fumen_md5, UserScore.fumen_hash_others
    )

    # ── 1. Fetch most-recent row per (hash, client_type) ─────────────────────
    # Use ROW_NUMBER() to pick the latest row per (fumen_hash, client_type) group.
    base_filters = [UserScore.user_id == target_user.id]
    if client_type:
        base_filters.append(UserScore.client_type == client_type)
    base_filters.extend(_initial_sync_exclusion_filters(target_user))
    if date:
        effective_date = cast(func.timezone("UTC", effective_ts), Date)
        base_filters.append(effective_date == date_cls.fromisoformat(date))

    inner = (
        select(
            UserScore.id.label("score_id"),
            func.row_number().over(
                partition_by=[hash_expr, UserScore.client_type],
                order_by=effective_ts.desc(),
            ).label("rn"),
            effective_ts.label("ets"),
        )
        .where(*base_filters)
        .subquery("inner_ranked")
    )
    # date 지정 시: 해당 날짜의 모든 행을 반환 (상한 없음).
    # date 미지정 시: 최신 N개만 반환 (recent-updates 위젯용 페이지네이션).
    q = (
        select(inner.c.score_id)
        .where(inner.c.rn == 1)
        .order_by(inner.c.ets.desc())
    )
    if not date:
        q = q.limit(limit)
    latest_ids_result = await db.execute(q)
    best_ids = [row.score_id for row in latest_ids_result]

    if not best_ids:
        return {"clear_type_updates": [], "exscore_updates": [], "max_combo_updates": [], "min_bp_updates": [], "play_count_updates": []}

    best_result = await db.execute(
        select(UserScore)
        .where(UserScore.id.in_(best_ids))
        .order_by(effective_ts.desc())
    )
    best_rows = best_result.scalars().all()

    # ── 2. Separate course records from fumen records ─────────────────────────
    fumen_best = [r for r in best_rows if r.fumen_hash_others is None]
    course_best = [r for r in best_rows if r.fumen_hash_others is not None]

    # ── 3. Build hash sets for bulk lookups ───────────────────────────────────
    sha256s = [r.fumen_sha256 for r in fumen_best if r.fumen_sha256]
    md5s = [r.fumen_md5 for r in fumen_best if r.fumen_md5 and not r.fumen_sha256]

    # ── 4. Fumen metadata lookup ──────────────────────────────────────────────
    fumen_meta: dict[str, dict] = {}  # sha256 or md5 → {title, artist}
    md5_to_sha256: dict[str, str] = {}
    if sha256s:
        rows = await db.execute(
            select(Fumen.sha256, Fumen.md5, Fumen.title, Fumen.artist, Fumen.table_entries)
            .where(Fumen.sha256.in_(sha256s))
        )
        for r in rows.all():
            fumen_meta[r.sha256] = {"title": r.title, "artist": r.artist, "table_entries": r.table_entries or []}
            if r.md5 and r.sha256:
                md5_to_sha256[r.md5] = r.sha256
    if md5s:
        rows = await db.execute(
            select(Fumen.md5, Fumen.sha256, Fumen.title, Fumen.artist, Fumen.table_entries)
            .where(Fumen.md5.in_(md5s))
        )
        for r in rows.all():
            fumen_meta[r.md5] = {"title": r.title, "artist": r.artist, "table_entries": r.table_entries or []}
            if r.md5 and r.sha256:
                md5_to_sha256[r.md5] = r.sha256

    # ── 5. Build table_levels from favorite tables ────────────────────────────
    fav_result = await db.execute(
        select(UserFavoriteDifficultyTable.table_id, UserFavoriteDifficultyTable.display_order)
        .where(UserFavoriteDifficultyTable.user_id == target_user.id)
    )
    fav_rows = fav_result.all()
    fav_table_ids_str: set[str] = {str(r[0]) for r in fav_rows}
    fav_table_order: dict[str, int] = {str(r[0]): r[1] for r in fav_rows}

    table_info: dict[str, dict[str, str]] = {}
    if fav_table_ids_str:
        tsym_result = await db.execute(
            select(DifficultyTable.id, DifficultyTable.symbol, DifficultyTable.slug)
            .where(DifficultyTable.id.in_([uuid.UUID(tid) for tid in fav_table_ids_str]))
        )
        table_info = {str(r.id): {"symbol": r.symbol or "", "slug": r.slug or ""} for r in tsym_result.all()}

    def _get_table_levels(hash_key: str | None) -> list[dict[str, str]]:
        if not hash_key or hash_key not in fumen_meta:
            return []
        levels: list[dict[str, str]] = []
        seen: set[tuple] = set()
        for entry in fumen_meta[hash_key].get("table_entries", []):
            tid = str(entry.get("table_id", ""))
            if tid not in fav_table_ids_str:
                continue
            info = table_info.get(tid, {"symbol": "", "slug": ""})
            sym = info["symbol"]
            slug = info["slug"]
            lv = str(entry.get("level", ""))
            key = (sym, lv)
            if key not in seen:
                seen.add(key)
                levels.append({"symbol": sym, "slug": slug, "level": lv, "_tid": tid})
        levels.sort(key=lambda x: fav_table_order.get(x["_tid"], 999))
        return [{"symbol": lv["symbol"], "slug": lv["slug"], "level": lv["level"]} for lv in levels]

    # ── 6. Bulk fetch previous rows for fumen records ─────────────────────────
    # For each best row: find the most recent prior row in same (fumen_hash, client_type)
    # Strategy: fetch all rows for the relevant hashes, sorted by recorded_at,
    # then find predecessor in Python
    prev_rows_map: dict[tuple, list] = {}  # (sha256|md5|hash_others, client_type) → sorted rows
    if fumen_best:
        prev_conditions = []
        if sha256s:
            prev_conditions.append(UserScore.fumen_sha256.in_(sha256s))
        if md5s:
            prev_conditions.append(
                (UserScore.fumen_md5.in_(md5s)) & UserScore.fumen_sha256.is_(None)
            )
        if prev_conditions:
            combined = prev_conditions[0]
            for c in prev_conditions[1:]:
                combined = combined | c
            prev_result = await db.execute(
                select(UserScore)
                .where(
                    UserScore.user_id == target_user.id,
                    UserScore.fumen_hash_others.is_(None),
                    combined,
                    *( [UserScore.client_type == client_type] if client_type else [] ),
                )
                .order_by(effective_ts.asc())
            )
            for r in prev_result.scalars().all():
                hash_key = r.fumen_sha256 or r.fumen_md5
                group_key = (hash_key, r.client_type)
                prev_rows_map.setdefault(group_key, []).append(r)

    aggregate_map = _build_fumen_aggregate(
        [row for rows in prev_rows_map.values() for row in rows],
        md5_to_sha256,
    )

    # ── 6b. Bulk fetch previous rows for course records ───────────────────────
    course_hash_set = [r.fumen_hash_others for r in course_best if r.fumen_hash_others]
    course_prev_rows_map: dict[tuple, list] = {}
    if course_hash_set:
        cprev_result = await db.execute(
            select(UserScore)
            .where(
                UserScore.user_id == target_user.id,
                UserScore.fumen_hash_others.in_(course_hash_set),
                *( [UserScore.client_type == client_type] if client_type else [] ),
            )
            .order_by(effective_ts.asc())
        )
        for r in cprev_result.scalars().all():
            group_key = (r.fumen_hash_others, r.client_type)
            course_prev_rows_map.setdefault(group_key, []).append(r)

    # ── 7. Course index ────────────────────────────────────────────────────────
    lr2_idx, bea_idx, _ = await _build_course_indexes(db)

    # ── 8. Build output lists ─────────────────────────────────────────────────
    clear_type_updates: list[dict] = []
    exscore_updates: list[dict] = []
    max_combo_updates: list[dict] = []
    min_bp_updates: list[dict] = []
    play_count_updates: list[dict] = []

    def _ts(row: UserScore) -> str | None:
        ts = row.recorded_at or row.synced_at
        return ts.isoformat() if ts else None

    # Course updates (is_course=True) — clear_type / exscore / play_count
    for r in course_best:
        if r.clear_type is None and r.exscore is None and r.play_count is None:
            continue
        course = _match_course_from_indexes(r.fumen_hash_others or "", r.client_type or "", lr2_idx, bea_idx)
        if course is None:
            continue
        cprev = _find_course_prev_row(r, course_prev_rows_map)
        all_course_rows = course_prev_rows_map.get((r.fumen_hash_others, r.client_type), [])
        all_rows = all_course_rows if any(row.id == r.id for row in all_course_rows) else all_course_rows + [r]
        best_clear = max(
            (
                display_clear_type(row.clear_type, exscore=row.exscore, rate=row.rate)
                for row in all_rows
                if row.clear_type is not None
            ),
            default=None,
        )
        best_exscore = max((row.exscore for row in all_rows if row.exscore is not None), default=None)
        best_rate = max((row.rate for row in all_rows if row.rate is not None), default=None)
        best_rank_row = max((row for row in all_rows if row.exscore is not None), key=lambda row: row.exscore or 0, default=None)
        best_rank = best_rank_row.rank if best_rank_row else None
        best_min_bp = min((row.min_bp for row in all_rows if row.min_bp is not None), default=None)
        best_max_combo = max((row.max_combo for row in all_rows if row.max_combo is not None), default=None)
        course_base = {
            "fumen_sha256": None,
            "fumen_md5": None,
            "title": course.name,
            "artist": None,
            "table_levels": [],
            "client_type": r.client_type,
            "recorded_at": _ts(r),
            "is_course": True,
            "is_new_play": cprev is None,
            "course_name": course.name,
            "dan_title": course.dan_title or "",
            "options": r.options,
            "source_client": CLIENT_LABEL.get(r.client_type or "", (r.client_type or "").upper()) if r.client_type else None,
            "source_client_detail": None,
            "current_state": {
                "clear_type": best_clear,
                "exscore": best_exscore,
                "rate": best_rate,
                "rank": best_rank,
                "min_bp": best_min_bp,
                "max_combo": best_max_combo,
            },
        }
        if r.clear_type is not None:
            prev_ct = display_clear_type(cprev.clear_type, exscore=cprev.exscore, rate=cprev.rate) if cprev else None
            new_ct = display_clear_type(r.clear_type, exscore=r.exscore, rate=r.rate)
            if (new_ct or 0) > (prev_ct or 0):
                clear_type_updates.append({**course_base, "prev_clear_type": prev_ct, "new_clear_type": new_ct})
        if r.exscore is not None:
            prev_ex = cprev.exscore if cprev else None
            prev_rank = cprev.rank if cprev else None
            prev_rate = cprev.rate if cprev else None
            if (r.exscore or 0) > (prev_ex or 0):
                exscore_updates.append({**course_base, "prev_exscore": prev_ex, "new_exscore": r.exscore, "prev_rank": prev_rank, "new_rank": r.rank, "prev_rate": prev_rate, "new_rate": r.rate, "best_min_bp": r.min_bp})
        if r.play_count is not None:
            prev_pc = cprev.play_count if cprev else None
            if prev_pc is None or r.play_count > prev_pc:
                play_count_updates.append({
                    **course_base,
                    "prev_play_count": prev_pc,
                    "new_play_count": r.play_count,
                    "is_initial_sync": _is_initial_sync_record(r, target_user),
                })

    # Fumen updates (is_course=False)
    processed_ct: set = set()
    processed_ex: set = set()
    processed_mc: set = set()
    processed_bp: set = set()
    processed_pc: set = set()

    for r in fumen_best:
        hash_key = r.fumen_sha256 or r.fumen_md5
        fk = (hash_key, r.client_type)
        meta = fumen_meta.get(hash_key or "", {})
        table_levels = _get_table_levels(hash_key)
        prev = _find_prev_row(r, prev_rows_map)
        aggregate_key = _canonical_fumen_key(r.fumen_sha256, r.fumen_md5, md5_to_sha256)
        aggregate = aggregate_map.get(aggregate_key, {})
        current_state = aggregate.get("current_state", {})
        current_best_min_bp = current_state.get("min_bp")

        base = {
            "fumen_sha256": r.fumen_sha256,
            "fumen_md5": r.fumen_md5,
            "title": meta.get("title"),
            "artist": meta.get("artist"),
            "table_levels": table_levels,
            "client_type": aggregate.get("client_type") if aggregate else r.client_type,
            "recorded_at": _ts(r),
            "is_course": False,
            "is_new_play": prev is None,
            "course_name": None,
            "dan_title": None,
            "options": aggregate.get("options") if aggregate else r.options,
            "source_client": aggregate.get("source_client"),
            "source_client_detail": aggregate.get("source_client_detail"),
            "current_state": current_state if current_state else {
                "clear_type": display_clear_type(r.clear_type, exscore=r.exscore, rate=r.rate),
                "exscore": r.exscore,
                "rate": r.rate,
                "rank": r.rank,
                "min_bp": current_best_min_bp,
                "max_combo": r.max_combo,
            },
        }

        if r.clear_type is not None and fk not in processed_ct:
            processed_ct.add(fk)
            prev_ct = display_clear_type(prev.clear_type, exscore=prev.exscore, rate=prev.rate) if prev else None
            new_ct = display_clear_type(r.clear_type, exscore=r.exscore, rate=r.rate)
            if (new_ct or 0) > (prev_ct or 0):
                clear_type_updates.append({**base, "prev_clear_type": prev_ct, "new_clear_type": new_ct, "best_min_bp": current_best_min_bp})

        if r.exscore is not None and fk not in processed_ex:
            processed_ex.add(fk)
            prev_ex = prev.exscore if prev else None
            prev_rank = prev.rank if prev else None
            prev_rate = prev.rate if prev else None
            if (r.exscore or 0) > (prev_ex or 0):
                exscore_updates.append({**base, "prev_exscore": prev_ex, "new_exscore": r.exscore, "prev_rank": prev_rank, "new_rank": r.rank, "prev_rate": prev_rate, "new_rate": r.rate, "best_min_bp": current_best_min_bp})

        if r.max_combo is not None and fk not in processed_mc:
            processed_mc.add(fk)
            prev_mc = prev.max_combo if prev else None
            if (r.max_combo or 0) > (prev_mc or 0):
                max_combo_updates.append({**base, "prev_max_combo": prev_mc, "new_max_combo": r.max_combo})

        if r.min_bp is not None and fk not in processed_bp:
            processed_bp.add(fk)
            prev_bp = prev.min_bp if prev else None
            if prev_bp is None or r.min_bp < prev_bp:
                min_bp_updates.append({**base, "prev_min_bp": prev_bp, "new_min_bp": r.min_bp})

        if r.play_count is not None and fk not in processed_pc:
            processed_pc.add(fk)
            prev_pc = prev.play_count if prev else None
            if prev_pc is None or r.play_count > prev_pc:
                play_count_updates.append({
                    **base,
                    "prev_play_count": prev_pc,
                    "new_play_count": r.play_count,
                    "is_initial_sync": _is_initial_sync_record(r, target_user),
                })

    return {
        "clear_type_updates": clear_type_updates,
        "exscore_updates": exscore_updates,
        "max_combo_updates": max_combo_updates,
        "min_bp_updates": min_bp_updates,
        "play_count_updates": play_count_updates,
    }
