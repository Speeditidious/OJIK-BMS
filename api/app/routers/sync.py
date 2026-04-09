"""Local agent synchronization endpoints."""
import math
from datetime import UTC, datetime
from datetime import date as date_cls
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, literal, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.score import UserPlayerStats, UserScore
from app.models.user import User

router = APIRouter(prefix="/sync", tags=["sync"])


def _compute_score_fields(
    client_type: str,
    judgments: dict | None,
    notes: int | None,
) -> tuple[int | None, float | None, str | None]:
    """Compute exscore, rate (%), and rank from judgments and note count."""
    if not judgments or not notes:
        return None, None, None
    if client_type == "lr2":
        exscore = judgments.get("perfect", 0) * 2 + judgments.get("great", 0)
    elif client_type == "beatoraja":
        exscore = (
            (judgments.get("epg", 0) + judgments.get("lpg", 0)) * 2
            + judgments.get("egr", 0)
            + judgments.get("lgr", 0)
        )
    else:
        return None, None, None
    max_ex = notes * 2
    if max_ex <= 0:
        return exscore, None, None
    rate = math.floor(exscore / max_ex * 10000) / 100
    # Rank thresholds use notes (not max_ex):
    #   exscore * 9 >= notes * 16 → AAA (≥ 8/9 of max)
    for rank, threshold in [("AAA", 16), ("AA", 14), ("A", 12), ("B", 10), ("C", 8), ("D", 6), ("E", 4)]:
        if exscore * 9 >= notes * threshold:
            return exscore, rate, rank
    return exscore, rate, "F"


class ScoreSyncItem(BaseModel):
    scorehash: str | None = None
    fumen_sha256: str | None = None
    fumen_md5: str | None = None
    fumen_hash_others: str | None = None  # course records
    client_type: str  # lr2 / beatoraja / qwilight
    clear_type: int | None = None
    notes: int | None = None
    exscore: int | None = None  # pre-computed exscore (e.g. from scorelog.db)
    max_combo: int | None = None
    min_bp: int | None = None
    judgments: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    play_count: int | None = None
    clear_count: int | None = None
    recorded_at: datetime | None = None
    song_hashes: list[dict[str, Any]] = []  # for course definition


class PlayerStats(BaseModel):
    client_type: str
    playcount: int | None = None
    clearcount: int | None = None
    playtime: int | None = None
    judgments: dict[str, Any] | None = None


class SyncRequest(BaseModel):
    scores: list[ScoreSyncItem] = []
    player_stats: list[PlayerStats] = []


class SyncResponse(BaseModel):
    synced_scores: int
    inserted_scores: int = 0
    skipped_scores: int = 0
    errors: list[str] = []


# ── Best-value helpers ────────────────────────────────────────────────────────

def _fumen_key(item: ScoreSyncItem) -> tuple[str | None, str | None, str | None]:
    """Return (sha256, md5, hash_others) key for grouping."""
    return (item.fumen_sha256, item.fumen_md5, item.fumen_hash_others)


async def _fetch_current_bests(
    user_id: Any,
    sha256s: set[str],
    md5s: set[str],
    hash_others: set[str],
    client_types: set[str],
    db: AsyncSession,
) -> dict[tuple, dict[str, Any]]:
    """Bulk-fetch per-field best values for the given fumen hashes.

    Returns a dict keyed by (fumen_sha256, fumen_md5, fumen_hash_others, client_type)
    with values: {clear_type, exscore, min_bp, max_combo, play_count}.
    Aggregates in Python after fetching all rows for the target hashes.
    """
    bests: dict[tuple, dict[str, Any]] = {}

    conditions = []
    if sha256s:
        conditions.append(
            (UserScore.fumen_sha256.in_(sha256s)) & (UserScore.fumen_sha256.isnot(None))
        )
    if md5s:
        conditions.append(
            (UserScore.fumen_md5.in_(md5s)) & (UserScore.fumen_md5.isnot(None)) &
            UserScore.fumen_sha256.is_(None)
        )
    if hash_others:
        conditions.append(
            (UserScore.fumen_hash_others.in_(hash_others)) & (UserScore.fumen_hash_others.isnot(None))
        )

    if not conditions:
        return bests

    combined = conditions[0]
    for c in conditions[1:]:
        combined = combined | c

    result = await db.execute(
        select(UserScore).where(
            UserScore.user_id == user_id,
            UserScore.client_type.in_(client_types),
            combined,
        )
    )
    rows = result.scalars().all()

    for row in rows:
        key = (row.fumen_sha256, row.fumen_md5, row.fumen_hash_others, row.client_type)
        if key not in bests:
            bests[key] = {
                "clear_type": None,
                "exscore": None,
                "min_bp": None,
                "max_combo": None,
                "play_count": None,
            }
        entry = bests[key]
        if row.clear_type is not None and (entry["clear_type"] is None or row.clear_type > entry["clear_type"]):
            entry["clear_type"] = row.clear_type
        if row.exscore is not None and (entry["exscore"] is None or row.exscore > entry["exscore"]):
            entry["exscore"] = row.exscore
        if row.min_bp is not None and (entry["min_bp"] is None or row.min_bp < entry["min_bp"]):
            entry["min_bp"] = row.min_bp
        if row.max_combo is not None and (entry["max_combo"] is None or row.max_combo > entry["max_combo"]):
            entry["max_combo"] = row.max_combo
        if row.play_count is not None and (entry["play_count"] is None or row.play_count > entry["play_count"]):
            entry["play_count"] = row.play_count

    return bests


