"""Score query endpoints."""

import math
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.models.course import Course
from app.models.difficulty_table import DifficultyTable
from app.models.fumen import Fumen, FumenTableEntry
from app.models.score import UserScore
from app.models.user import User
from app.services.clear_type_display import display_clear_type
from app.services.client_aggregation import (
    CLIENT_LABEL,
    PerClientBest,
    aggregate_source_client,
)
from app.services.initial_sync import is_initial_sync_timestamp
from app.services.score_history import is_play_count_only_update
from app.services.score_row_detail import (
    build_course_stages,
    course_option_label,
    decode_arrangement,
    match_course_from_hash,
    normalize_judgments,
    pick_best_per_client,
)

router = APIRouter(prefix="/scores", tags=["scores"])


def _compute_rate_rank(exscore: int, notes_total: int) -> tuple[float, str]:
    """Compute rate (%) and rank from exscore and notes_total."""
    max_ex = notes_total * 2
    if max_ex <= 0:
        return 0.0, "F"
    rate = math.floor(exscore / max_ex * 10000) / 100
    for rank, threshold in [("AAA", 16), ("AA", 14), ("A", 12), ("B", 10), ("C", 8), ("D", 6), ("E", 4)]:
        if exscore * 9 >= notes_total * threshold:
            return rate, rank
    return rate, "F"


def _effective_score_ts(score: UserScore):
    """Return the timestamp used to order score history rows."""
    return score.recorded_at or score.synced_at


def _history_group_key(score: UserScore) -> tuple[str | None, str]:
    return (score.fumen_sha256 or score.fumen_md5, score.client_type)


def _filter_play_count_only_history_rows(scores: list[UserScore]) -> list[UserScore]:
    """Remove metadata-only play-count rows from a fumen history response."""
    by_key: dict[tuple[str | None, str], list[UserScore]] = {}
    for score in scores:
        by_key.setdefault(_history_group_key(score), []).append(score)

    hidden_ids: set[uuid.UUID] = set()
    for rows in by_key.values():
        ordered = sorted(
            rows,
            key=lambda score: (_effective_score_ts(score) is None, _effective_score_ts(score)),
        )
        prev: UserScore | None = None
        for score in ordered:
            if is_play_count_only_update(score, prev):
                hidden_ids.add(score.id)
            else:
                prev = score

    return [score for score in scores if score.id not in hidden_ids]


class UserScoreRead(BaseModel):
    id: str
    user_id: str
    fumen_id: str | None = None
    scorehash: str | None
    fumen_sha256: str | None
    fumen_md5: str | None
    fumen_hash_others: str | None
    client_type: str
    clear_type: int | None
    exscore: int | None
    rate: float | None
    rank: str | None
    max_combo: int | None
    min_bp: int | None
    play_count: int | None
    options: dict | None = None
    recorded_at: str | None
    synced_at: str | None
    is_first_sync: bool = False
    judgment_detail: dict | None = None
    arrangement: dict | None = None
    model_config = ConfigDict(from_attributes=True)


class PerFieldBestScore(BaseModel):
    """Per-field best score aggregated from each client's latest row."""
    best_clear_type: int | None = None
    best_clear_type_client: str | None = None
    best_exscore: int | None = None
    rate: float | None = None
    rank: str | None = None
    best_exscore_client: str | None = None
    best_min_bp: int | None = None
    best_min_bp_client: str | None = None
    best_max_combo: int | None = None
    best_max_combo_client: str | None = None
    source_client: str | None = None
    source_client_detail: dict | None = None


async def _resolve_target_user(
    user_id: uuid.UUID | None,
    current_user: User | None,
    db: AsyncSession,
) -> User:
    """Resolve the score owner for song history lookups."""
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


