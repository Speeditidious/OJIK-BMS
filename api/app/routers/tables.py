"""Difficulty table endpoints: list, favorites, import, sync, fumen query."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    get_current_admin,
    get_current_user,
    get_current_user_optional,
)
from app.models.difficulty_table import DifficultyTable, UserFavoriteDifficultyTable
from app.models.fumen import Fumen
from app.models.score import UserScore
from app.models.user import User
from app.schemas import MessageResponse

router = APIRouter(prefix="/tables", tags=["tables"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class DifficultyTableRead(BaseModel):
    id: uuid.UUID
    name: str
    symbol: str | None
    slug: str | None
    source_url: str | None
    is_default: bool
    song_count: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_count(cls, table: DifficultyTable, count: int | None = None) -> DifficultyTableRead:
        return cls(
            id=table.id,
            name=table.name,
            symbol=table.symbol,
            slug=table.slug,
            source_url=table.source_url,
            is_default=table.is_default,
            song_count=count,
        )


class TableFumenScore(BaseModel):
    """Per-field best scores for a fumen, derived from is_best_* flags."""
    best_clear_type: int | None
    best_exscore: int | None
    rate: float | None
    rank: str | None
    best_min_bp: int | None
    source_client: str | None          # "LR", "BR", "MIX", or None
    source_client_detail: dict | None  # e.g. {"clear_type": "LR", "exscore": "BR", "min_bp": "BR"}


class TableFumen(BaseModel):
    level: str
    md5: str | None
    sha256: str | None
    title: str | None
    artist: str | None
    file_url: str | None
    table_entries: list[Any] | None
    user_score: TableFumenScore | None = None

    model_config = ConfigDict(from_attributes=True)


class TableDetailRead(DifficultyTableRead):
    level_order: list[str] = []


class ImportTableRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()


class FavoriteReorderRequest(BaseModel):
    table_ids: list[uuid.UUID]


# ── List & detail ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[DifficultyTableRead])
async def list_tables(
    db: AsyncSession = Depends(get_db),
) -> list[DifficultyTableRead]:
    """List all difficulty tables."""
    result = await db.execute(
        select(DifficultyTable).order_by(DifficultyTable.is_default.desc(), DifficultyTable.name)
    )
    tables = result.scalars().all()

    # Get fumen counts per table in one query
    _elem = cast(func.jsonb_array_elements(Fumen.table_entries), JSONB)
    _table_id_col = _elem["table_id"].as_string()
    count_result = await db.execute(
        select(_table_id_col, func.count())
        .select_from(Fumen)
        .where(Fumen.table_entries.isnot(None))
        .group_by(_table_id_col)
    )
    counts: dict[str, int] = {row[0]: row[1] for row in count_result.all()}

    return [DifficultyTableRead.from_orm_with_count(t, counts.get(str(t.id))) for t in tables]


@router.get("/favorites/me", response_model=list[DifficultyTableRead])
async def get_my_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DifficultyTableRead]:
    """Get the current user's favorite tables ordered by display_order."""
    result = await db.execute(
        select(DifficultyTable)
        .join(UserFavoriteDifficultyTable, DifficultyTable.id == UserFavoriteDifficultyTable.table_id)
        .where(UserFavoriteDifficultyTable.user_id == current_user.id)
        .order_by(UserFavoriteDifficultyTable.display_order)
    )
    tables = result.scalars().all()
    return [DifficultyTableRead.from_orm_with_count(t) for t in tables]