# ── Same-day merge helpers ─────────────────────────────────────────────────────

def _pick(a: Any, b: Any, *, higher_better: bool) -> Any:
    """Return the better of two nullable values (None treated as worst)."""
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b) if higher_better else min(a, b)


def _merge_into_existing(
    existing: UserScore,
    item: "ScoreSyncItem",
    new_exscore: int | None,
    new_rate: float | None,
    new_rank: str | None,
) -> dict[str, Any]:
    """Return UPDATE kwargs that merge item into existing row, keeping best per field.

    Performance fields (clear_type/exscore/min_bp/max_combo/play_count) each
    take the better value independently.  recorded_at takes the later timestamp.
    judgments/options/scorehash/clear_count come from whichever side has the
    later recorded_at.
    """
    merged_clear_type = _pick(item.clear_type, existing.clear_type, higher_better=True)
    merged_exscore = _pick(new_exscore, existing.exscore, higher_better=True)
    merged_min_bp = _pick(item.min_bp, existing.min_bp, higher_better=False)
    merged_max_combo = _pick(item.max_combo, existing.max_combo, higher_better=True)
    merged_play_count = _pick(item.play_count, existing.play_count, higher_better=True)

    # recorded_at: take the later timestamp
    item_ts = item.recorded_at
    existing_ts = existing.recorded_at
    if item_ts is not None and existing_ts is not None:
        use_new_side = item_ts >= existing_ts
    elif item_ts is not None:
        use_new_side = True
    else:
        use_new_side = False
    merged_recorded_at = item_ts if use_new_side else existing_ts

    # rate/rank follow merged_exscore source
    if merged_exscore == new_exscore and new_exscore is not None:
        merged_rate, merged_rank = new_rate, new_rank
    else:
        merged_rate, merged_rank = existing.rate, existing.rank

    # judgments/options/scorehash/clear_count: take from later recorded_at side
    if use_new_side:
        merged_judgments = item.judgments
        merged_options = item.options
        merged_scorehash = item.scorehash
        merged_clear_count = item.clear_count
    else:
        merged_judgments = existing.judgments
        merged_options = existing.options
        merged_scorehash = existing.scorehash
        merged_clear_count = existing.clear_count

    return {
        "clear_type": merged_clear_type,
        "exscore": merged_exscore,
        "rate": merged_rate,
        "rank": merged_rank,
        "min_bp": merged_min_bp,
        "max_combo": merged_max_combo,
        "play_count": merged_play_count,
        "clear_count": merged_clear_count,
        "judgments": merged_judgments,
        "options": merged_options,
        "scorehash": merged_scorehash,
        "recorded_at": merged_recorded_at,
    }


async def _fetch_same_day_rows(
    user_id: Any,
    sha256s: set[str],
    md5s: set[str],
    dates: set[date_cls],
    db: AsyncSession,
) -> dict[tuple, UserScore]:
    """Batch-fetch existing fumen rows that fall on any of the given UTC dates.

    Returns {(sha256_or_md5, client_type, utc_date): UserScore}.
    When multiple rows share the same key, the one with the latest recorded_at
    is kept (will be further merged at insert time).
    """
    result_map: dict[tuple, UserScore] = {}
    if not dates or not (sha256s or md5s):
        return result_map

    conds = []
    if sha256s:
        conds.append(
            UserScore.fumen_sha256.in_(sha256s) & UserScore.fumen_sha256.isnot(None)
        )
    if md5s:
        conds.append(
            UserScore.fumen_md5.in_(md5s)
            & UserScore.fumen_md5.isnot(None)
            & UserScore.fumen_sha256.is_(None)
        )
    combined = conds[0]
    for c in conds[1:]:
        combined = combined | c

    rows_result = await db.execute(
        select(UserScore).where(
            UserScore.user_id == user_id,
            UserScore.fumen_hash_others.is_(None),
            combined,
            cast(func.timezone("UTC", UserScore.recorded_at), Date).in_([literal(d, Date) for d in dates]),
        )
    )
    for row in rows_result.scalars().all():
        if row.recorded_at is None:
            continue
        d = row.recorded_at.date()
        hash_key = row.fumen_sha256 or row.fumen_md5
        k = (hash_key, row.client_type, d)
        existing = result_map.get(k)
        if existing is None or (row.recorded_at > existing.recorded_at):
            result_map[k] = row
    return result_map


