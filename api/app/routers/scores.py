"""Score query endpoints."""

import math
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.models.fumen import Fumen
from app.models.score import UserScore
from app.models.user import User
from app.services.client_aggregation import (
    CLIENT_LABEL,
    PerClientBest,
    aggregate_source_client,
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


class UserScoreRead(BaseModel):
    id: str
    user_id: str
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
            fumen_sha256=s.fumen_sha256,
            fumen_md5=s.fumen_md5,
            fumen_hash_others=s.fumen_hash_others,
            client_type=s.client_type,
            clear_type=s.clear_type,
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

    if len(hash_value) == 64:
        # sha256 lookup: find fumen's md5 to also fetch md5-only rows (e.g. LR2)
        fumen_condition = Fumen.sha256 == hash_value
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

    # Fetch first_synced_at for is_first_sync detection
    fst_result = await db.execute(select(User.first_synced_at).where(User.id == target_user.id))
    first_synced_at: dict | None = fst_result.scalar_one_or_none()

    def _is_first_sync(s: UserScore) -> bool:
        if not first_synced_at or s.synced_at is None:
            return False
        fst_str = first_synced_at.get(s.client_type)
        if not fst_str:
            return False
        fst = datetime.fromisoformat(fst_str)
        if fst.tzinfo is None:
            fst = fst.replace(tzinfo=UTC)
        return abs((s.synced_at - fst).total_seconds()) <= 3600

    # Fetch notes_total for rate/rank computation on rows where they're null (e.g. scorelog.db rows)
    notes_total: int | None = None
    if any(s.rate is None and s.exscore is not None for s in scores):
        fumen_result = await db.execute(select(Fumen.notes_total).where(fumen_condition).limit(1))
        notes_total = fumen_result.scalar_one_or_none()

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
            fumen_sha256=s.fumen_sha256,
            fumen_md5=s.fumen_md5,
            fumen_hash_others=s.fumen_hash_others,
            client_type=s.client_type,
            clear_type=s.clear_type,
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
        ))
    return out


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
        if s.clear_type is not None and (best.best_clear_type is None or s.clear_type > best.best_clear_type):
            best.best_clear_type = s.clear_type
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
