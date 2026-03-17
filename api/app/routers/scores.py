"""Score query endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.score import ScoreHistory, UserScore
from app.models.user import User

router = APIRouter(prefix="/scores", tags=["scores"])


class UserScoreRead(BaseModel):
    id: str
    user_id: str
    song_sha256: str
    client_type: str
    clear_type: int | None
    score_rate: float | None
    max_combo: int | None
    min_bp: int | None
    play_count: int
    model_config = ConfigDict(from_attributes=True)


class ScoreHistoryRead(BaseModel):
    id: str
    user_id: str
    song_sha256: str
    client_type: str
    clear_type: int | None
    old_clear_type: int | None
    score: float | None
    old_score: float | None
    model_config = ConfigDict(from_attributes=True)


@router.get("/me", response_model=List[UserScoreRead])
async def get_my_scores(
    client_type: Optional[str] = Query(None, description="Filter by client type: lr2, beatoraja, qwilight"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserScoreRead]:
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
            song_sha256=s.song_sha256,
            client_type=s.client_type,
            clear_type=s.clear_type,
            score_rate=s.score_rate,
            max_combo=s.max_combo,
            min_bp=s.min_bp,
            play_count=s.play_count,
        )
        for s in scores
    ]


@router.get("/me/{song_sha256}", response_model=UserScoreRead)
async def get_score_for_song(
    song_sha256: str,
    client_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserScoreRead:
    """Get current user's score for a specific song."""
    from fastapi import HTTPException, status

    query = select(UserScore).where(
        UserScore.user_id == current_user.id,
        UserScore.song_sha256 == song_sha256,
    )
    if client_type:
        query = query.where(UserScore.client_type == client_type)

    result = await db.execute(query)
    score = result.scalar_one_or_none()

    if score is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Score not found")

    return UserScoreRead(
        id=str(score.id),
        user_id=str(score.user_id),
        song_sha256=score.song_sha256,
        client_type=score.client_type,
        clear_type=score.clear_type,
        score_rate=score.score_rate,
        max_combo=score.max_combo,
        min_bp=score.min_bp,
        play_count=score.play_count,
    )


@router.get("/me/history", response_model=List[ScoreHistoryRead])
async def get_score_history(
    song_sha256: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ScoreHistoryRead]:
    """Get current user's score history."""
    query = select(ScoreHistory).where(ScoreHistory.user_id == current_user.id)

    if song_sha256:
        query = query.where(ScoreHistory.song_sha256 == song_sha256)

    query = query.order_by(ScoreHistory.played_at.desc()).limit(limit)
    result = await db.execute(query)
    histories = result.scalars().all()

    return [
        ScoreHistoryRead(
            id=str(h.id),
            user_id=str(h.user_id),
            song_sha256=h.song_sha256,
            client_type=h.client_type,
            clear_type=h.clear_type,
            old_clear_type=h.old_clear_type,
            score=h.score,
            old_score=h.old_score,
        )
        for h in histories
    ]
