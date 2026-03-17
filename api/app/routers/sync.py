"""Local agent synchronization endpoints."""
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.course import Course, CourseScoreHistory, UserCourseScore
from app.models.score import (
    ScoreHistory,
    UserPlayerStats,
    UserPlayerStatsHistory,
    UserScore,
)
from app.models.song import Song, UserOwnedSong
from app.models.user import User

router = APIRouter(prefix="/sync", tags=["sync"])

# Judgment keys that represent actual note hits (excl. ghost/miss inputs)
_LR2_HIT_KEYS = ["pgreat", "great", "good", "bad"]
_BT_HIT_KEYS = ["ep", "lp", "eg", "lg", "egd", "lgd", "ebd", "lbd", "epr", "lpr"]


def _notes_per_play(judgments: dict | None) -> int:
    """Return the per-play hit note count from best-score judgments."""
    if not judgments:
        return 0
    return sum(judgments.get(k, 0) for k in _LR2_HIT_KEYS + _BT_HIT_KEYS)


def _has_change(existing: UserScore, item: "ScoreSyncItem") -> bool:
    """Return True if any tracked field has changed since the last sync."""
    return (
        (item.clear_type is not None and item.clear_type != existing.clear_type)
        or (item.score_rate is not None and item.score_rate != existing.score_rate)
        or (item.max_combo is not None and item.max_combo != existing.max_combo)
        or (item.min_bp is not None and item.min_bp != existing.min_bp)
        or item.clear_count > existing.clear_count
    )


class ScoreSyncItem(BaseModel):
    song_sha256: str | None = None
    song_md5: str | None = None
    client_type: str  # lr2 / beatoraja / qwilight
    clear_type: int | None = None
    score_rate: float | None = None
    max_combo: int | None = None
    min_bp: int | None = None
    judgments: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    play_count: int = 0
    clear_count: int = 0
    played_at: datetime | None = None


class OwnedSongItem(BaseModel):
    song_md5: str | None = None
    song_sha256: str
    title: str | None = None
    artist: str | None = None
    subartist: str | None = None
    subtitle: str | None = None
    bpm: float | None = None


class PlayerStats(BaseModel):
    client_type: str
    total_notes_hit: int
    total_play_count: int | None = None


class CourseSyncItem(BaseModel):
    course_hash: str
    client_type: str
    clear_type: int | None = None
    score_rate: float | None = None
    max_combo: int | None = None
    min_bp: int | None = None
    play_count: int = 0
    clear_count: int = 0
    played_at: datetime | None = None
    song_hashes: list[dict[str, Any]] = []


class ScoreLogItem(BaseModel):
    """Single Beatoraja scorelog entry for backfilling score_history."""
    song_sha256: str
    client_type: str
    clear_type: int | None = None
    max_combo: int | None = None
    min_bp: int | None = None
    played_at: datetime


class SyncRequest(BaseModel):
    scores: list[ScoreSyncItem] = []
    owned_songs: list[OwnedSongItem] = []
    player_stats: list[PlayerStats] = []
    courses: list[CourseSyncItem] = []
    score_log: list[ScoreLogItem] = []


class SyncResponse(BaseModel):
    synced_scores: int
    synced_songs: int
    synced_courses: int = 0
    synced_score_log: int = 0
    errors: list[str] = []


