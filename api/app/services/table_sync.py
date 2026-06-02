"""Shared difficulty table synchronization service."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.difficulty_table import DifficultyTable
from app.parsers.table_fetcher import (
    fetch_table,
    get_default_table_configs,
    get_update_config,
    save_table_to_disk,
)
from app.services.table_import import (
    remove_stale_entries,
    upsert_courses,
    upsert_fumens,
)


def canonicalize_table_url(url: str) -> str:
    """Normalize admin-provided table URLs for source_url matching."""
    raw = url.strip()
    parsed = urlsplit(raw)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def auto_slug_for_url(url: str) -> str:
    """Return a deterministic slug for URL-only difficulty tables."""
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"url_{digest}"


def _normalize_db_level_order(slug: str, level_order: list[Any] | None) -> list[Any] | None:
    """Return the DB-facing level order with source-specific aliases applied."""
    if level_order is None:
        return None
    if slug == "gachimijoy":
        return ["?" if str(level) == "8" else level for level in level_order]
    return list(level_order)


@dataclass(frozen=True)
class TableSyncTarget:
    """Existing DB difficulty table selected for remote synchronization."""

    id: uuid.UUID
    slug: str | None
    name: str


async def list_table_sync_targets(
    *,
    slugs: list[str] | None = None,
    exclude_slugs: list[str] | None = None,
    default_only: bool = False,
    user_only: bool = False,
    respect_auto_update: bool = False,
) -> list[TableSyncTarget]:
    """Return DB difficulty tables with source URLs selected for sync."""
    if default_only and user_only:
        raise ValueError("default_only and user_only cannot both be true")
    requested_slugs = set(slugs) if slugs is not None else None
    excluded_slugs = set(exclude_slugs or [])
    default_configs = get_default_table_configs()
    default_slugs = {config["slug"] for config in default_configs}
    if respect_auto_update:
        excluded_slugs.update(
            config["slug"]
            for config in default_configs
            if not config.get("auto_update", True)
        )

    async with AsyncSessionLocal() as db:
        query = select(DifficultyTable.id, DifficultyTable.slug, DifficultyTable.name).where(
            DifficultyTable.source_url.isnot(None)
        )
        if requested_slugs is not None:
            query = query.where(DifficultyTable.slug.in_(requested_slugs))
        if excluded_slugs:
            query = query.where(DifficultyTable.slug.not_in(excluded_slugs))
        if default_only:
            query = query.where(DifficultyTable.is_default.is_(True))
        if user_only:
            query = query.where(DifficultyTable.is_default.is_(False))
        result = await db.execute(
            query.order_by(
                DifficultyTable.is_default.desc(),
                DifficultyTable.default_order,
                DifficultyTable.name,
            )
        )
        rows = result.all()

    return [
        TableSyncTarget(id=row[0], slug=row[1], name=row[2])
        for row in rows
        if (not default_only or row[1] in default_slugs or row[1] is None)
    ]


async def sync_table_by_url(
    url: str,
    *,
    is_default: bool = False,
    configured_slug: str | None = None,
    configured_name: str | None = None,
    symbol_fallback: str | None = None,
    default_order: int | None = None,
    save_disk_cache: bool = True,
    log_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Fetch a table by URL, upsert its DB rows, and return a summary."""
    canonical_url = canonicalize_table_url(url)

    try:
        await _log(log_id, f"Fetching {canonical_url}")
        await _set_log_status(log_id, "running")
        table_data = await fetch_table(canonical_url)
        summary = await _persist_table_data(
            canonical_url=canonical_url,
            table_data=table_data,
            is_default=is_default,
            configured_slug=configured_slug,
            configured_name=configured_name,
            symbol_fallback=symbol_fallback,
            default_order=default_order,
            save_disk_cache=save_disk_cache,
            log_id=log_id,
        )
        await _set_log_status(log_id, "success")
        return summary
    except Exception as exc:
        await _log(log_id, f"Sync failed: {exc}", level="error")
        await _set_log_status(log_id, "failed", error_message=str(exc))
        raise