@router.get("/{table_id}", response_model=TableDetailRead)
async def get_table(
    table_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TableDetailRead:
    """Get a specific difficulty table with level_order."""
    table = await _get_table_or_404(table_id, db)
    level_order: list[str] = table.level_order or []
    obj = DifficultyTableRead.from_orm_with_count(table)
    return TableDetailRead(**obj.model_dump(), level_order=level_order)


_CLIENT_LABEL = {"lr2": "LR", "beatoraja": "BR"}


@router.get("/{table_id}/songs", response_model=list[TableFumen])
async def get_table_songs(
    table_id: uuid.UUID,
    level: str | None = Query(default=None, description="Filter by level (e.g. sl0)"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[TableFumen]:
    """Get fumens for a difficulty table, optionally filtered by level.

    When authenticated, includes per-field best user scores for each fumen.
    """
    await _get_table_or_404(table_id, db)

    table_id_str = str(table_id)
    query = select(Fumen).where(
        Fumen.table_entries.contains([{"table_id": table_id_str}])
    )
    result = await db.execute(query)
    fumens = result.scalars().all()

    # Build level map and apply optional level filter
    fumen_level_map: dict[tuple[str | None, str | None], str] = {}
    filtered_fumens: list[Fumen] = []
    for f in fumens:
        entries: list[dict] = f.table_entries or []
        fumen_level: str = ""
        for entry in entries:
            if entry.get("table_id") == table_id_str:
                fumen_level = str(entry.get("level", "")).strip()
                break
        if level is not None and fumen_level != level:
            continue
        fumen_level_map[(f.sha256, f.md5)] = fumen_level
        filtered_fumens.append(f)

    # Fetch per-field best scores for the logged-in user (2 queries max)
    score_map: dict[tuple[str | None, str | None], TableFumenScore] = {}
    if current_user and filtered_fumens:
        sha256_list = [f.sha256 for f in filtered_fumens if f.sha256]
        md5_list = [f.md5 for f in filtered_fumens if f.md5 and not f.sha256]

        score_conditions = []
        if sha256_list:
            score_conditions.append(UserScore.fumen_sha256.in_(sha256_list))
        if md5_list:
            score_conditions.append(
                (UserScore.fumen_md5.in_(md5_list)) & UserScore.fumen_sha256.is_(None)
            )

        if score_conditions:
            combined = score_conditions[0]
            for c in score_conditions[1:]:
                combined = combined | c

            score_rows_result = await db.execute(
                select(UserScore).where(
                    UserScore.user_id == current_user.id,
                    UserScore.fumen_hash_others.is_(None),
                    combined,
                ).order_by(UserScore.recorded_at.desc().nullslast())
            )
            score_rows = score_rows_result.scalars().all()

            # Per-fumen: pick the most recent row per client_type, then take best per field
            per_fumen_client: dict[tuple[str | None, str | None], dict[str, Any]] = {}
            for s in score_rows:
                key = (s.fumen_sha256, s.fumen_md5 if not s.fumen_sha256 else None)
                per_client = per_fumen_client.setdefault(key, {})
                # Already ordered by recorded_at DESC — keep first (most recent) per client_type
                if s.client_type not in per_client:
                    per_client[s.client_type] = s

            for key, per_client in per_fumen_client.items():
                raw: dict[str, Any] = {
                    "clear_type": None, "clear_type_client": None,
                    "exscore": None, "rate": None, "rank": None, "exscore_client": None,
                    "min_bp": None, "min_bp_client": None,
                }
                for ct, s in per_client.items():
                    client_label = _CLIENT_LABEL.get(ct, ct)
                    if s.clear_type is not None and (raw["clear_type"] is None or s.clear_type > raw["clear_type"]):
                        raw["clear_type"] = s.clear_type
                        raw["clear_type_client"] = client_label
                    if s.exscore is not None and (raw["exscore"] is None or s.exscore > raw["exscore"]):
                        raw["exscore"] = s.exscore
                        raw["rate"] = s.rate
                        raw["rank"] = s.rank
                        raw["exscore_client"] = client_label
                    if s.min_bp is not None and (raw["min_bp"] is None or s.min_bp < raw["min_bp"]):
                        raw["min_bp"] = s.min_bp
                        raw["min_bp_client"] = client_label

                clients = {
                    v for k, v in raw.items()
                    if k.endswith("_client") and v is not None
                }
                if len(clients) > 1:
                    source_client = "MIX"
                    source_client_detail = {
                        "clear_type": raw["clear_type_client"],
                        "exscore": raw["exscore_client"],
                        "min_bp": raw["min_bp_client"],
                    }
                elif len(clients) == 1:
                    source_client = next(iter(clients))
                    source_client_detail = None
                else:
                    source_client = None
                    source_client_detail = None

                score_map[key] = TableFumenScore(
                    best_clear_type=raw["clear_type"],
                    best_exscore=raw["exscore"],
                    rate=raw["rate"],
                    rank=raw["rank"],
                    best_min_bp=raw["min_bp"],
                    source_client=source_client,
                    source_client_detail=source_client_detail,
                )

    results: list[TableFumen] = []
    for f in filtered_fumens:
        key = (f.sha256, f.md5 if not f.sha256 else None)
        results.append(
            TableFumen(
                level=fumen_level_map[(f.sha256, f.md5)],
                md5=f.md5,
                sha256=f.sha256,
                title=f.title,
                artist=f.artist,
                file_url=f.file_url,
                table_entries=f.table_entries,
                user_score=score_map.get(key),
            )
        )

    results.sort(key=lambda f: (f.level, (f.title or "").lower()))
    return results


# ── Favorites ────────────────────────────────────────────────────────────────

@router.post("/favorites/{table_id}", response_model=MessageResponse)
async def add_favorite(
    table_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Add a table to the current user's favorites."""
    await _get_table_or_404(table_id, db)

    existing = await db.execute(
        select(UserFavoriteDifficultyTable).where(
            UserFavoriteDifficultyTable.user_id == current_user.id,
            UserFavoriteDifficultyTable.table_id == table_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        order_result = await db.execute(
            select(func.count()).select_from(UserFavoriteDifficultyTable).where(
                UserFavoriteDifficultyTable.user_id == current_user.id
            )
        )
        current_count = order_result.scalar() or 0
        db.add(
            UserFavoriteDifficultyTable(
                user_id=current_user.id,
                table_id=table_id,
                display_order=current_count,
            )
        )
        await db.commit()

    return MessageResponse(message="Table added to favorites")


@router.delete("/favorites/{table_id}", response_model=MessageResponse)
async def remove_favorite(
    table_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Remove a table from favorites."""
    result = await db.execute(
        select(UserFavoriteDifficultyTable).where(
            UserFavoriteDifficultyTable.user_id == current_user.id,
            UserFavoriteDifficultyTable.table_id == table_id,
        )
    )
    favorite = result.scalar_one_or_none()
    if favorite is not None:
        await db.delete(favorite)
        await db.commit()

    return MessageResponse(message="Table removed from favorites")


@router.put("/favorites/reorder", response_model=MessageResponse)
async def reorder_favorites(
    body: FavoriteReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Reorder favorites by providing an ordered list of table IDs."""
    result = await db.execute(
        select(UserFavoriteDifficultyTable).where(
            UserFavoriteDifficultyTable.user_id == current_user.id
        )
    )
    favorites: dict[uuid.UUID, UserFavoriteDifficultyTable] = {
        f.table_id: f for f in result.scalars().all()
    }

    for order, table_id in enumerate(body.table_ids):
        if table_id in favorites:
            favorites[table_id].display_order = order

    await db.commit()
    return MessageResponse(message="Favorites reordered")


# ── Import & manual sync ──────────────────────────────────────────────────────

@router.post("/import", response_model=DifficultyTableRead, status_code=status.HTTP_201_CREATED)
async def import_table(
    body: ImportTableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DifficultyTableRead:
    """Import an external difficulty table by URL.

    If a table with the same source_url already exists, returns it instead of
    creating a duplicate. The table is fetched and parsed immediately; on
    success it is added to the user's favorites.
    """
    from app.parsers.table_fetcher import fetch_table

    # Check for existing table with same URL
    existing_result = await db.execute(
        select(DifficultyTable).where(DifficultyTable.source_url == body.url)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        await _ensure_favorite(current_user.id, existing.id, db)
        return DifficultyTableRead.from_orm_with_count(existing)

    # Fetch and parse
    try:
        table_data = await fetch_table(body.url)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to fetch or parse table: {exc}",
        )

    if table_data is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Table source returned no data",
        )

    header = table_data.get("header", {})
    name: str = header.get("name") or body.url
    symbol: str | None = header.get("symbol")
    level_order: list | None = table_data.get("level_order") or header.get("level_order")

    new_table = DifficultyTable(
        name=name,
        symbol=symbol,
        source_url=body.url,
        is_default=False,
        level_order=level_order,
    )
    db.add(new_table)
    await db.flush()

    await _ensure_favorite(current_user.id, new_table.id, db)
    await db.commit()
    await db.refresh(new_table)

    return DifficultyTableRead.from_orm_with_count(new_table)


@router.post("/{table_id}/sync", response_model=MessageResponse)
async def sync_table(
    table_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Manually trigger a sync for a specific difficulty table (queues Celery task)."""
    await _get_table_or_404(table_id, db)

    from app.tasks.table_updater import update_difficulty_table
    update_difficulty_table.delay(str(table_id))

    return MessageResponse(message=f"Sync queued for table {table_id}")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_table_or_404(table_id: uuid.UUID, db: AsyncSession) -> DifficultyTable:
    result = await db.execute(select(DifficultyTable).where(DifficultyTable.id == table_id))
    table = result.scalar_one_or_none()
    if table is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    return table


async def _ensure_favorite(user_id: Any, table_id: uuid.UUID, db: AsyncSession) -> None:
    existing = await db.execute(
        select(UserFavoriteDifficultyTable).where(
            UserFavoriteDifficultyTable.user_id == user_id,
            UserFavoriteDifficultyTable.table_id == table_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        order_result = await db.execute(
            select(func.count()).select_from(UserFavoriteDifficultyTable).where(
                UserFavoriteDifficultyTable.user_id == user_id
            )
        )
        count = order_result.scalar() or 0
        db.add(UserFavoriteDifficultyTable(user_id=user_id, table_id=table_id, display_order=count))
