"""Score query endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.score import UserScore
from app.models.user import User

router = APIRouter(prefix="/scores", tags=["scores"])

_CLIENT_LABEL = {"lr2": "LR", "beatoraja": "BR"}


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
    recorded_at: str | None
    synced_at: str | None
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
            recorded_at=s.recorded_at.isoformat() if s.recorded_at else None,
            synced_at=s.synced_at.isoformat() if s.synced_at else None,
        )
        for s in scores
    ]


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
    clients_used: dict[str, str] = {}  # field → client_label

    for s in per_client.values():
        label = _CLIENT_LABEL.get(s.client_type, s.client_type)
        if s.clear_type is not None and (best.best_clear_type is None or s.clear_type > best.best_clear_type):
            best.best_clear_type = s.clear_type
            best.best_clear_type_client = label
            clients_used["clear_type"] = label
        if s.exscore is not None and (best.best_exscore is None or s.exscore > best.best_exscore):
            best.best_exscore = s.exscore
            best.rate = s.rate
            best.rank = s.rank
            best.best_exscore_client = label
            clients_used["exscore"] = label
        if s.min_bp is not None and (best.best_min_bp is None or s.min_bp < best.best_min_bp):
            best.best_min_bp = s.min_bp
            best.best_min_bp_client = label
            clients_used["min_bp"] = label
        if s.max_combo is not None and (best.best_max_combo is None or s.max_combo > best.best_max_combo):
            best.best_max_combo = s.max_combo
            best.best_max_combo_client = label
            clients_used["max_combo"] = label

    unique_clients = set(clients_used.values())
    if len(unique_clients) > 1:
        best.source_client = "MIX"
        best.source_client_detail = {
            k: v for k, v in {
                "clear_type": best.best_clear_type_client,
                "exscore": best.best_exscore_client,
                "min_bp": best.best_min_bp_client,
                "max_combo": best.best_max_combo_client,
            }.items() if v is not None
        }
    elif len(unique_clients) == 1:
        best.source_client = next(iter(unique_clients))

    return best