async def sync_table_by_id(
    table_id: uuid.UUID,
    *,
    log_id: uuid.UUID | None = None,
    respect_min_interval: bool = True,
) -> dict[str, Any]:
    """Fetch and update an existing difficulty table by DB id."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(DifficultyTable).where(DifficultyTable.id == table_id))
        table = result.scalar_one_or_none()

    if table is None:
        await _log(log_id, f"Table not found: {table_id}", level="warning")
        await _set_log_status(log_id, "failed", error_message="Table not found")
        return {"status": "not_found", "table_id": str(table_id)}
    if not table.source_url:
        await _log(log_id, f"Table has no source_url: {table_id}", level="warning")
        await _set_log_status(log_id, "failed", error_message="Table has no source_url")
        return {"status": "no_url", "table_id": str(table_id)}

    if respect_min_interval and table.updated_at:
        update_config = get_update_config()
        min_hours = update_config.get("min_request_interval_hours", 1)
        elapsed = datetime.now(UTC) - table.updated_at
        if elapsed.total_seconds() < min_hours * 3600:
            message = (
                f"Skipping {table.name}: last synced "
                f"{elapsed.total_seconds() / 3600:.1f}h ago (min: {min_hours}h)"
            )
            await _log(log_id, message)
            await _set_log_status(log_id, "success")
            return {"status": "skipped_too_recent", "table_id": str(table_id), "name": table.name}

    cfg_symbol = None
    if table.slug:
        cfg_map = {config["slug"]: config for config in get_default_table_configs()}
        cfg_symbol = cfg_map.get(table.slug, {}).get("symbol")

    return await sync_table_by_url(
        table.source_url,
        is_default=table.is_default,
        configured_slug=table.slug,
        configured_name=table.name,
        symbol_fallback=cfg_symbol or table.symbol,
        default_order=table.default_order,
        save_disk_cache=True,
        log_id=log_id,
    )


async def _persist_table_data(
    *,
    canonical_url: str,
    table_data: dict[str, Any],
    is_default: bool,
    configured_slug: str | None,
    configured_name: str | None,
    symbol_fallback: str | None,
    default_order: int | None,
    save_disk_cache: bool,
    log_id: uuid.UUID | None,
) -> dict[str, Any]:
    header = table_data.get("header", {})
    songs = table_data.get("songs", [])
    courses = table_data.get("courses", [])
    slug = configured_slug or auto_slug_for_url(canonical_url)
    name = configured_name or header.get("name") or header.get("title") or urlsplit(canonical_url).netloc
    effective_symbol = symbol_fallback or table_data.get("symbol")
    db_level_order = _normalize_db_level_order(slug, table_data.get("level_order"))

    if save_disk_cache and slug:
        save_table_to_disk(slug, table_data)
        await _log(log_id, f"Saved disk cache difficulty_tables/{slug}")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            if configured_slug:
                result = await db.execute(select(DifficultyTable).where(DifficultyTable.slug == configured_slug))
            else:
                result = await db.execute(select(DifficultyTable).where(DifficultyTable.source_url == canonical_url))
            table = result.scalar_one_or_none()

            if table is None:
                table = DifficultyTable(
                    name=name,
                    symbol=effective_symbol,
                    slug=slug,
                    source_url=canonical_url,
                    is_default=is_default,
                    default_order=default_order,
                    level_order=db_level_order,
                )
                db.add(table)
                await db.flush()
                db_status = "inserted"
            else:
                table.name = name
                table.symbol = effective_symbol
                table.source_url = canonical_url
                if configured_slug:
                    table.slug = configured_slug
                elif not table.slug:
                    table.slug = slug
                if is_default:
                    table.is_default = True
                if default_order is not None:
                    table.default_order = default_order
                table.level_order = db_level_order
                table.updated_at = datetime.now(UTC)
                db_status = "updated"

            await _log(log_id, f"Upserting {len(songs)} fumens")
            seen_fumen_ids = await upsert_fumens(db, table.id, songs)
            removed = await remove_stale_entries(db, table.id, seen_fumen_ids)
            await _log(log_id, f"Removed {removed} stale table entries")
            course_summary = await upsert_courses(db, table.id, courses)
            await _log(log_id, f"Courses: {course_summary}")

            table_id = table.id
            table_name = table.name

    return {
        "status": "success",
        "db_status": db_status,
        "table_id": str(table_id),
        "name": table_name,
        "slug": slug,
        "fumen_count": len(seen_fumen_ids),
        "stale_removed": removed,
        "courses": course_summary,
    }


async def _log(log_id: uuid.UUID | None, message: str, *, level: str = "info") -> None:
    if log_id is None:
        return
    from app.services.admin_action_log import append_line

    await append_line(log_id, message, level=level)


async def _set_log_status(
    log_id: uuid.UUID | None,
    status: str,
    *,
    error_message: str | None = None,
) -> None:
    if log_id is None:
        return
    from app.services.admin_action_log import set_status

    await set_status(log_id, status, error_message=error_message)
