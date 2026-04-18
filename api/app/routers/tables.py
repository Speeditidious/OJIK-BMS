"""Difficulty table endpoints: list, favorites, import, sync, fumen query."""
from __future__ import annotations

import math
import uuid
from datetime import datetime
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
from app.models.fumen import Fumen, UserFumenTag
from app.models.score import UserScore
from app.models.user import User
from app.schemas import MessageResponse
from app.services.client_aggregation import (
    CLIENT_LABEL,
    PerClientBest,
    aggregate_source_client,
)

router = APIRouter(prefix="/tables", tags=["tables"])


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


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class DifficultyTableRead(BaseModel):
    id: uuid.UUID
    name: str
    symbol: str | None
    slug: str | None
    source_url: str | None
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
            is_default=table.is_default,
            updated_at=table.updated_at,
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
    options: dict | None = None
    client_type: str | None = None
    play_count: int | None = None


class UserTagRead(BaseModel):
    id: str
    tag: str

    model_config = ConfigDict(from_attributes=True)


class TableFumen(BaseModel):
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
        .select_from(Fumen)
        .where(Fumen.table_entries.contains([{"table_id": str(table_id)}]))
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
        # md5-only fumens (no sha256 in fumens table)
        md5_list = [f.md5 for f in filtered_fumens if f.md5 and not f.sha256]
        # md5s for fumens that ALSO have sha256 — needed to find old md5-only user_scores rows
        # (e.g. LR2 rows stored before sha256 was available or LR2 which never has sha256)
        md5_for_sha256_fumens = [f.md5 for f in filtered_fumens if f.sha256 and f.md5]
        # Map: md5 → canonical (sha256, None) key, for normalizing md5-only rows below
        md5_to_key: dict[str, tuple[str | None, str | None]] = {
            f.md5: (f.sha256, None)
            for f in filtered_fumens
            if f.sha256 and f.md5
        }

        score_conditions = []
        if sha256_list:
            score_conditions.append(UserScore.fumen_sha256.in_(sha256_list))
        if md5_list:
            score_conditions.append(
                (UserScore.fumen_md5.in_(md5_list)) & UserScore.fumen_sha256.is_(None)
            )
        if md5_for_sha256_fumens:
            # Also fetch md5-only rows whose fumen now has sha256 (e.g. all LR2 rows)
            score_conditions.append(
                (UserScore.fumen_md5.in_(md5_for_sha256_fumens)) & UserScore.fumen_sha256.is_(None)
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

            # Per-fumen: accumulate per-field best across ALL rows per client_type
            # Structure: { fumen_key: { client_type: { "clear_type", "exscore", "rate", "rank", "min_bp", "options", "play_count" } } }
            per_fumen_client: dict[tuple[str | None, str | None], dict[str, dict[str, Any]]] = {}
            for s in score_rows:
                # Normalize key: md5-only rows for fumens that have sha256 → use (sha256, None)
                if s.fumen_sha256 is None and s.fumen_md5 and s.fumen_md5 in md5_to_key:
                    key = md5_to_key[s.fumen_md5]
                else:
                    key = (s.fumen_sha256, s.fumen_md5 if not s.fumen_sha256 else None)
                per_client = per_fumen_client.setdefault(key, {})
                ct = s.client_type
                if ct not in per_client:
                    per_client[ct] = {"clear_type": None, "exscore": None, "rate": None, "rank": None, "min_bp": None, "options": None, "play_count": None}
                entry = per_client[ct]
                if s.clear_type is not None and (entry["clear_type"] is None or s.clear_type > entry["clear_type"]):
                    entry["clear_type"] = s.clear_type
                    entry["options"] = s.options
                if s.exscore is not None and (entry["exscore"] is None or s.exscore > entry["exscore"]):
                    entry["exscore"] = s.exscore
                    entry["rate"] = s.rate
                    entry["rank"] = s.rank
                if s.min_bp is not None and (entry["min_bp"] is None or s.min_bp < entry["min_bp"]):
                    entry["min_bp"] = s.min_bp
                if s.play_count is not None:
                    entry["play_count"] = (entry["play_count"] or 0) + s.play_count

            for key, per_client in per_fumen_client.items():
                raw: dict[str, Any] = {
                    "clear_type": None, "clear_type_client": None,
                    "exscore": None, "rate": None, "rank": None, "exscore_client": None,
                    "min_bp": None, "min_bp_client": None,
                    "options": None, "best_client_type": None, "play_count": None,
                }
                for ct, entry in per_client.items():
                    client_label = CLIENT_LABEL.get(ct, ct.upper())
                    if entry["clear_type"] is not None and (raw["clear_type"] is None or entry["clear_type"] > raw["clear_type"]):
                        raw["clear_type"] = entry["clear_type"]
                        raw["clear_type_client"] = client_label
                        raw["options"] = entry["options"]
                        raw["best_client_type"] = ct
                    if entry["exscore"] is not None and (raw["exscore"] is None or entry["exscore"] > raw["exscore"]):
                        raw["exscore"] = entry["exscore"]
                        raw["rate"] = entry["rate"]
                        raw["rank"] = entry["rank"]
                        raw["exscore_client"] = client_label
                    if entry["min_bp"] is not None and (raw["min_bp"] is None or entry["min_bp"] < raw["min_bp"]):
                        raw["min_bp"] = entry["min_bp"]
                        raw["min_bp_client"] = client_label
                    raw["play_count"] = (raw["play_count"] or 0) + (entry["play_count"] or 0)

                source_client, source_client_detail = aggregate_source_client(
                    PerClientBest(
                        client_type=ct,
                        clear_type=entry["clear_type"],
                        exscore=entry["exscore"],
                        rate=entry["rate"],
                        rank=entry["rank"],
                        min_bp=entry["min_bp"],
                    )
                    for ct, entry in per_client.items()
                )

                # Compute rate/rank from exscore + notes_total when null (e.g. scorelog.db rows)
                rate = raw["rate"]
                rank = raw["rank"]
                if (rate is None or rank is None) and raw["exscore"] is not None:
                    notes_map = {
                        (f.sha256, f.md5 if not f.sha256 else None): f.notes_total
                        for f in filtered_fumens
                    }
                    nt = notes_map.get(key)
                    if nt:
                        rate, rank = _compute_rate_rank(raw["exscore"], nt)

                score_map[key] = TableFumenScore(
                    best_clear_type=raw["clear_type"],
                    best_exscore=raw["exscore"],
                    rate=rate,
                    rank=rank,
                    best_min_bp=raw["min_bp"],
                    source_client=source_client,
                    source_client_detail=source_client_detail,
                    options=raw["options"],
                    client_type=raw["best_client_type"],
                    play_count=raw["play_count"] or None,
                )

    # Fetch user tags for logged-in user
    tag_map: dict[tuple[str | None, str | None], list[UserTagRead]] = {}
    if current_user and filtered_fumens:
        sha256_list_tags = [f.sha256 for f in filtered_fumens if f.sha256]
        md5_list_tags = [f.md5 for f in filtered_fumens if f.md5 and not f.sha256]

        tag_conditions = []
        if sha256_list_tags:
            tag_conditions.append(UserFumenTag.fumen_sha256.in_(sha256_list_tags))
        if md5_list_tags:
            tag_conditions.append(
                (UserFumenTag.fumen_md5.in_(md5_list_tags)) & UserFumenTag.fumen_sha256.is_(None)
            )

        if tag_conditions:
            combined_tag = tag_conditions[0]
            for c in tag_conditions[1:]:
                combined_tag = combined_tag | c

            tag_rows_result = await db.execute(
                select(UserFumenTag).where(
                    UserFumenTag.user_id == current_user.id,
                    combined_tag,
                )
            )
            for tag in tag_rows_result.scalars().all():
                t_key = (tag.fumen_sha256, tag.fumen_md5 if not tag.fumen_sha256 else None)
                tag_map.setdefault(t_key, []).append(
                    UserTagRead(id=str(tag.id), tag=tag.tag)
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
                table_entries=f.table_entries,
                user_score=score_map.get(key),
                user_tags=tag_map.get(key, []),
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