@router.post("/", response_model=SyncResponse)
async def sync_data(
    payload: SyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """
    Bulk upsert scores and owned songs from the local agent.

    Uses a single pre-fetch query per batch to avoid N+1 queries.
    Only updates existing scores when the new data is an improvement.
    """
    errors: list[str] = []
    synced_scores = 0
    synced_songs = 0
    synced_courses = 0
    synced_score_log = 0
    now = datetime.now(UTC)

    # Upsert owned songs FIRST so that Song table has MD5↔SHA256 mappings
    # before score processing tries to resolve md5 → sha256.
    if payload.owned_songs:
        try:
            seen_sha256: set[str] = set()
            song_rows = []
            song_meta_rows = []
            for song_item in payload.owned_songs:
                if song_item.song_sha256 not in seen_sha256:
                    seen_sha256.add(song_item.song_sha256)
                    song_rows.append({
                        "user_id": current_user.id,
                        "song_md5": song_item.song_md5,
                        "song_sha256": song_item.song_sha256,
                        "synced_at": now,
                    })
                    # Always create Song row for MD5↔SHA256 mapping,
                    # even when title/artist are missing from BMS header parsing.
                    song_meta_rows.append({
                        "sha256": song_item.song_sha256,
                        "md5": song_item.song_md5,
                        "title": song_item.title,
                        "artist": song_item.artist,
                        "subartist": song_item.subartist,
                        "subtitle": song_item.subtitle,
                        "bpm": song_item.bpm,
                    })

            _chunk = 4_096
            for i in range(0, len(song_rows), _chunk):
                chunk = song_rows[i : i + _chunk]
                stmt = (
                    insert(UserOwnedSong)
                    .values(chunk)
                    .on_conflict_do_nothing(index_elements=["user_id", "song_sha256"])
                )
                await db.execute(stmt)

            # Upsert song metadata into the Song table.
            # Use COALESCE to preserve existing metadata when new values are NULL.
            for i in range(0, len(song_meta_rows), _chunk):
                chunk = song_meta_rows[i : i + _chunk]
                song_stmt = insert(Song).values(chunk)
                song_stmt = song_stmt.on_conflict_do_update(
                    index_elements=["sha256"],
                    set_={
                        "md5": func.coalesce(song_stmt.excluded.md5, Song.md5),
                        "title": func.coalesce(song_stmt.excluded.title, Song.title),
                        "artist": func.coalesce(song_stmt.excluded.artist, Song.artist),
                        "subartist": func.coalesce(song_stmt.excluded.subartist, Song.subartist),
                        "subtitle": func.coalesce(song_stmt.excluded.subtitle, Song.subtitle),
                        "bpm": func.coalesce(song_stmt.excluded.bpm, Song.bpm),
                    },
                )
                await db.execute(song_stmt)

            synced_songs = len(song_rows)
        except Exception as e:
            errors.append(f"Song sync error: {str(e)}")

    # Flush owned songs so Song table is visible to score md5→sha256 lookup
    await db.flush()

    # Upsert scores — pre-fetch all existing rows in one query.
    # Identity key: (song_sha256 or song_md5, client_type)
    if payload.scores:
        # Resolve md5 → sha256 via songs table for LR2 md5-only scores.
        # When a match is found we use effective_sha256 so these scores join
        # the same sha256-keyed constraint as BMS-scanned data.
        lr2_md5_set = {
            item.song_md5
            for item in payload.scores
            if item.song_md5
        }
        md5_to_sha256: dict[str, str] = {}
        if lr2_md5_set:
            sha256_lookup = await db.execute(
                select(Song.md5, Song.sha256).where(
                    Song.md5.in_(lr2_md5_set),
                    Song.sha256.is_not(None),
                )
            )
            md5_to_sha256 = {row.md5: row.sha256 for row in sha256_lookup.all()}

        # Reverse lookup: sha256 → md5 for Beatoraja scores that have no song_md5.
        # Allows Beatoraja records to be found when a table only provides MD5.
        beatoraja_sha256_set = {
            item.song_sha256
            for item in payload.scores
            if item.song_sha256 and not item.song_md5
        }
        sha256_to_md5: dict[str, str] = {}
        if beatoraja_sha256_set:
            md5_lookup = await db.execute(
                select(Song.sha256, Song.md5).where(
                    Song.sha256.in_(beatoraja_sha256_set),
                    Song.md5.is_not(None),
                )
            )
            sha256_to_md5 = {row.sha256: row.md5 for row in md5_lookup.all()}

        sha256_pairs = [
            (item.song_sha256, item.client_type)
            for item in payload.scores
            if item.song_sha256
        ]
        md5_pairs = [
            (item.song_md5, item.client_type)
            for item in payload.scores
            if item.song_md5
        ]

        from sqlalchemy import or_
        where_clauses = []
        if sha256_pairs:
            where_clauses.append(
                tuple_(UserScore.song_sha256, UserScore.client_type).in_(sha256_pairs)
            )
        if md5_pairs:
            where_clauses.append(
                tuple_(UserScore.song_md5, UserScore.client_type).in_(md5_pairs)
            )

        existing_scores: list[UserScore] = []
        if where_clauses:
            existing_result = await db.execute(
                select(UserScore).where(
                    UserScore.user_id == current_user.id,
                    or_(*where_clauses),
                )
            )
            existing_scores = list(existing_result.scalars().all())

        existing_map: dict[tuple[str | None, str], UserScore] = {}
        for s in existing_scores:
            primary_key = (s.song_sha256 or s.song_md5, s.client_type)
            existing_map[primary_key] = s
            # Also index by md5 alone so sha256-resolved records can find their old md5-only row
            if s.song_md5 and not s.song_sha256:
                existing_map[(s.song_md5, s.client_type)] = s

        new_scores: list[UserScore] = []
        history_entries: list[ScoreHistory] = []

        for item in payload.scores:
            if not item.song_sha256 and not item.song_md5:
                errors.append("Score skipped: no song_sha256 or song_md5 provided")
                continue

            try:
                # Resolve effective sha256: use item's sha256, or look up from songs table by md5
                effective_sha256 = item.song_sha256 or md5_to_sha256.get(item.song_md5 or "")
                # Resolve effective md5: use item's md5, or reverse-look up from sha256 (Beatoraja)
                effective_md5 = item.song_md5 or sha256_to_md5.get(item.song_sha256 or "")

                identity_key = (effective_sha256 or effective_md5, item.client_type)
                existing = existing_map.get(identity_key)
                # Fallback: if sha256 was just resolved, also try the old md5-only key.
                # If found, merge sha256 onto the existing row to prevent duplicate row creation.
                if existing is None and effective_md5:
                    existing = existing_map.get((effective_md5, item.client_type))
                    if existing is not None and effective_sha256 and not existing.song_sha256:
                        existing.song_sha256 = effective_sha256

                today = date.today()

                def _make_history_stmt(
                    sha256_val: str | None,
                    md5_val: str | None,
                    old_clear_type: int | None,
                    old_score: float | None,
                    old_combo: int | None,
                    old_min_bp: int | None,
                    old_clear_count: int,
                    old_play_count: int = 0,
                    play_count: int = 0,
                ) -> Any:
                    """Build ScoreHistory INSERT ... ON CONFLICT upsert statement.

                    Uses the sha256-based unique constraint when sha256 is available;
                    falls back to the partial md5-only index for LR2-only records.
                    """
                    values = dict(
                        user_id=current_user.id,
                        song_sha256=sha256_val,
                        song_md5=md5_val,
                        client_type=item.client_type,
                        sync_date=today,
                        old_clear_type=old_clear_type,
                        clear_type=item.clear_type,
                        old_score=old_score,
                        score=item.score_rate,
                        score_rate=item.score_rate,
                        old_combo=old_combo,
                        combo=item.max_combo,
                        old_min_bp=old_min_bp,
                        min_bp=item.min_bp,
                        old_clear_count=old_clear_count,
                        clear_count=item.clear_count,
                        play_count=play_count,
                        old_play_count=old_play_count,
                        played_at=item.played_at,
                        recorded_at=func.now(),
                    )
                    update_set = {
                        "song_md5": md5_val,
                        "clear_type": item.clear_type,
                        "score": item.score_rate,
                        "score_rate": item.score_rate,
                        "combo": item.max_combo,
                        "min_bp": item.min_bp,
                        "clear_count": item.clear_count,
                        "play_count": play_count,
                        "played_at": item.played_at,
                        "recorded_at": func.now(),
                    }
                    if sha256_val:
                        return (
                            insert(ScoreHistory)
                            .values(**values)
                            .on_conflict_do_update(
                                constraint="uq_score_history_user_song_client_date",
                                set_=update_set,
                            )
                        )
                    else:
                        # md5-only path: use partial unique index from migration 0013
                        return (
                            insert(ScoreHistory)
                            .values(**values)
                            .on_conflict_do_update(
                                index_elements=["user_id", "song_md5", "client_type", "sync_date"],
                                index_where=text("song_sha256 IS NULL AND song_md5 IS NOT NULL"),
                                set_=update_set,
                            )
                        )

                if existing is None:
                    new_score = UserScore(
                        user_id=current_user.id,
                        song_sha256=effective_sha256,
                        song_md5=effective_md5,
                        client_type=item.client_type,
                        clear_type=item.clear_type,
                        score_rate=item.score_rate,
                        max_combo=item.max_combo,
                        min_bp=item.min_bp,
                        judgments=item.judgments,
                        options=item.options,
                        play_count=item.play_count,
                        clear_count=item.clear_count,
                        hit_notes=item.clear_count * _notes_per_play(item.judgments),
                        played_at=item.played_at,
                        synced_at=now,
                    )
                    new_scores.append(new_score)
                    history_entries.append(
                        _make_history_stmt(
                            effective_sha256, effective_md5, None, None, None, None, 0,
                            old_play_count=0, play_count=item.play_count,
                        )
                    )
                else:
                    # Always update metadata fields regardless of score improvement.
                    # options (arrangement, seed, etc.) must reflect the latest parser output.
                    # synced_at is intentionally NOT updated here — it records the initial sync time.
                    existing.options = item.options
                    old_play_count = existing.play_count
                    existing.play_count = item.play_count
                    # Backfill sha256/md5 if now resolved via songs table or agent
                    if effective_sha256 and not existing.song_sha256:
                        existing.song_sha256 = effective_sha256
                    if effective_md5 and not existing.song_md5:
                        existing.song_md5 = effective_md5

                    score_changed = _has_change(existing, item)
                    play_count_increased = item.play_count > old_play_count

                    if score_changed:
                        old_clear_type = existing.clear_type
                        old_score = existing.score_rate
                        old_combo = existing.max_combo
                        old_min_bp = existing.min_bp
                        old_clear_count = existing.clear_count

                        delta = max(0, item.clear_count - existing.clear_count)
                        existing.hit_notes = (existing.hit_notes or 0) + delta * _notes_per_play(item.judgments)
                        existing.clear_count = item.clear_count

                        # Score/combo/BP: only update when improved
                        if item.clear_type is not None and (
                            existing.clear_type is None or item.clear_type > existing.clear_type
                        ):
                            existing.clear_type = item.clear_type
                        if item.score_rate and (
                            existing.score_rate is None or item.score_rate > existing.score_rate
                        ):
                            existing.score_rate = item.score_rate
                        if item.max_combo and (
                            existing.max_combo is None or item.max_combo > existing.max_combo
                        ):
                            existing.max_combo = item.max_combo
                        if item.min_bp is not None and (
                            existing.min_bp is None or item.min_bp < existing.min_bp
                        ):
                            existing.min_bp = item.min_bp

                        existing.judgments = item.judgments
                        existing.played_at = item.played_at

                        final_sha256 = effective_sha256 or existing.song_sha256
                        final_md5 = effective_md5 or existing.song_md5
                        history_entries.append(
                            _make_history_stmt(
                                final_sha256, final_md5,
                                old_clear_type, old_score, old_combo, old_min_bp, old_clear_count,
                                old_play_count=old_play_count, play_count=item.play_count,
                            )
                        )
                    elif play_count_increased:
                        # play_count changed (FAILED plays); no score improvement.
                        # Record in score_history for per-sync play count tracking.
                        final_sha256 = effective_sha256 or existing.song_sha256
                        final_md5 = effective_md5 or existing.song_md5
                        history_entries.append(
                            _make_history_stmt(
                                final_sha256, final_md5,
                                existing.clear_type, existing.score_rate, existing.max_combo,
                                existing.min_bp, existing.clear_count,
                                old_play_count=old_play_count, play_count=item.play_count,
                            )
                        )

                synced_scores += 1
            except Exception as e:
                errors.append(f"Score sync error for {item.song_sha256 or item.song_md5}: {str(e)}")

        if new_scores:
            db.add_all(new_scores)
        for stmt in history_entries:
            await db.execute(stmt)

    # Upsert player stats — one row per (user_id, client_type)
    if payload.player_stats:
        for ps in payload.player_stats:
            stmt = (
                insert(UserPlayerStats)
                .values(
                    user_id=current_user.id,
                    client_type=ps.client_type,
                    total_notes_hit=ps.total_notes_hit,
                    total_play_count=ps.total_play_count,
                    synced_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "client_type"],
                    set_={
                        "total_notes_hit": ps.total_notes_hit,
                        "total_play_count": ps.total_play_count,
                        "synced_at": now,
                    },
                )
            )
            await db.execute(stmt)

            history_stmt = (
                insert(UserPlayerStatsHistory)
                .values(
                    user_id=current_user.id,
                    client_type=ps.client_type,
                    sync_date=now.date(),
                    total_notes_hit=ps.total_notes_hit,
                    total_play_count=ps.total_play_count,
                )
                .on_conflict_do_update(
                    constraint="uq_player_stats_history",
                    set_={
                        "total_notes_hit": ps.total_notes_hit,
                        "total_play_count": ps.total_play_count,
                    },
                )
            )
            await db.execute(history_stmt)

    # Upsert course records
    if payload.courses:
        # Pre-fetch all existing user_course_scores in one query
        course_hash_set = [c.course_hash for c in payload.courses]
        existing_course_result = await db.execute(
            select(UserCourseScore).where(
                UserCourseScore.user_id == current_user.id,
                UserCourseScore.course_hash.in_(course_hash_set),
            )
        )
        existing_course_map: dict[tuple[str, str], UserCourseScore] = {
            (s.course_hash, s.client_type): s
            for s in existing_course_result.scalars().all()
        }

        for item in payload.courses:
            try:
                # 1. Upsert course definition (idempotent — hash is the PK)
                course_stmt = (
                    insert(Course)
                    .values(
                        course_hash=item.course_hash,
                        source=item.client_type,
                        song_count=len(item.song_hashes),
                        song_hashes=item.song_hashes,
                    )
                    .on_conflict_do_nothing(index_elements=["course_hash"])
                )
                await db.execute(course_stmt)

                # 2. Upsert best score for this user
                key = (item.course_hash, item.client_type)
                existing = existing_course_map.get(key)

                if existing is None:
                    db.add(UserCourseScore(
                        user_id=current_user.id,
                        course_hash=item.course_hash,
                        client_type=item.client_type,
                        clear_type=item.clear_type,
                        score_rate=item.score_rate,
                        max_combo=item.max_combo,
                        min_bp=item.min_bp,
                        play_count=item.play_count,
                        clear_count=item.clear_count,
                        played_at=item.played_at,
                        synced_at=now,
                    ))
                    db.add(CourseScoreHistory(
                        user_id=current_user.id,
                        course_hash=item.course_hash,
                        client_type=item.client_type,
                        clear_type=item.clear_type,
                        old_clear_type=None,
                        score_rate=item.score_rate,
                        old_score_rate=None,
                        max_combo=item.max_combo,
                        min_bp=item.min_bp,
                        played_at=item.played_at,
                    ))
                else:
                    existing.play_count = item.play_count
                    existing.synced_at = now

                    improved = (
                        (item.clear_type is not None and (
                            existing.clear_type is None or item.clear_type > existing.clear_type
                        ))
                        or (item.score_rate is not None and (
                            existing.score_rate is None or item.score_rate > existing.score_rate
                        ))
                        or (item.max_combo is not None and (
                            existing.max_combo is None or item.max_combo > existing.max_combo
                        ))
                        or (item.min_bp is not None and (
                            existing.min_bp is None or item.min_bp < existing.min_bp
                        ))
                        or item.clear_count > existing.clear_count
                    )
                    if improved:
                        old_clear_type = existing.clear_type
                        old_score_rate = existing.score_rate

                        if item.clear_type is not None and (
                            existing.clear_type is None or item.clear_type > existing.clear_type
                        ):
                            existing.clear_type = item.clear_type
                        if item.score_rate and (
                            existing.score_rate is None or item.score_rate > existing.score_rate
                        ):
                            existing.score_rate = item.score_rate
                        if item.max_combo and (
                            existing.max_combo is None or item.max_combo > existing.max_combo
                        ):
                            existing.max_combo = item.max_combo
                        if item.min_bp is not None and (
                            existing.min_bp is None or item.min_bp < existing.min_bp
                        ):
                            existing.min_bp = item.min_bp
                        existing.clear_count = item.clear_count
                        existing.played_at = item.played_at

                        db.add(CourseScoreHistory(
                            user_id=current_user.id,
                            course_hash=item.course_hash,
                            client_type=item.client_type,
                            clear_type=item.clear_type,
                            old_clear_type=old_clear_type,
                            score_rate=item.score_rate,
                            old_score_rate=old_score_rate,
                            max_combo=item.max_combo,
                            min_bp=item.min_bp,
                            played_at=item.played_at,
                        ))

                synced_courses += 1
            except Exception as e:
                errors.append(f"Course sync error for {item.course_hash[:16]}...: {str(e)}")

    # Backfill score_history from Beatoraja scorelog (historical improvement records).
    # Uses ON CONFLICT DO NOTHING so existing entries are never overwritten.
    if payload.score_log:
        _log_chunk = 1000
        valid_log = [
            item for item in payload.score_log
            if len(item.song_sha256) == 64
        ]
        log_rows = [
            {
                "user_id": current_user.id,
                "song_sha256": item.song_sha256,
                "song_md5": None,
                "client_type": item.client_type,
                "sync_date": item.played_at.date(),
                "clear_type": item.clear_type,
                "old_clear_type": None,
                "score": None,
                "score_rate": None,
                "old_score": None,
                "combo": item.max_combo,
                "old_combo": None,
                "min_bp": item.min_bp,
                "old_min_bp": None,
                "clear_count": None,
                "old_clear_count": None,
                "played_at": item.played_at,
            }
            for item in valid_log
        ]
        for i in range(0, len(log_rows), _log_chunk):
            chunk = log_rows[i : i + _log_chunk]
            stmt = (
                insert(ScoreHistory)
                .values(chunk)
                .on_conflict_do_nothing(constraint="uq_score_history_user_song_client_date")
            )
            await db.execute(stmt)
        synced_score_log = len(valid_log)

    await db.commit()

    return SyncResponse(
        synced_scores=synced_scores,
        synced_songs=synced_songs,
        synced_courses=synced_courses,
        synced_score_log=synced_score_log,
        errors=errors,
    )


@router.get("/status")
async def get_sync_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get sync status for the current user."""
    scores_count = await db.execute(
        select(func.count(UserScore.id)).where(UserScore.user_id == current_user.id)
    )
    songs_count = await db.execute(
        select(func.count()).select_from(UserOwnedSong).where(
            UserOwnedSong.user_id == current_user.id
        )
    )
    last_synced = await db.execute(
        select(func.max(UserScore.synced_at)).where(UserScore.user_id == current_user.id)
    )

    return {
        "user_id": str(current_user.id),
        "total_scores": scores_count.scalar_one(),
        "total_owned_songs": songs_count.scalar_one(),
        "last_synced_at": last_synced.scalar_one(),
    }
