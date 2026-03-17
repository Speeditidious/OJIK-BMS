"""Play analysis data endpoints."""
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, cast, func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.course import CourseScoreHistory
from app.models.score import (
    ScoreHistory,
    UserPlayerStats,
    UserPlayerStatsHistory,
    UserScore,
)
from app.models.song import Song
from app.models.table import DifficultyTable, UserFavoriteTable
from app.models.user import User

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/summary")
async def get_play_summary(
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a summary of the current user's play statistics.

    Pass client_type=lr2 or client_type=beatoraja to filter by game client.
    Omit client_type to get combined stats across all clients.
    """
    base_filter = [UserScore.user_id == current_user.id]
    if client_type:
        base_filter.append(UserScore.client_type == client_type)

    result = await db.execute(
        select(
            func.count(UserScore.id).label("total_scores"),
            func.sum(UserScore.play_count).label("total_play_count"),
            func.sum(UserScore.hit_notes).label("total_notes"),
        ).where(*base_filter)
    )
    row = result.one()

    # Use player table totals (exact) when available; fall back to per-song sum.
    # Also use UserPlayerStats.synced_at as the authoritative last-sync time —
    # UserScore.synced_at is set only at initial insert and never updated thereafter.
    stats_filter = [UserPlayerStats.user_id == current_user.id]
    if client_type:
        stats_filter.append(UserPlayerStats.client_type == client_type)
    pstats_result = await db.execute(
        select(
            func.sum(UserPlayerStats.total_notes_hit),
            func.sum(UserPlayerStats.total_play_count),
            func.max(UserPlayerStats.synced_at),
        ).where(*stats_filter)
    )
    pstats = pstats_result.one()

    total_notes = int(pstats[0] or 0) or int(row.total_notes or 0)
    total_play_count = int(pstats[1] or 0) or int(row.total_play_count or 0)
    last_synced_at = pstats[2]

    # First sync date per client type — always unfiltered (informational)
    first_sync_result = await db.execute(
        select(UserScore.client_type, func.min(UserScore.synced_at))
        .where(UserScore.user_id == current_user.id)
        .group_by(UserScore.client_type)
    )
    first_synced_by_client = {
        row[0]: row[1].isoformat() if row[1] else None
        for row in first_sync_result.all()
    }

    return {
        "total_scores": row.total_scores or 0,
        "total_play_count": total_play_count,
        "total_notes": total_notes,
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        "first_synced_by_client": first_synced_by_client,
    }


@router.get("/heatmap")
async def get_activity_heatmap(
    year: int = Query(default=0, description="Year (0 = current year)"),
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return per-day record update counts for the given year.

    Uses played_at only (actual in-game play timestamp).
    Entries where played_at is NULL are excluded to avoid data spikes.
    Returns {date, value} for days with value > 0.
    """
    target_year = year if year > 0 else datetime.now(UTC).year
    start = datetime(target_year, 1, 1, tzinfo=UTC)
    end = datetime(target_year + 1, 1, 1, tzinfo=UTC)

    # Require played_at to be set — LR2 records have played_at=NULL (no per-play date in
    # score.db) and must be excluded here to avoid a spike on the first sync date.
    song_q = (
        select(cast(ScoreHistory.played_at, Date).label("day"))
        .where(
            ScoreHistory.user_id == current_user.id,
            ScoreHistory.played_at.is_not(None),
            ScoreHistory.played_at >= start,
            ScoreHistory.played_at < end,
        )
    )
    if client_type:
        song_q = song_q.where(ScoreHistory.client_type == client_type)

    course_q = (
        select(cast(CourseScoreHistory.played_at, Date).label("day"))
        .where(
            CourseScoreHistory.user_id == current_user.id,
            CourseScoreHistory.played_at.is_not(None),
            CourseScoreHistory.played_at >= start,
            CourseScoreHistory.played_at < end,
        )
    )
    if client_type:
        course_q = course_q.where(CourseScoreHistory.client_type == client_type)

    combined = union_all(song_q, course_q).subquery()
    result = await db.execute(
        select(combined.c.day, func.count().label("cnt"))
        .group_by(combined.c.day)
        .order_by(combined.c.day)
    )
    rows = result.all()

    return {
        "year": target_year,
        "data": [{"date": str(r.day), "value": r.cnt} for r in rows],
    }


@router.get("/activity")
async def get_activity_bar(
    days: int = Query(default=30, ge=7, le=365, description="Number of recent days"),
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return daily record update counts for the last N days.
    Uses played_at only (actual in-game play time).
    Entries where played_at is NULL are excluded to avoid data spikes.
    """
    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    # Require played_at to be set — LR2 records have played_at=NULL (no per-play date in
    # score.db) and must be excluded here to avoid a spike on the first sync date.
    song_q = (
        select(cast(ScoreHistory.played_at, Date).label("day"))
        .where(
            ScoreHistory.user_id == current_user.id,
            ScoreHistory.played_at.is_not(None),
            ScoreHistory.played_at >= since,
        )
    )
    if client_type:
        song_q = song_q.where(ScoreHistory.client_type == client_type)

    course_q = (
        select(cast(CourseScoreHistory.played_at, Date).label("day"))
        .where(
            CourseScoreHistory.user_id == current_user.id,
            CourseScoreHistory.played_at.is_not(None),
            CourseScoreHistory.played_at >= since,
        )
    )
    if client_type:
        course_q = course_q.where(CourseScoreHistory.client_type == client_type)

    combined = union_all(song_q, course_q).subquery()
    result = await db.execute(
        select(combined.c.day, func.count().label("updates"))
        .group_by(combined.c.day)
        .order_by(combined.c.day)
    )
    rows = result.all()

    return {
        "days": days,
        "data": [{"date": str(r.day), "updates": r.updates} for r in rows],
    }


@router.get("/recent-updates")
async def get_recent_updates(
    limit: int = Query(default=20, ge=1, le=100),
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    date: str | None = Query(None, description="YYYY-MM-DD — filter by played_at date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return recent score improvement history, ordered by actual play time.

    Includes song title/subtitle/artist, difficulty level badges from the user's
    favorite tables, and score_rate for Rank display.
    Pass date=YYYY-MM-DD to filter by played_at date (returns up to 200 entries).
    """
    play_ts = func.coalesce(ScoreHistory.played_at, ScoreHistory.recorded_at)
    recent_filter = [ScoreHistory.user_id == current_user.id]
    if client_type:
        recent_filter.append(ScoreHistory.client_type == client_type)
    if date:
        recent_filter.append(func.date(ScoreHistory.played_at) == date)
        effective_limit = 200
    else:
        effective_limit = limit

    result = await db.execute(
        select(ScoreHistory)
        .where(*recent_filter)
        .order_by(play_ts.desc())
        .limit(effective_limit)
    )
    entries = result.scalars().all()

    # Collect hashes to look up song metadata (sha256 preferred, md5 as fallback for LR2)
    sha256s = [e.song_sha256 for e in entries if e.song_sha256]
    # Include md5 for ALL entries so sha256-lookup failures can fall back to md5
    md5s = [e.song_md5 for e in entries if e.song_md5]

    # song_map keyed by sha256; md5_song_map keyed by md5
    song_map: dict[str, Any] = {}
    md5_song_map: dict[str, Any] = {}
    if sha256s:
        songs_result = await db.execute(
            select(Song.sha256, Song.title, Song.subtitle, Song.artist).where(
                Song.sha256.in_(sha256s)
            )
        )
        for row in songs_result.all():
            song_map[row.sha256] = {
                "title": row.title,
                "subtitle": row.subtitle,
                "artist": row.artist,
            }
    if md5s:
        md5_songs_result = await db.execute(
            select(Song.md5, Song.title, Song.subtitle, Song.artist).where(
                Song.md5.in_(md5s)
            )
        )
        for row in md5_songs_result.all():
            md5_song_map[row.md5] = {
                "title": row.title,
                "subtitle": row.subtitle,
                "artist": row.artist,
            }

    # Build sha256 → [{symbol, level}] map from user's favorite tables
    sha256_to_levels: dict[str, list[dict[str, str]]] = {}
    sha256_to_levels_seen: dict[str, set] = {}
    if sha256s:
        fav_result = await db.execute(
            select(UserFavoriteTable.table_id).where(
                UserFavoriteTable.user_id == current_user.id
            )
        )
        fav_table_ids = [r[0] for r in fav_result.all()]
        if fav_table_ids:
            tables_result = await db.execute(
                select(DifficultyTable.symbol, DifficultyTable.table_data).where(
                    DifficultyTable.id.in_(fav_table_ids)
                )
            )
            sha256_set = set(sha256s)
            for table_row in tables_result.all():
                symbol = table_row.symbol or ""
                table_data = table_row.table_data or {}
                for song in table_data.get("songs", []):
                    s256 = song.get("sha256", "")
                    if s256 and s256 in sha256_set:
                        level = str(song.get("level", ""))
                        key = (symbol, level)
                        if key not in sha256_to_levels_seen.setdefault(s256, set()):
                            sha256_to_levels_seen[s256].add(key)
                            sha256_to_levels.setdefault(s256, []).append({"symbol": symbol, "level": level})

    return {
        "updates": [
            {
                "id": str(e.id),
                "song_sha256": e.song_sha256,
                "song_md5": e.song_md5,
                "client_type": e.client_type,
                "clear_type": e.clear_type,
                "old_clear_type": e.old_clear_type,
                "score": e.score,
                "old_score": e.old_score,
                "score_rate": e.score_rate if e.score_rate is not None else e.score,
                "old_score_rate": e.old_score,
                "min_bp": e.min_bp,
                "old_min_bp": e.old_min_bp,
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
                "played_at": e.played_at.isoformat() if e.played_at else None,
                "sync_date": e.sync_date.isoformat() if e.sync_date else None,
                "title": (
                    song_map.get(e.song_sha256 or "", {}).get("title")
                    or md5_song_map.get(e.song_md5 or "", {}).get("title")
                    or None
                ),
                "subtitle": (
                    song_map.get(e.song_sha256 or "", {}).get("subtitle")
                    or md5_song_map.get(e.song_md5 or "", {}).get("subtitle")
                    or None
                ),
                "artist": (
                    song_map.get(e.song_sha256 or "", {}).get("artist")
                    or md5_song_map.get(e.song_md5 or "", {}).get("artist")
                    or None
                ),
                "difficulty_levels": sha256_to_levels.get(e.song_sha256 or "", []) if e.song_sha256 else [],
            }
            for e in entries
        ]
    }


@router.get("/grade-distribution")
async def get_grade_distribution(
    client_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get grade/clear type distribution for chart rendering."""
    query = select(UserScore.clear_type, func.count(UserScore.id)).where(
        UserScore.user_id == current_user.id
    )
    if client_type:
        query = query.where(UserScore.client_type == client_type)

    query = query.group_by(UserScore.clear_type).order_by(UserScore.clear_type)
    result = await db.execute(query)

    distribution = [
        {"clear_type": row[0], "count": row[1]}
        for row in result.all()
    ]

    return {"distribution": distribution}


@router.get("/score-trend")
async def get_score_trend(
    song_sha256: str = Query(..., description="SHA256 of the song"),
    client_type: str | None = Query(None),
    limit: int = Query(30, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get score trend for a specific song over time."""
    query = (
        select(ScoreHistory)
        .where(
            ScoreHistory.user_id == current_user.id,
            ScoreHistory.song_sha256 == song_sha256,
        )
        .order_by(ScoreHistory.recorded_at.desc())
        .limit(limit)
    )
    if client_type:
        query = query.where(ScoreHistory.client_type == client_type)

    result = await db.execute(query)
    histories = result.scalars().all()

    trend = [
        {
            "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None,
            "played_at": h.played_at.isoformat() if h.played_at else None,
            "score": h.score,
            "clear_type": h.clear_type,
            "min_bp": h.min_bp,
        }
        for h in reversed(histories)
    ]

    return {"song_sha256": song_sha256, "trend": trend}


@router.get("/notes-activity")
async def get_notes_activity(
    days: int = Query(default=90, ge=7, le=730, description="Number of recent days"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return per-day delta of notes hit and play count from player_stats history.

    Uses LAG window function to compute sync-to-sync deltas per client_type,
    then aggregates across clients per day.

    Response: [{"date": "YYYY-MM-DD", "notes": int, "plays": int}, ...]
    """
    h = UserPlayerStatsHistory
    lag_notes = func.lag(h.total_notes_hit).over(
        partition_by=[h.user_id, h.client_type],
        order_by=h.sync_date,
    )
    lag_plays = func.lag(h.total_play_count).over(
        partition_by=[h.user_id, h.client_type],
        order_by=h.sync_date,
    )
    delta_notes = func.greatest(
        0, h.total_notes_hit - func.coalesce(lag_notes, h.total_notes_hit)
    )
    delta_plays = func.greatest(
        0, h.total_play_count - func.coalesce(lag_plays, h.total_play_count)
    )

    now = datetime.now(UTC).date()
    since = now - timedelta(days=days)

    subq = (
        select(
            h.sync_date.label("sync_date"),
            delta_notes.label("delta_notes"),
            delta_plays.label("delta_plays"),
        )
        .where(
            h.user_id == current_user.id,
        )
        .subquery()
    )

    result = await db.execute(
        select(
            subq.c.sync_date,
            func.sum(subq.c.delta_notes).label("notes"),
            func.sum(subq.c.delta_plays).label("plays"),
        )
        .where(subq.c.sync_date >= since)
        .group_by(subq.c.sync_date)
        .order_by(subq.c.sync_date)
    )
    return [
        {"date": str(row.sync_date), "notes": int(row.notes or 0), "plays": int(row.plays or 0)}
        for row in result.all()
    ]


@router.get("/table/{table_id}/clear-distribution")
async def get_table_clear_distribution(
    table_id: int,
    client_type: str | None = Query(None, description="Filter by client: lr2, beatoraja"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get per-level clear type distribution and per-song scores for a difficulty table.

    Returns:
        levels: per-level histogram data (clear_type → count)
        songs: per-song score data (title, level, clear_type, score_rate, min_bp)
        level_order: ordered list of level names from the table header
    """
    table_result = await db.execute(
        select(DifficultyTable).where(DifficultyTable.id == table_id)
    )
    table = table_result.scalar_one_or_none()
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")

    if not table.table_data or "songs" not in table.table_data:
        return {
            "table_id": table_id,
            "table_name": table.name,
            "table_symbol": table.symbol or "",
            "client_type": client_type,
            "levels": [],
            "songs": [],
            "level_order": [],
        }

    songs_data: list[dict[str, Any]] = table.table_data["songs"]
    level_order: list[str] = table.table_data.get("level_order") or []

    sha256_list, md5_list = [], []
    for s in songs_data:
        if s.get("sha256"):
            sha256_list.append(s["sha256"])
        if s.get("md5"):
            md5_list.append(s["md5"])

    if not sha256_list and not md5_list:
        return {
            "table_id": table_id,
            "table_name": table.name,
            "table_symbol": table.symbol or "",
            "client_type": client_type,
            "levels": [],
            "songs": [],
            "level_order": level_order,
        }

    # Build OR filter across both hash types
    hash_filter = []
    if sha256_list:
        hash_filter.append(UserScore.song_sha256.in_(sha256_list))
    if md5_list:
        hash_filter.append(UserScore.song_md5.in_(md5_list))

    score_filter = [
        UserScore.user_id == current_user.id,
        or_(*hash_filter),
    ]
    if client_type:
        score_filter.append(UserScore.client_type == client_type)

    scores_result = await db.execute(
        select(
            UserScore.song_sha256,
            UserScore.song_md5,
            UserScore.client_type,
            UserScore.clear_type,
            UserScore.score_rate,
            UserScore.min_bp,
            UserScore.judgments,
            UserScore.options,
        ).where(*score_filter)
    )
    score_rows = scores_result.all()

    # Pick best score per hash (highest clear_type wins), keyed by sha256 and md5
    score_map_by_sha256: dict[str, dict[str, Any]] = {}
    score_map_by_md5: dict[str, dict[str, Any]] = {}

    def _better(existing: dict[str, Any] | None, new_entry: dict[str, Any]) -> bool:
        return existing is None or (new_entry["clear_type"] or 0) > (existing["clear_type"] or 0)

    for row in score_rows:
        entry = {
            "clear_type": row.clear_type,
            "score_rate": row.score_rate,
            "min_bp": row.min_bp,
            "client_type": row.client_type,
            "judgments": row.judgments,
            "options": row.options,
        }
        if row.song_sha256:
            if _better(score_map_by_sha256.get(row.song_sha256), entry):
                score_map_by_sha256[row.song_sha256] = entry
        if row.song_md5:
            if _better(score_map_by_md5.get(row.song_md5), entry):
                score_map_by_md5[row.song_md5] = entry

    # Build song list and level histogram simultaneously
    songs_out: list[dict[str, Any]] = []
    level_counts: dict[str, dict[int, int]] = {}

    for s in songs_data:
        sha256 = s.get("sha256") or ""
        md5 = s.get("md5") or ""
        level = str(s.get("level", "")).strip()
        # Merge sha256 and md5 maps, picking the better clear_type when both exist
        sha256_entry = score_map_by_sha256.get(sha256) if sha256 else None
        md5_entry = score_map_by_md5.get(md5) if md5 else None
        if sha256_entry is None:
            score_data = md5_entry
        elif md5_entry is None:
            score_data = sha256_entry
        else:
            # Both exist — pick the one with higher clear_type
            score_data = sha256_entry if _better(md5_entry, sha256_entry) else md5_entry
        clear_type: int = (
            score_data["clear_type"]
            if score_data and score_data["clear_type"] is not None
            else 0
        )

        if level not in level_counts:
            level_counts[level] = {}
        level_counts[level][clear_type] = level_counts[level].get(clear_type, 0) + 1

        # Compute EX Score from judgments (pgreat*2 + great)
        ex_score: int | None = None
        if score_data and score_data.get("judgments"):
            j = score_data["judgments"]
            ex_score = j.get("pgreat", 0) * 2 + j.get("great", 0)

        songs_out.append({
            "sha256": sha256,
            "title": s.get("title") or "",
            "artist": s.get("artist") or "",
            "level": level,
            "clear_type": clear_type,
            "score_rate": score_data["score_rate"] if score_data else None,
            "min_bp": score_data["min_bp"] if score_data else None,
            "client_type": score_data["client_type"] if score_data else None,
            "ex_score": ex_score,
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
        "table_id": table_id,
        "table_name": table.name,
        "table_symbol": table.symbol or "",
        "client_type": client_type,
        "levels": levels_out,
        "songs": songs_out,
        "level_order": level_order,
    }