def _is_improvement(
    item: ScoreSyncItem,
    exscore: int | None,
    best: dict[str, Any] | None,
) -> bool:
    """Return True if the new score strictly improves at least one tracked field over current bests.

    All comparisons are strict (>, <) so that unchanged records on re-sync are not inserted again.
    play_count uses strict > as it is a cumulative counter.
    """
    if best is None:
        return True  # no existing record — always insert

    # Regular fumen record
    if item.clear_type is not None:
        if best["clear_type"] is None or item.clear_type > best["clear_type"]:
            return True

    if exscore is not None:
        if best["exscore"] is None or exscore > best["exscore"]:
            return True

    if item.min_bp is not None:
        if best["min_bp"] is None or item.min_bp < best["min_bp"]:
            return True

    if item.max_combo is not None:
        if best["max_combo"] is None or item.max_combo > best["max_combo"]:
            return True

    if item.play_count is not None:
        if best["play_count"] is None or item.play_count > best["play_count"]:
            return True

    return False


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=SyncResponse)
async def sync_data(
    payload: SyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """
    Bulk upsert scores from the local agent.

    Accumulating model:
    - If scorehash is not None: INSERT with ON CONFLICT (scorehash, user_id, client_type)
      DO UPDATE (partial unique index applies only when scorehash IS NOT NULL).
    - If scorehash is None: plain INSERT (no dedup).
    - Course records: fumen_hash_others is set (course_hash from client); stored as-is in user_scores.
    - Improvement check: if no field improves over existing per-field bests, the row is skipped.
    """
    errors: list[str] = []
    synced_scores = 0
    inserted_scores = 0
    skipped_scores = 0
    now = datetime.now(UTC)

    if not payload.scores and not payload.player_stats:
        return SyncResponse(synced_scores=0, skipped_scores=0, errors=[])

    # ── Bulk pre-fetch per-field bests ──────────────────────────────────────────
    current_bests: dict[tuple, dict[str, Any]] = {}
    same_day_map: dict[tuple, UserScore] = {}
    if payload.scores:
        sha256s = {item.fumen_sha256 for item in payload.scores if item.fumen_sha256}
        md5s = {item.fumen_md5 for item in payload.scores if item.fumen_md5 and not item.fumen_sha256}
        hash_others = {item.fumen_hash_others for item in payload.scores if item.fumen_hash_others}
        client_types = {item.client_type for item in payload.scores}
        current_bests = await _fetch_current_bests(
            current_user.id, sha256s, md5s, hash_others, client_types, db
        )

        # ── Pre-fetch same-day rows for fumen records (courses excluded) ─────
        fumen_dates: set[date_cls] = {
            item.recorded_at.date()
            for item in payload.scores
            if item.recorded_at and not item.fumen_hash_others
        }
        same_day_map = await _fetch_same_day_rows(
            current_user.id, sha256s, md5s, fumen_dates, db
        )

    if payload.scores:
        for item in payload.scores:
            try:
                exscore, rate, rank = _compute_score_fields(
                    item.client_type, item.judgments, item.notes
                )
                # Fall back to client-supplied exscore when judgments/notes are unavailable
                if exscore is None and item.exscore is not None:
                    exscore = item.exscore

                is_course = bool(item.fumen_hash_others)

                # ── Best key for lookup ─────────────────────────────────────
                # sha256 takes priority; md5-only if sha256 absent; hash_others for courses
                if item.fumen_sha256:
                    best_key = (item.fumen_sha256, None, None, item.client_type)
                elif item.fumen_md5:
                    best_key = (None, item.fumen_md5, None, item.client_type)
                else:
                    best_key = (None, None, item.fumen_hash_others, item.client_type)

                best = current_bests.get(best_key)

                # ── Improvement check ───────────────────────────────────────
                if not _is_improvement(item, exscore, best):
                    skipped_scores += 1
                    continue

                # ── Same-day merge for fumen records ────────────────────────
                # Courses keep the legacy insert path (no same-day dedup).
                # Fumen records: if a row already exists for this (hash, client_type, UTC date),
                # UPDATE that row with the per-field best values rather than inserting a new one.
                same_day_key: tuple | None = None
                existing_same_day: UserScore | None = None
                if not is_course and item.recorded_at:
                    hash_key = item.fumen_sha256 or item.fumen_md5
                    same_day_key = (hash_key, item.client_type, item.recorded_at.date())
                    existing_same_day = same_day_map.get(same_day_key)

                async with db.begin_nested():
                    if existing_same_day is not None:
                        # Merge into the existing same-day row
                        merged = _merge_into_existing(existing_same_day, item, exscore, rate, rank)
                        await db.execute(
                            update(UserScore)
                            .where(UserScore.id == existing_same_day.id)
                            .values(**merged, synced_at=now)
                        )
                        new_id = existing_same_day.id
                        # Reflect merged values back so in-memory best cache stays accurate
                        exscore = merged["exscore"]
                        rate = merged["rate"]
                        rank = merged["rank"]
                        item = item.model_copy(update={
                            "clear_type": merged["clear_type"],
                            "min_bp": merged["min_bp"],
                            "max_combo": merged["max_combo"],
                            "play_count": merged["play_count"],
                        })
                        # Reflect merged field values onto the in-memory object so subsequent
                        # merges for the same key compare against up-to-date values.
                        for _f, _v in merged.items():
                            setattr(existing_same_day, _f, _v)
                        same_day_map[same_day_key] = existing_same_day
                    else:
                        # No same-day row — insert new
                        values = dict(
                            user_id=current_user.id,
                            client_type=item.client_type,
                            scorehash=item.scorehash,
                            fumen_sha256=item.fumen_sha256,
                            fumen_md5=item.fumen_md5,
                            fumen_hash_others=item.fumen_hash_others,
                            clear_type=item.clear_type,
                            exscore=exscore,
                            rate=rate,
                            rank=rank,
                            max_combo=item.max_combo,
                            min_bp=item.min_bp,
                            play_count=item.play_count,
                            clear_count=item.clear_count,
                            judgments=item.judgments,
                            options=item.options,
                            recorded_at=item.recorded_at,
                            synced_at=now,
                        )
                        _ins = insert(UserScore).values(**values)
                        stmt = (
                            _ins
                            .on_conflict_do_update(
                                index_elements=["scorehash", "user_id", "client_type"],
                                index_where=text("scorehash IS NOT NULL"),
                                set_={
                                    "clear_type": func.coalesce(_ins.excluded.clear_type, UserScore.clear_type),
                                    "exscore": func.coalesce(_ins.excluded.exscore, UserScore.exscore),
                                    "rate": func.coalesce(_ins.excluded.rate, UserScore.rate),
                                    "rank": func.coalesce(_ins.excluded.rank, UserScore.rank),
                                    "max_combo": func.coalesce(_ins.excluded.max_combo, UserScore.max_combo),
                                    "min_bp": func.coalesce(_ins.excluded.min_bp, UserScore.min_bp),
                                    "play_count": func.coalesce(_ins.excluded.play_count, UserScore.play_count),
                                    "clear_count": func.coalesce(_ins.excluded.clear_count, UserScore.clear_count),
                                    "judgments": func.coalesce(_ins.excluded.judgments, UserScore.judgments),
                                    "options": func.coalesce(_ins.excluded.options, UserScore.options),
                                },
                            )
                            .returning(UserScore.id)
                        )
                        result = await db.execute(stmt)
                        new_id = result.scalar_one_or_none()
                        if new_id is None:
                            skipped_scores += 1
                            continue
                        inserted_scores += 1
                        # Register in same_day_map so subsequent items in same payload can merge into it
                        if same_day_key is not None:
                            # Store a lightweight sentinel (we only need the id and field values)
                            new_row_sentinel = UserScore(
                                id=new_id,
                                user_id=current_user.id,
                                client_type=item.client_type,
                                fumen_sha256=item.fumen_sha256,
                                fumen_md5=item.fumen_md5,
                                clear_type=item.clear_type,
                                exscore=exscore,
                                rate=rate,
                                rank=rank,
                                min_bp=item.min_bp,
                                max_combo=item.max_combo,
                                play_count=item.play_count,
                                clear_count=item.clear_count,
                                judgments=item.judgments,
                                options=item.options,
                                scorehash=item.scorehash,
                                recorded_at=item.recorded_at,
                            )
                            same_day_map[same_day_key] = new_row_sentinel

                # Update in-memory best cache for subsequent items in same payload
                effective_best: dict[str, Any] = best or {
                    "clear_type": None, "exscore": None,
                    "min_bp": None, "max_combo": None, "play_count": None,
                }
                if best_key not in current_bests:
                    current_bests[best_key] = effective_best.copy()
                entry = current_bests[best_key]
                if item.clear_type is not None and (entry["clear_type"] is None or item.clear_type >= entry["clear_type"]):
                    entry["clear_type"] = item.clear_type
                if exscore is not None and (entry["exscore"] is None or exscore >= entry["exscore"]):
                    entry["exscore"] = exscore
                if not is_course:
                    if item.min_bp is not None and (entry["min_bp"] is None or item.min_bp <= entry["min_bp"]):
                        entry["min_bp"] = item.min_bp
                    if item.max_combo is not None and (entry["max_combo"] is None or item.max_combo >= entry["max_combo"]):
                        entry["max_combo"] = item.max_combo

                synced_scores += 1
            except Exception as e:
                identifier = item.scorehash or item.fumen_sha256 or item.fumen_md5 or item.fumen_hash_others or "?"
                errors.append(f"Score sync error for {identifier}: {str(e)}")

    # Upsert player stats — one row per (user_id, client_type, UTC date); synced_at updated on same-day conflict.
    # ON CONFLICT with the functional index is not directly usable via SQLAlchemy dialect,
    # so we use SELECT + UPDATE/INSERT pattern.
    if payload.player_stats:
        today = now.date()
        for ps in payload.player_stats:
            existing = await db.execute(
                select(UserPlayerStats).where(
                    UserPlayerStats.user_id == current_user.id,
                    UserPlayerStats.client_type == ps.client_type,
                    text("CAST(synced_at AT TIME ZONE 'UTC' AS date) = :d"),
                ),
                {"d": today},
            )
            row = existing.scalar_one_or_none()
            if row:
                await db.execute(
                    update(UserPlayerStats)
                    .where(UserPlayerStats.id == row.id)
                    .values(
                        playcount=ps.playcount,
                        clearcount=ps.clearcount,
                        playtime=ps.playtime,
                        judgments=ps.judgments,
                        synced_at=now,
                    )
                )
            else:
                # Check if anything actually changed since the last recorded row
                latest_result = await db.execute(
                    select(UserPlayerStats)
                    .where(
                        UserPlayerStats.user_id == current_user.id,
                        UserPlayerStats.client_type == ps.client_type,
                    )
                    .order_by(UserPlayerStats.synced_at.desc())
                    .limit(1)
                )
                latest_row = latest_result.scalar_one_or_none()
                if (
                    latest_row is not None
                    and latest_row.playcount == ps.playcount
                    and latest_row.clearcount == ps.clearcount
                    and latest_row.playtime == ps.playtime
                ):
                    continue
                db.add(UserPlayerStats(
                    user_id=current_user.id,
                    client_type=ps.client_type,
                    synced_at=now,
                    playcount=ps.playcount,
                    clearcount=ps.clearcount,
                    playtime=ps.playtime,
                    judgments=ps.judgments,
                ))

        # Set first_synced_at[client_type] if not already recorded
        for ct in {ps.client_type for ps in payload.player_stats}:
            await db.execute(
                text("""
                    UPDATE users
                    SET first_synced_at = (
                        CASE WHEN first_synced_at IS NOT NULL AND jsonb_typeof(first_synced_at) = 'object'
                             THEN first_synced_at
                             ELSE '{}'::jsonb
                        END
                    ) || jsonb_build_object(:ct, CAST(:ts AS TEXT))
                    WHERE id = :uid
                      AND (
                        first_synced_at IS NULL
                        OR jsonb_typeof(first_synced_at) != 'object'
                        OR first_synced_at->:ct IS NULL
                      )
                """),
                {"uid": str(current_user.id), "ct": ct, "ts": now.isoformat()},
            )

    await db.commit()

    return SyncResponse(
        synced_scores=synced_scores,
        inserted_scores=inserted_scores,
        skipped_scores=skipped_scores,
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
    last_synced = await db.execute(
        select(func.max(UserScore.synced_at)).where(UserScore.user_id == current_user.id)
    )

    return {
        "user_id": str(current_user.id),
        "total_scores": scores_count.scalar_one(),
        "last_synced_at": last_synced.scalar_one(),
    }
