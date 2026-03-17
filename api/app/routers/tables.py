"""Difficulty table endpoints: list, favorites, import, sync, song query."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.models.table import DifficultyTable, UserFavoriteTable
from app.models.user import User
from app.schemas import MessageResponse

router = APIRouter(prefix="/tables", tags=["tables"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class DifficultyTableRead(BaseModel):
    id: int
    name: str
    symbol: str | None
    slug: str | None
    source_url: str | None
    is_default: bool
    last_synced_at: datetime | None
    song_count: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_count(cls, table: DifficultyTable) -> "DifficultyTableRead":
        song_count: int | None = None
        if table.table_data and "songs" in table.table_data:
            song_count = len(table.table_data["songs"])
        return cls(
            id=table.id,
            name=table.name,
            symbol=table.symbol,
            slug=table.slug,
            source_url=table.source_url,
            is_default=table.is_default,
            last_synced_at=table.last_synced_at,
            song_count=song_count,
        )


class TableSong(BaseModel):
    level: str
    md5: str
    sha256: str
    title: str
    artist: str
    url: str
    extra: dict[str, Any] = {}

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
    table_ids: list[int]


# ── List & detail ─────────────────────────────────────────────────────────────

@router.get("/", response_model=List[DifficultyTableRead])
async def list_tables(
    db: AsyncSession = Depends(get_db),
) -> List[DifficultyTableRead]:
    """List all difficulty tables (no table_data payload)."""
    result = await db.execute(
        select(DifficultyTable).order_by(DifficultyTable.is_default.desc(), DifficultyTable.name)
    )
    tables = result.scalars().all()
    return [DifficultyTableRead.from_orm_with_count(t) for t in tables]


@router.get("/favorites/me", response_model=List[DifficultyTableRead])
async def get_my_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DifficultyTableRead]:
    """Get the current user's favorite tables ordered by display_order."""
    result = await db.execute(
        select(DifficultyTable)
        .join(UserFavoriteTable, DifficultyTable.id == UserFavoriteTable.table_id)
        .where(UserFavoriteTable.user_id == current_user.id)
        .order_by(UserFavoriteTable.display_order)
    )
    tables = result.scalars().all()
    return [DifficultyTableRead.from_orm_with_count(t) for t in tables]


@router.get("/{table_id}", response_model=TableDetailRead)
async def get_table(
    table_id: int,
    db: AsyncSession = Depends(get_db),
) -> TableDetailRead:
    """Get a specific difficulty table with level_order (no song list)."""
    table = await _get_table_or_404(table_id, db)
    level_order: list[str] = []
    if table.table_data:
        level_order = table.table_data.get("level_order") or []
    obj = DifficultyTableRead.from_orm_with_count(table)
    return TableDetailRead(**obj.model_dump(), level_order=level_order)


@router.get("/{table_id}/songs", response_model=List[TableSong])
async def get_table_songs(
    table_id: int,
    level: str | None = Query(default=None, description="Filter by level (e.g. sl0)"),
    db: AsyncSession = Depends(get_db),
) -> List[TableSong]:
    """Get songs for a difficulty table, optionally filtered by level."""
    table = await _get_table_or_404(table_id, db)

    if not table.table_data or "songs" not in table.table_data:
        return []

    songs: list[dict] = table.table_data["songs"]
    if level is not None:
        songs = [s for s in songs if str(s.get("level", "")).strip() == level]

    result: list[TableSong] = []
    for s in songs:
        known = {"level", "md5", "sha256", "title", "artist", "url"}
        extra = {k: v for k, v in s.items() if k not in known}
        result.append(
            TableSong(
                level=str(s.get("level", "")).strip(),
                md5=s.get("md5") or "",
                sha256=s.get("sha256") or "",
                title=s.get("title") or "",
                artist=s.get("artist") or "",
                url=s.get("url") or "",
                extra=extra,
            )
        )
    result.sort(key=lambda s: (s.level, s.title.lower()))
    return result


# ── Favorites ────────────────────────────────────────────────────────────────

@router.post("/favorites/{table_id}", response_model=MessageResponse)
async def add_favorite(
    table_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Add a table to the current user's favorites."""
    await _get_table_or_404(table_id, db)

    existing = await db.execute(
        select(UserFavoriteTable).where(
            UserFavoriteTable.user_id == current_user.id,
            UserFavoriteTable.table_id == table_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        # Append at the end
        order_result = await db.execute(
            select(func.count()).select_from(UserFavoriteTable).where(
                UserFavoriteTable.user_id == current_user.id
            )
        )
        current_count = order_result.scalar() or 0
        db.add(
            UserFavoriteTable(
                user_id=current_user.id,
                table_id=table_id,
                display_order=current_count,
            )
        )
        await db.commit()

    return MessageResponse(message="Table added to favorites")


@router.delete("/favorites/{table_id}", response_model=MessageResponse)
async def remove_favorite(
    table_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Remove a table from favorites."""
    result = await db.execute(
        select(UserFavoriteTable).where(
            UserFavoriteTable.user_id == current_user.id,
            UserFavoriteTable.table_id == table_id,
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
        select(UserFavoriteTable).where(UserFavoriteTable.user_id == current_user.id)
    )
    favorites: dict[int, UserFavoriteTable] = {f.table_id: f for f in result.scalars().all()}

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
        # Add to favorites and return
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

    new_table = DifficultyTable(
        name=name,
        symbol=symbol,
        source_url=body.url,
        is_default=False,
        table_data=table_data,
        last_synced_at=datetime.utcnow(),
    )
    db.add(new_table)
    await db.flush()  # get the new id

    await _ensure_favorite(current_user.id, new_table.id, db)
    await db.commit()
    await db.refresh(new_table)

    return DifficultyTableRead.from_orm_with_count(new_table)


@router.post("/{table_id}/sync", response_model=MessageResponse)
async def sync_table(
    table_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Manually trigger a sync for a specific difficulty table (queues Celery task)."""
    await _get_table_or_404(table_id, db)

    from app.tasks.table_updater import update_difficulty_table
    update_difficulty_table.delay(table_id)

    return MessageResponse(message=f"Sync queued for table {table_id}")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_table_or_404(table_id: int, db: AsyncSession) -> DifficultyTable:
    result = await db.execute(select(DifficultyTable).where(DifficultyTable.id == table_id))
    table = result.scalar_one_or_none()
    if table is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    return table


async def _ensure_favorite(user_id: Any, table_id: int, db: AsyncSession) -> None:
    existing = await db.execute(
        select(UserFavoriteTable).where(
            UserFavoriteTable.user_id == user_id,
            UserFavoriteTable.table_id == table_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        order_result = await db.execute(
            select(func.count()).select_from(UserFavoriteTable).where(
                UserFavoriteTable.user_id == user_id
            )
        )
        count = order_result.scalar() or 0
        db.add(UserFavoriteTable(user_id=user_id, table_id=table_id, display_order=count))