@router.get("/me", response_model=list[UserScoreRead])
async def get_my_scores(
    client_type: str | None = Query(None, description="Filter by client type: lr2, beatoraja, qwilight"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserScoreRead]:
    """Get current user's scores."""
    query = select(UserScore).where(UserScore.user_id == current_user.id)

    if client_type:
        query = query.where(UserScore.client_type == client_type)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    scores = result.scalars().all()

    return [
        UserScoreRead(
            id=str(s.id),
            user_id=str(s.user_id),
            scorehash=s.scorehash,
            fumen_id=str(s.fumen_id) if s.fumen_id else None,
            fumen_sha256=s.fumen_sha256,
            fumen_md5=s.fumen_md5,
            fumen_hash_others=s.fumen_hash_others,
            client_type=s.client_type,
            clear_type=display_clear_type(s.clear_type, exscore=s.exscore, rate=s.rate),
            exscore=s.exscore,
            rate=s.rate,
            rank=s.rank,
            max_combo=s.max_combo,
            min_bp=s.min_bp,
            play_count=s.play_count,
            options=s.options,
            recorded_at=s.recorded_at.isoformat() if s.recorded_at else None,
            synced_at=s.synced_at.isoformat() if s.synced_at else None,
        )
        for s in scores
    ]


@router.get("/me/fumen/{hash_value}", response_model=list[UserScoreRead])
async def get_scores_for_fumen(
    hash_value: str,
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[UserScoreRead]:
    """Get all score rows for a specific fumen (sha256 or md5), ordered by recorded_at DESC."""
    from sqlalchemy import or_ as _or

    target_user = await _resolve_target_user(user_id, current_user, db)

    fumen_condition = None
    notes_condition = None
    # Resolve hash type by length first; uuid.UUID() would otherwise mis-parse
    # a 32-char md5 as a fumen_id UUID.
    if len(hash_value) == 64:
        fumen_uuid = None
    elif len(hash_value) == 32:
        fumen_uuid = None
    else:
        try:
            fumen_uuid = uuid.UUID(hash_value)
        except ValueError:
            fumen_uuid = None

    if fumen_uuid is not None:
        condition = (
            UserScore.fumen_id == fumen_uuid,
            UserScore.fumen_hash_others.is_(None),
        )
        notes_condition = Fumen.fumen_id == fumen_uuid
    elif len(hash_value) == 64:
        # sha256 lookup: find fumen's md5 to also fetch md5-only rows (e.g. LR2)
        fumen_condition = Fumen.sha256 == hash_value
        notes_condition = fumen_condition
        fumen_row = await db.execute(select(Fumen.md5).where(fumen_condition).limit(1))
        paired_md5 = fumen_row.scalar_one_or_none()
        if paired_md5:
            hash_condition = _or(
                (UserScore.fumen_sha256 == hash_value),
                (UserScore.fumen_md5 == paired_md5) & UserScore.fumen_sha256.is_(None),
            )
        else:
            hash_condition = UserScore.fumen_sha256 == hash_value
        condition = (hash_condition, UserScore.fumen_hash_others.is_(None))
    elif len(hash_value) == 32:
        # md5 lookup: include rows regardless of whether sha256 is also set
        fumen_condition = Fumen.md5 == hash_value
        notes_condition = fumen_condition
        condition = (
            UserScore.fumen_md5 == hash_value,
            UserScore.fumen_hash_others.is_(None),
        )
    else:
        from fastapi import HTTPException as _HTTPException
        from fastapi import status as _status
        raise _HTTPException(status_code=_status.HTTP_400_BAD_REQUEST, detail="Invalid hash length")

    result = await db.execute(
        select(UserScore)
        .where(UserScore.user_id == target_user.id, *condition)
        .order_by(func.coalesce(UserScore.recorded_at, UserScore.synced_at).desc().nullslast())
    )
    scores = result.scalars().all()
    scores = _filter_play_count_only_history_rows(scores)

    # Fetch first_synced_at for is_first_sync detection
    fst_result = await db.execute(select(User.first_synced_at).where(User.id == target_user.id))
    first_synced_at: dict | None = fst_result.scalar_one_or_none()

    def _is_first_sync(s: UserScore) -> bool:
        return is_initial_sync_timestamp(first_synced_at, s.client_type, s.synced_at)

    # Fetch notes_total and keymode for rate/rank computation and arrangement decoding.
    # Always fetch when there are scores so arrangement can be decoded for every row.
    notes_total: int | None = None
    fumen_keymode: int | None = None
    if scores and notes_condition is not None:
        fumen_meta_result = await db.execute(
            select(Fumen.notes_total, Fumen.keymode).where(notes_condition).limit(1)
        )
        row = fumen_meta_result.one_or_none()
        if row is not None:
            notes_total, fumen_keymode = row[0], row[1]

    def _get_rate_rank(s: UserScore) -> tuple[float | None, str | None]:
        if s.rate is not None:
            return s.rate, s.rank
        if s.exscore is not None and notes_total:
            return _compute_rate_rank(s.exscore, notes_total)
        return None, None

    out = []
    for s in scores:
        rate, rank = _get_rate_rank(s)
        out.append(UserScoreRead(
            id=str(s.id),
            user_id=str(s.user_id),
            scorehash=s.scorehash,
            fumen_id=str(s.fumen_id) if s.fumen_id else None,
            fumen_sha256=s.fumen_sha256,
            fumen_md5=s.fumen_md5,
            fumen_hash_others=s.fumen_hash_others,
            client_type=s.client_type,
            clear_type=display_clear_type(s.clear_type, exscore=s.exscore, rate=rate),
            exscore=s.exscore,
            rate=rate,
            rank=rank,
            max_combo=s.max_combo,
            min_bp=s.min_bp,
            play_count=s.play_count,
            options=s.options,
            recorded_at=s.recorded_at.isoformat() if s.recorded_at else None,
            synced_at=s.synced_at.isoformat() if s.synced_at else None,
            is_first_sync=_is_first_sync(s),
            judgment_detail=normalize_judgments(s.client_type, s.judgments),
            arrangement=decode_arrangement(s.client_type, s.options, fumen_keymode),
        ))
    return out


class RowDetailRecord(BaseModel):
    """Single client's best score record in fumen row detail response."""

    score_id: str
    client_type: str
    clear_type: int | None
    min_bp: int | None
    rate: float | None
    rank: str | None
    exscore: int | None
    play_count: int | None
    judgment_detail: dict | None
    arrangement: dict | None


class FumenRowDetailResponse(BaseModel):
    """Response for GET /scores/fumen/{fumen_id}/row-detail."""

    fumen_id: str
    keymode: int | None
    detail_basis: str
    records: list[RowDetailRecord]


class CourseRowDetailRecord(BaseModel):
    """One aggregate course score record for an execution client."""

    score_id: str
    client_type: str
    judgment_detail: dict | None
    option_label: str | None


class CourseStage(BaseModel):
    """One ordered member of a course."""

    stage: int
    level: str | None
    title: str | None
    fumen_sha256: str | None = None
    fumen_md5: str | None = None
    table_symbol: str | None = None


class CourseRowDetailResponse(BaseModel):
    """Response for GET /scores/course/{course_hash}/row-detail."""

    course_name: str
    records: list[CourseRowDetailRecord]
    stages: list[CourseStage]


@router.get("/course/{course_hash}/row-detail", response_model=CourseRowDetailResponse)
async def get_course_row_detail(
    course_hash: str,
    client_type: str = Query(..., description="Client used to resolve the aggregate course hash"),
    score_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = Query(None),
    as_of: str | None = Query(None, description="ISO date YYYY-MM-DD for historical filtering"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CourseRowDetailResponse:
    """Return aggregate judgments, option labels, and ordered stages for a course."""
    target_user = await _resolve_target_user(user_id, current_user, db)

    course_result = await db.execute(select(Course).where(Course.is_active.is_(True)))
    course = match_course_from_hash(course_result.scalars().all(), course_hash, client_type)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    score_query = select(UserScore).where(
        UserScore.user_id == target_user.id,
        UserScore.fumen_hash_others == course_hash,
    )
    if score_id is not None:
        score_query = score_query.where(UserScore.id == score_id)
    if as_of:
        try:
            as_of_date = date.fromisoformat(as_of)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="as_of must be in ISO format YYYY-MM-DD",
            )
        score_query = score_query.where(
            func.coalesce(UserScore.recorded_at, UserScore.synced_at).cast(Date) <= as_of_date
        )
    score_result = await db.execute(score_query)
    representatives = pick_best_per_client(score_result.scalars().all())

    records = [
        CourseRowDetailRecord(
            score_id=str(score.id),
            client_type=score.client_type,
            judgment_detail=normalize_judgments(score.client_type, score.judgments),
            option_label=course_option_label(score.client_type, score.options),
        )
        for score in representatives
    ]

    # Fetch source table symbol and slug for level display and fallback logic
    source_table_symbol: str | None = None
    source_table_slug: str | None = None
    if course.source_table_id:
        tbl_result = await db.execute(
            select(DifficultyTable.symbol, DifficultyTable.slug)
            .where(DifficultyTable.id == course.source_table_id)
            .limit(1)
        )
        tbl_row = tbl_result.first()
        if tbl_row:
            source_table_symbol = tbl_row.symbol
            source_table_slug = tbl_row.slug

    sha256_list = list(course.sha256_list or [])
    hashes = [value for value in (sha256_list if sha256_list else course.md5_list or []) if value]
    if hashes:
        hash_condition = Fumen.sha256.in_(hashes) if sha256_list else Fumen.md5.in_(hashes)
        stage_result = await db.execute(
            select(Fumen.sha256, Fumen.md5, Fumen.title, FumenTableEntry.level)
            .outerjoin(
                FumenTableEntry,
                and_(
                    FumenTableEntry.fumen_id == Fumen.fumen_id,
                    FumenTableEntry.table_id == course.source_table_id,
                ),
            )
            .where(hash_condition)
        )
        stage_rows = stage_result.all()

        # For new_balgwang courses, also query balgwang as a level fallback
        fallback_rows: list[Any] = []
        fallback_table_symbol: str | None = None
        if source_table_slug == "new_balgwang":
            balgwang_result = await db.execute(
                select(DifficultyTable.id, DifficultyTable.symbol)
                .where(DifficultyTable.slug == "balgwang")
                .limit(1)
            )
            balgwang_row = balgwang_result.first()
            if balgwang_row:
                fallback_table_symbol = balgwang_row.symbol
                fb_result = await db.execute(
                    select(Fumen.sha256, Fumen.md5, Fumen.title, FumenTableEntry.level)
                    .outerjoin(
                        FumenTableEntry,
                        and_(
                            FumenTableEntry.fumen_id == Fumen.fumen_id,
                            FumenTableEntry.table_id == balgwang_row.id,
                        ),
                    )
                    .where(hash_condition)
                )
                fallback_rows = fb_result.all()
    else:
        stage_rows = []
        fallback_rows = []
        fallback_table_symbol = None

    return CourseRowDetailResponse(
        course_name=course.name,
        records=records,
        stages=[
            CourseStage(**stage)
            for stage in build_course_stages(
                course,
                stage_rows,
                fallback_rows=fallback_rows or None,
                table_symbol=source_table_symbol,
                fallback_table_symbol=fallback_table_symbol,
            )
        ],
    )


def _build_fumen_row_detail_record(
    score: UserScore,
    notes_total: int | None,
    keymode: int | None,
) -> RowDetailRecord:
    """Serialize one real fumen score row into lazy expanded detail."""
    rate = score.rate
    rank = score.rank
    if rate is None and score.exscore is not None and notes_total:
        rate, rank = _compute_rate_rank(score.exscore, notes_total)
    return RowDetailRecord(
        score_id=str(score.id),
        client_type=score.client_type,
        clear_type=display_clear_type(score.clear_type, exscore=score.exscore, rate=rate),
        min_bp=score.min_bp,
        rate=rate,
        rank=rank,
        exscore=score.exscore,
        play_count=score.play_count,
        judgment_detail=normalize_judgments(score.client_type, score.judgments),
        arrangement=decode_arrangement(score.client_type, score.options, keymode),
    )


@router.get("/row/{score_id}/row-detail", response_model=FumenRowDetailResponse)
async def get_score_row_detail(
    score_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(None),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> FumenRowDetailResponse:
    """Return lazy detail for one exact non-course score row."""
    target_user = await _resolve_target_user(user_id, current_user, db)
    score_result = await db.execute(
        select(UserScore).where(
            UserScore.id == score_id,
            UserScore.user_id == target_user.id,
            UserScore.fumen_hash_others.is_(None),
        )
    )
    score = score_result.scalar_one_or_none()
    if score is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Score row not found")

    identity_conditions = []
    if score.fumen_id:
        identity_conditions.append(Fumen.fumen_id == score.fumen_id)
    if score.fumen_sha256:
        identity_conditions.append(Fumen.sha256 == score.fumen_sha256)
    if score.fumen_md5:
        identity_conditions.append(Fumen.md5 == score.fumen_md5)
    if not identity_conditions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fumen not found")

    fumen_result = await db.execute(
        select(Fumen.fumen_id, Fumen.keymode, Fumen.notes_total)
        .where(or_(*identity_conditions))
        .limit(1)
    )
    fumen = fumen_result.one_or_none()
    if fumen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fumen not found")

    return FumenRowDetailResponse(
        fumen_id=str(fumen.fumen_id),
        keymode=fumen.keymode,
        detail_basis="score_row",
        records=[_build_fumen_row_detail_record(score, fumen.notes_total, fumen.keymode)],
    )


@router.get("/fumen/{fumen_id}/row-detail", response_model=FumenRowDetailResponse)
async def get_fumen_row_detail(
    fumen_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(None),
    as_of: str | None = Query(None, description="ISO date YYYY-MM-DD for historical filtering"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> FumenRowDetailResponse:
    """Return one best score record per client type for a fumen, identified by fumen_id UUID.

    Selection is by highest exscore, then highest clear_type, then latest timestamp.
    Course records (fumen_hash_others IS NOT NULL) are excluded.
    An ``as_of`` date filters to scores recorded/synced on or before that date.
    """
    # 1. Resolve fumen
    fumen_result = await db.execute(
        select(Fumen.fumen_id, Fumen.sha256, Fumen.md5, Fumen.keymode, Fumen.notes_total)
        .where(Fumen.fumen_id == fumen_id)
        .limit(1)
    )
    fumen_row = fumen_result.one_or_none()
    if fumen_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fumen not found")

    fumen_sha256 = fumen_row.sha256
    fumen_md5 = fumen_row.md5
    fumen_keymode = fumen_row.keymode
    notes_total = fumen_row.notes_total

    # 2. Resolve target user
    target_user = await _resolve_target_user(user_id, current_user, db)

    # 3. Build fumen identity condition
    # Include rows linked by fumen_id UUID, sha256, or md5-only (LR2) fallback
    identity_conditions = [UserScore.fumen_id == fumen_id]
    if fumen_sha256:
        identity_conditions.append(UserScore.fumen_sha256 == fumen_sha256)
    if fumen_md5:
        # LR2 rows: md5 matches, but fumen_sha256 is NULL (no sha256 recorded)
        identity_conditions.append(
            (UserScore.fumen_md5 == fumen_md5) & UserScore.fumen_sha256.is_(None)
        )

    base_condition = (
        UserScore.user_id == target_user.id,
        UserScore.fumen_hash_others.is_(None),
        or_(*identity_conditions),
    )

    query = select(UserScore).where(*base_condition)

    # 4. as_of date filter
    if as_of:
        try:
            as_of_date = date.fromisoformat(as_of)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="as_of must be in ISO format YYYY-MM-DD",
            )
        query = query.where(
            func.coalesce(UserScore.recorded_at, UserScore.synced_at).cast(Date) <= as_of_date
        )

    result = await db.execute(query)
    all_scores = result.scalars().all()

    # 5. Pick best representative per client
    representatives = pick_best_per_client(all_scores)

    # 6. Build records
    records: list[RowDetailRecord] = []
    for s in representatives:
        records.append(_build_fumen_row_detail_record(s, notes_total, fumen_keymode))

    return FumenRowDetailResponse(
        fumen_id=str(fumen_id),
        keymode=fumen_keymode,
        detail_basis="best_exscore_per_client",
        records=records,
    )


@router.get("/me/{fumen_sha256}", response_model=PerFieldBestScore)
async def get_score_for_song(
    fumen_sha256: str,
    client_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PerFieldBestScore:
    """Get per-field best scores for a specific fumen (by sha256).

    Fetches the most recent row per client type, then picks the best value
    per field across clients (MIX source_client if clients differ).
    """
    query = (
        select(UserScore)
        .where(
            UserScore.user_id == current_user.id,
            UserScore.fumen_sha256 == fumen_sha256,
            UserScore.fumen_hash_others.is_(None),
        )
        .order_by(UserScore.recorded_at.desc().nullslast())
    )
    if client_type:
        query = query.where(UserScore.client_type == client_type)

    result = await db.execute(query)
    all_rows = result.scalars().all()

    if not all_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Score not found")

    # Pick the most recent row per client_type
    per_client: dict[str, UserScore] = {}
    for s in all_rows:
        if s.client_type not in per_client:
            per_client[s.client_type] = s

    best = PerFieldBestScore()

    for s in per_client.values():
        label = CLIENT_LABEL.get(s.client_type, s.client_type.upper())
        clear_type = display_clear_type(s.clear_type, exscore=s.exscore, rate=s.rate)
        if clear_type is not None and (best.best_clear_type is None or clear_type > best.best_clear_type):
            best.best_clear_type = clear_type
            best.best_clear_type_client = label
        if s.exscore is not None and (best.best_exscore is None or s.exscore > best.best_exscore):
            best.best_exscore = s.exscore
            best.rate = s.rate
            best.rank = s.rank
            best.best_exscore_client = label
        if s.min_bp is not None and (best.best_min_bp is None or s.min_bp < best.best_min_bp):
            best.best_min_bp = s.min_bp
            best.best_min_bp_client = label
        if s.max_combo is not None and (best.best_max_combo is None or s.max_combo > best.best_max_combo):
            best.best_max_combo = s.max_combo
            best.best_max_combo_client = label

    per_client_bests = [
        PerClientBest(
            client_type=s.client_type,
            clear_type=s.clear_type,
            exscore=s.exscore,
            rate=s.rate,
            rank=s.rank,
            min_bp=s.min_bp,
        )
        for s in per_client.values()
    ]
    best.source_client, best.source_client_detail = aggregate_source_client(per_client_bests)

    return best
