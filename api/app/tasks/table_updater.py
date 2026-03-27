"""Celery tasks for fetching and updating difficulty tables."""
import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.table_updater.update_difficulty_table",
    bind=True,
    max_retries=2,
    default_retry_delay=3600,
)
def update_difficulty_table(self: Any, table_id: str) -> dict:
    """Fetch and update a single difficulty table from its source URL.

    table_id is passed as a string for Celery JSON serialization.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_update_difficulty_table(uuid.UUID(table_id)))
    except Exception as exc:
        logger.error(f"Failed to update table {table_id}: {exc}")
        raise self.retry(exc=exc)


async def _async_update_difficulty_table(table_id: uuid.UUID) -> dict:
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

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DifficultyTable).where(DifficultyTable.id == table_id)
        )
        table = result.scalar_one_or_none()

        if table is None:
            return {"status": "not_found", "table_id": table_id}

        if not table.source_url:
            return {"status": "no_url", "table_id": table_id}

        update_config = get_update_config()
        min_hours = update_config.get("min_request_interval_hours", 1)
        if table.updated_at:
            elapsed = datetime.now(UTC) - table.updated_at
            if elapsed.total_seconds() < min_hours * 3600:
                logger.info(
                    f"Skipping table {table_id} ({table.name}): last synced "
                    f"{elapsed.total_seconds() / 3600:.1f}h ago (min: {min_hours}h)"
                )
                return {"status": "skipped_too_recent", "table_id": table_id, "name": table.name}

        try:
            table_data = await fetch_table(table.source_url)

            if table.slug:
                save_table_to_disk(table.slug, table_data)

            table.level_order = table_data.get("level_order")

            header_symbol = table_data.get("symbol")
            if header_symbol:
                table.symbol = header_symbol
            elif table.symbol is None and table.slug:
                cfg_map = {c["slug"]: c for c in get_default_table_configs()}
                fallback = cfg_map.get(table.slug, {}).get("symbol")
                if fallback:
                    table.symbol = fallback

            seen_keys = await upsert_fumens(db, table_id, table_data.get("songs", []))
            removed = await remove_stale_entries(db, table_id, seen_keys)
            await upsert_courses(db, table_id, table_data.get("courses", []))
            await db.commit()

            logger.info(f"Updated DifficultyTable {table_id}: {table.name}, {len(seen_keys)} fumens")
            return {
                "status": "success",
                "table_id": table_id,
                "name": table.name,
                "fumen_count": len(seen_keys),
                "stale_removed": removed,
            }

        except Exception as exc:
            logger.error(f"Error updating table {table_id} ({table.source_url}): {exc}")
            raise


@celery_app.task(name="app.tasks.table_updater.update_all_difficulty_tables")
def update_all_difficulty_tables() -> dict:
    """Trigger updates for all difficulty tables that have a source URL."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_update_all_tables())
    except Exception as exc:
        logger.error(f"Failed to queue table updates: {exc}")
        raise


async def _async_update_all_tables() -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.difficulty_table import DifficultyTable
    from app.parsers.table_fetcher import get_default_table_configs

    excluded_slugs = {
        c["slug"] for c in get_default_table_configs()
        if not c.get("auto_update", True)
    }

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DifficultyTable.id, DifficultyTable.slug)
            .where(DifficultyTable.source_url.isnot(None))
        )
        rows = result.all()

    table_ids = [str(row[0]) for row in rows if row[1] not in excluded_slugs]

    if excluded_slugs:
        skipped = [row[1] for row in rows if row[1] in excluded_slugs]
        logger.info(f"Skipping auto-update for excluded tables: {skipped}")

    for table_id in table_ids:
        update_difficulty_table.delay(table_id)

    logger.info(f"Queued updates for {len(table_ids)} difficulty tables")
    return {"queued": len(table_ids), "table_ids": table_ids}
