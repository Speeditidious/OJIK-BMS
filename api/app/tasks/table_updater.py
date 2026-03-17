"""Celery tasks for fetching and updating difficulty tables."""
import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.table_updater.update_difficulty_table",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def update_difficulty_table(self: Any, table_id: int) -> dict:
    """Fetch and update a single difficulty table from its source URL."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_update_difficulty_table(table_id))
    except Exception as exc:
        logger.error(f"Failed to update table {table_id}: {exc}")
        raise self.retry(exc=exc)


async def _async_update_difficulty_table(table_id: int) -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.table import DifficultyTable
    from app.parsers.table_fetcher import (
        fetch_table,
        get_update_config,
        save_table_to_disk,
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

        # Enforce minimum request interval
        update_config = get_update_config()
        min_hours = update_config.get("min_request_interval_hours", 6)
        if table.last_synced_at:
            elapsed = datetime.now(UTC) - table.last_synced_at
            if elapsed.total_seconds() < min_hours * 3600:
                logger.info(
                    f"Skipping table {table_id} ({table.name}): last synced "
                    f"{elapsed.total_seconds() / 3600:.1f}h ago (min: {min_hours}h)"
                )
                return {"status": "skipped_too_recent", "table_id": table_id, "name": table.name}

        try:
            table_data = await fetch_table(
                table.source_url,
                last_modified=table.last_modified_header,
            )

            if table_data is None:
                # 304 Not Modified
                logger.info(f"Table {table_id} ({table.name}) not modified — skipping")
                return {"status": "not_modified", "table_id": table_id, "name": table.name}

            # Persist to local disk cache
            if table.slug:
                save_table_to_disk(table.slug, table_data)

            # Update DB
            table.table_data = table_data
            table.last_synced_at = datetime.now(UTC)
            await db.commit()

            logger.info(f"Updated DifficultyTable {table_id}: {table.name}")
            return {
                "status": "success",
                "table_id": table_id,
                "name": table.name,
                "song_count": len(table_data.get("songs", [])),
                "synced_at": table.last_synced_at.isoformat(),
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
    from app.models.table import DifficultyTable
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

    table_ids = [row[0] for row in rows if row[1] not in excluded_slugs]

    if excluded_slugs:
        skipped = [row[1] for row in rows if row[1] in excluded_slugs]
        logger.info(f"Skipping auto-update for excluded tables: {skipped}")

    for table_id in table_ids:
        update_difficulty_table.delay(table_id)

    logger.info(f"Queued updates for {len(table_ids)} difficulty tables")
    return {"queued": len(table_ids), "table_ids": table_ids}
