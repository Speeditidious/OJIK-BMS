"""Difficulty table endpoints: list, favorites, import, sync, fumen query."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    get_current_admin,
    get_current_user,
    get_current_user_optional,
)
from app.models.difficulty_table import DifficultyTable, UserFavoriteDifficultyTable
from app.models.fumen import Fumen, FumenTableEntry
from app.models.table_import import TableImportLog, TableSourceAlias
from app.models.user import User
from app.schemas import MessageResponse
from app.services.default_table_order import sort_difficulty_tables
from app.services.fumen_user_scores import (
    TableFumenScore,
    UserTagRead,
    fetch_user_score_map,
    fetch_user_tag_map,
)
from app.services.level_display_preferences import (
    resolve_non_regular_hidden_levels,
    resolve_visible_table_ids,
)

router = APIRouter(prefix="/tables", tags=["tables"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

def _representative_site_url(site: str | None) -> str | None:
    """Return a public representative-site URL only when it is web-link shaped."""
    value = (site or "").strip()
    if value.startswith(("http://", "https://")):
        return value
    return None


class DifficultyTableRead(BaseModel):
    id: uuid.UUID
    name: str
    symbol: str | None
    slug: str | None
    source_url: str | None
    site: str | None = None
    representative_site_url: str | None = None
    is_default: bool
    updated_at: datetime | None = None
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
            site=table.site,
            representative_site_url=_representative_site_url(table.site),
            is_default=table.is_default,
            updated_at=table.updated_at,
            song_count=count,
        )


class TableFumen(BaseModel):
    fumen_id: uuid.UUID
    level: str
    md5: str | None
    sha256: str | None
    title: str | None
    artist: str | None
    file_url: str | None
    file_url_diff: str | None = None
    bpm_main: float | None = None
    bpm_min: float | None = None
    bpm_max: float | None = None
    notes_total: int | None = None
    notes_n: int | None = None
    notes_ln: int | None = None
    notes_s: int | None = None
    notes_ls: int | None = None
    total: int | None = None
    length: int | None = None
    youtube_url: str | None = None
    table_entries: list[Any] | None
    user_score: TableFumenScore | None = None
    user_tags: list[UserTagRead] = []

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


class TableImportQuotaRead(BaseModel):
    created_limit: int
    created_used: int
    created_remaining: int
    failed_limit: int
    failed_used: int
    failed_remaining: int
    created_reset_at: datetime
    failed_reset_at: datetime


class ImportTableResponse(BaseModel):
    table: DifficultyTableRead
    outcome: Literal["created", "duplicate"]
    message: str
    quota: TableImportQuotaRead | None = None


# ── List & detail ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[DifficultyTableRead])
async def list_tables(
    db: AsyncSession = Depends(get_db),
) -> list[DifficultyTableRead]:
    """List all difficulty tables."""
    result = await db.execute(
        select(DifficultyTable).order_by(
            DifficultyTable.is_default.desc(),
            DifficultyTable.default_order.asc().nulls_last(),
            DifficultyTable.name,
        )
    )
    tables = list(result.scalars().all())
    tables = sort_difficulty_tables(tables)

    count_result = await db.execute(
        select(FumenTableEntry.table_id, func.count())
        .select_from(FumenTableEntry)
        .group_by(FumenTableEntry.table_id)
    )
    counts: dict[str, int] = {str(row[0]): row[1] for row in count_result.all()}

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


@router.get("/favorites/by-user/{user_id}", response_model=list[DifficultyTableRead])
async def get_user_favorites(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DifficultyTableRead]:
    """Get a user's favorite tables ordered by display_order."""
    result = await db.execute(
        select(DifficultyTable)
        .join(UserFavoriteDifficultyTable, DifficultyTable.id == UserFavoriteDifficultyTable.table_id)
        .where(UserFavoriteDifficultyTable.user_id == user_id)
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

    count_result = await db.execute(
        select(func.count())
        .select_from(FumenTableEntry)
        .where(FumenTableEntry.table_id == table_id)
    )
    song_count: int | None = count_result.scalar()

    obj = DifficultyTableRead.from_orm_with_count(table, song_count)
    return TableDetailRead(**obj.model_dump(), level_order=level_order)

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

    query = (
        select(Fumen, FumenTableEntry.level)
        .join(FumenTableEntry, FumenTableEntry.fumen_id == Fumen.fumen_id)
        .where(FumenTableEntry.table_id == table_id)
    )
    if level is not None:
        query = query.where(FumenTableEntry.level == level)
    result = await db.execute(query)
    rows = result.all()
    filtered_fumens = [row[0] for row in rows]

    fumen_level_map: dict[uuid.UUID, str] = {row[0].fumen_id: row[1] for row in rows}
    visible_table_ids = await resolve_visible_table_ids(db, current_user)
    non_regular_hidden = await resolve_non_regular_hidden_levels(db, current_user)
    table_entries_map = await _table_entries_map(
        db,
        [f.fumen_id for f in filtered_fumens],
        visible_table_ids=visible_table_ids,
        non_regular_hidden=non_regular_hidden,
    )

    # Fetch per-field best scores and tags for the logged-in user
    score_map: dict[tuple[str | None, str | None], TableFumenScore] = {}
    tag_map: dict[tuple[str | None, str | None], list[UserTagRead]] = {}
    if current_user and filtered_fumens:
        score_map = await fetch_user_score_map(db, current_user.id, filtered_fumens)
        tag_map = await fetch_user_tag_map(db, current_user.id, filtered_fumens)

    results: list[TableFumen] = []
    for f in filtered_fumens:
        results.append(
            TableFumen(
                fumen_id=f.fumen_id,
                level=fumen_level_map[f.fumen_id],
                md5=f.md5,
                sha256=f.sha256,
                title=f.title,
                artist=f.artist,
                file_url=f.file_url,
                file_url_diff=f.file_url_diff,
                bpm_main=f.bpm_main,
                bpm_min=f.bpm_min,
                bpm_max=f.bpm_max,
                notes_total=f.notes_total,
                notes_n=f.notes_n,
                notes_ln=f.notes_ln,
                notes_s=f.notes_s,
                notes_ls=f.notes_ls,
                total=f.total,
                length=f.length,
                youtube_url=f.youtube_url,
                table_entries=table_entries_map.get(f.fumen_id, []),
                user_score=score_map.get(f.fumen_id),
                user_tags=tag_map.get(f.fumen_id, []),
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
    table = await _get_table_or_404(table_id, db)

    existing = await db.execute(
        select(UserFavoriteDifficultyTable).where(
            UserFavoriteDifficultyTable.user_id == current_user.id,
            UserFavoriteDifficultyTable.table_id == table_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        if table.default_order is not None:
            initial_order = table.default_order
        else:
            order_result = await db.execute(
                select(func.count()).select_from(UserFavoriteDifficultyTable).where(
                    UserFavoriteDifficultyTable.user_id == current_user.id
                )
            )
            initial_order = order_result.scalar() or 0
        db.add(
            UserFavoriteDifficultyTable(
                user_id=current_user.id,
                table_id=table_id,
                display_order=initial_order,
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

@router.get("/import/quota", response_model=TableImportQuotaRead)
async def get_import_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableImportQuotaRead:
    """Return the current user's table import quota state."""
    return await _get_import_quota(current_user.id, db)


@router.post("/import", response_model=ImportTableResponse, status_code=status.HTTP_201_CREATED)
async def import_table(
    body: ImportTableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportTableResponse:
    """Import an external difficulty table by URL.

    If a table with the same source_url already exists, returns it instead of
    creating a duplicate. The table is fetched and parsed immediately; on
    success it is added to the user's favorites.
    """
    from app.parsers.table_fetcher import fetch_table
    from app.services.table_sync import canonicalize_table_url

    source_url = canonicalize_table_url(body.url)

    existing = await _find_existing_import_table(source_url, db)
    if existing is not None:
        song_count = await _count_table_fumens(existing.id, db)
        await _ensure_favorite(current_user.id, existing.id, db)
        _add_table_import_log(db, current_user.id, source_url, "duplicate")
        await db.commit()
        await db.refresh(existing)
        return ImportTableResponse(
            table=DifficultyTableRead.from_orm_with_count(existing, song_count),
            outcome="duplicate",
            message="이미 존재하는 난이도표라 즐겨찾기에 추가했습니다.",
            quota=await _get_import_quota(current_user.id, db),
        )

    quota = await _get_import_quota(current_user.id, db)
    if quota.failed_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="비정상적인 요청 방지를 위해 1시간 5회로 제한했습니다.",
        )
    if quota.created_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="해당 난이도표 사이트에 비정상적인 요청을 방지하기 위해 하루 5회로 제한했습니다.",
        )

    # Fetch and parse
    try:
        table_data = await _fetch_import_table_data(source_url, fetch_table)
    except HTTPException as exc:
        _add_table_import_log(db, current_user.id, source_url, "failed", str(exc.detail))
        await db.commit()
        raise

    header = table_data.get("header", {})
    name: str = header.get("name") or body.url

    new_table = DifficultyTable(
        name=name,
        source_url=source_url,
        is_default=False,
    )
    db.add(new_table)
    await db.flush()

    song_count = await _populate_imported_table(new_table, table_data, db)
    await _ensure_favorite(current_user.id, new_table.id, db)
    _add_table_import_log(db, current_user.id, source_url, "created")
    await db.commit()
    await db.refresh(new_table)

    return ImportTableResponse(
        table=DifficultyTableRead.from_orm_with_count(new_table, song_count),
        outcome="created",
        message="난이도표를 추가했습니다.",
        quota=await _get_import_quota(current_user.id, db),
    )


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


async def _find_existing_import_table(source_url: str, db: AsyncSession) -> DifficultyTable | None:
    """Find an existing table by canonical source URL or admin-registered alias."""
    result = await db.execute(select(DifficultyTable).where(DifficultyTable.source_url == source_url))
    table = result.scalar_one_or_none()
    if table is not None:
        return table

    alias_result = await db.execute(
        select(DifficultyTable)
        .join(TableSourceAlias, TableSourceAlias.table_id == DifficultyTable.id)
        .where(TableSourceAlias.alias_url == source_url)
    )
    return alias_result.scalar_one_or_none()


async def _fetch_import_table_data(url: str, fetch_table: Any) -> dict:
    """Fetch and validate difficulty table data for user-driven imports."""
    import httpx

    try:
        table_data = await fetch_table(url)
    except ValueError as exc:
        detail = str(exc)
        if "No <meta name='bmstable'>" in detail or "data_url" in detail or "not a JSON array" in detail:
            message = "난이도표 URL이 아닙니다."
        else:
            message = "유효하지 않은 난이도표 링크입니다."
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"URL 접근에 실패했습니다. Error Code: {exc.response.status_code}",
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"URL 접근에 실패했습니다. Error Code: {exc}",
        )
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

    return table_data


async def _get_import_quota(user_id: uuid.UUID, db: AsyncSession) -> TableImportQuotaRead:
    """Return quota usage for created and failed user table imports."""
    now = datetime.now(UTC)
    created_since = now - timedelta(hours=24)
    failed_since = now - timedelta(hours=1)
    created_limit = 5
    failed_limit = 5

    created_result = await db.execute(
        select(func.count())
        .select_from(TableImportLog)
        .where(
            TableImportLog.user_id == user_id,
            TableImportLog.outcome == "created",
            TableImportLog.created_at >= created_since,
        )
    )
    failed_result = await db.execute(
        select(func.count())
        .select_from(TableImportLog)
        .where(
            TableImportLog.user_id == user_id,
            TableImportLog.outcome == "failed",
            TableImportLog.created_at >= failed_since,
        )
    )
    created_used = int(created_result.scalar() or 0)
    failed_used = int(failed_result.scalar() or 0)
    return TableImportQuotaRead(
        created_limit=created_limit,
        created_used=created_used,
        created_remaining=max(created_limit - created_used, 0),
        failed_limit=failed_limit,
        failed_used=failed_used,
        failed_remaining=max(failed_limit - failed_used, 0),
        created_reset_at=now + timedelta(hours=24),
        failed_reset_at=now + timedelta(hours=1),
    )


def _add_table_import_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    source_url: str,
    outcome: Literal["created", "duplicate", "failed"],
    error_detail: str | None = None,
) -> None:
    db.add(
        TableImportLog(
            user_id=user_id,
            source_url=source_url,
            outcome=outcome,
            error_detail=error_detail,
        )
    )


async def _populate_imported_table(
    table: DifficultyTable,
    table_data: dict,
    db: AsyncSession,
) -> int:
    """Persist parsed import data into fumen/course tables and return fumen count."""
    from app.services.table_import import upsert_courses, upsert_fumens

    header = table_data.get("header", {})
    table.name = header.get("name") or table.name
    table.symbol = header.get("symbol") or table_data.get("symbol") or table.symbol
    table.level_order = table_data.get("level_order") or header.get("level_order")
    table.updated_at = datetime.now(UTC)

    await upsert_fumens(db, table.id, table_data.get("songs", []))
    await upsert_courses(db, table.id, table_data.get("courses", []))
    await db.flush()

    return await _count_table_fumens(table.id, db)


async def _count_table_fumens(table_id: uuid.UUID, db: AsyncSession) -> int:
    """Return the number of fumen rows linked to a difficulty table."""
    result = await db.execute(
        select(func.count())
        .select_from(FumenTableEntry)
        .where(FumenTableEntry.table_id == table_id)
    )
    return int(result.scalar() or 0)


async def _table_entries_map(
    db: AsyncSession,
    fumen_ids: list[uuid.UUID],
    visible_table_ids: set[uuid.UUID] | None = None,
    non_regular_hidden: dict[uuid.UUID, set[str]] | None = None,
) -> dict[uuid.UUID, list[dict[str, str]]]:
    """Return legacy-shaped table_entries lists for API compatibility."""
    if not fumen_ids:
        return {}
    if visible_table_ids is not None and not visible_table_ids:
        return {fid: [] for fid in fumen_ids}
    query = (
        select(FumenTableEntry.fumen_id, FumenTableEntry.table_id, FumenTableEntry.level)
        .where(FumenTableEntry.fumen_id.in_(fumen_ids))
    )
    if visible_table_ids is not None:
        query = query.where(FumenTableEntry.table_id.in_(visible_table_ids))
    result = await db.execute(query)
    out: dict[uuid.UUID, list[dict[str, str]]] = {fid: [] for fid in fumen_ids}
    for fumen_id, table_id, entry_level in result.all():
        if non_regular_hidden and entry_level in non_regular_hidden.get(table_id, set()):
            continue
        out.setdefault(fumen_id, []).append({"table_id": str(table_id), "level": entry_level})
    return out


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
