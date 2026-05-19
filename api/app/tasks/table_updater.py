"""Celery tasks for fetching and updating difficulty tables."""
import asyncio
import logging
import uuid
from typing import Any

from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.table_updater.update_difficulty_table",
    bind=True,
    max_retries=2,
    default_retry_delay=3600,
)
def update_difficulty_table(
    self: Any,
    table_id: str,
    log_id: str | None = None,
    force: bool = True,
) -> dict:
    """Fetch and update a single difficulty table from its source URL.

    table_id is passed as a string for Celery JSON serialization.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            _async_update_difficulty_table(
                uuid.UUID(table_id),
                uuid.UUID(log_id) if log_id else None,
                force=force,
            )
        )
    except Exception as exc:
        logger.error(f"Failed to update table {table_id}: {exc}")
        raise self.retry(exc=exc)


async def _async_update_difficulty_table(
    table_id: uuid.UUID,
    log_id: uuid.UUID | None,
    *,
    force: bool = True,
) -> dict:
    from app.services.admin_action_log import refresh_parent_status
    from app.services.table_sync import sync_table_by_id

    result = await sync_table_by_id(
        table_id,
        log_id=log_id,
        respect_min_interval=not force,
    )
    logger.info(f"Updated DifficultyTable {table_id}: {result}")
    if log_id:
        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models.admin_action_log import AdminActionLog

        async with AsyncSessionLocal() as db:
            row_result = await db.execute(select(AdminActionLog.parent_log_id).where(AdminActionLog.id == log_id))
            parent_log_id = row_result.scalar_one_or_none()
        if parent_log_id:
            await refresh_parent_status(parent_log_id)
    return result


@celery_app.task(
    name="app.tasks.table_updater.update_difficulty_table_by_url",
    bind=True,
    max_retries=2,
    default_retry_delay=3600,
)
def update_difficulty_table_by_url(self: Any, url: str, log_id: str | None = None) -> dict:
    """Fetch and update a difficulty table from an arbitrary source URL."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            _async_update_difficulty_table_by_url(url, uuid.UUID(log_id) if log_id else None)
        )
    except Exception as exc:
        logger.error(f"Failed to update table by URL {url}: {exc}")
        raise self.retry(exc=exc)


async def _async_update_difficulty_table_by_url(url: str, log_id: uuid.UUID | None) -> dict:
    from app.services.table_sync import sync_table_by_url

    return await sync_table_by_url(url, is_default=False, save_disk_cache=True, log_id=log_id)


@celery_app.task(name="app.tasks.table_updater.update_all_difficulty_tables")
def update_all_difficulty_tables(
    slugs: list[str] | None = None,
    exclude_slugs: list[str] | None = None,
    log_id: str | None = None,
    default_only: bool = False,
    user_only: bool = False,
    force: bool = True,
    respect_auto_update: bool = False,
) -> dict:
    """Trigger updates for all difficulty tables that have a source URL."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            _async_update_all_tables(
                slugs=slugs,
                exclude_slugs=exclude_slugs,
                log_id=uuid.UUID(log_id) if log_id else None,
                default_only=default_only,
                user_only=user_only,
                force=force,
                respect_auto_update=respect_auto_update,
            )
        )
    except Exception as exc:
        logger.error(f"Failed to queue table updates: {exc}")
        raise


async def _async_update_all_tables(
    slugs: list[str] | None = None,
    exclude_slugs: list[str] | None = None,
    log_id: uuid.UUID | None = None,
    default_only: bool = False,
    user_only: bool = False,
    force: bool = True,
    respect_auto_update: bool = False,
) -> dict:
    from app.services.admin_action_log import (
        append_line,
        create_log,
        mark_task_id,
        refresh_parent_status,
        set_status,
    )
    from app.services.table_sync import list_table_sync_targets

    target_rows = await list_table_sync_targets(
        slugs=slugs,
        exclude_slugs=exclude_slugs,
        default_only=default_only,
        user_only=user_only,
        respect_auto_update=respect_auto_update,
    )

    if log_id:
        await set_status(log_id, "running")
        await append_line(log_id, f"Queueing {len(target_rows)} table sync jobs")

    table_ids: list[str] = []
    action_name = "sync_user_tables" if user_only else ("sync_default_tables" if default_only else "sync_all_tables")
    for index, row in enumerate(target_rows):
        table_id = str(row.id)
        table_ids.append(table_id)
        child_log_id = None
        if log_id:
            child_log_id = await create_log(
                action_name=action_name,
                target_kind="difficulty_table",
                target_id=table_id,
                target_label=row.name,
                parent_log_id=log_id,
            )
        task_kwargs = {"log_id": str(child_log_id) if child_log_id else None, "force": force}
        if user_only and not force:
            task_result = update_difficulty_table.apply_async(
                args=[table_id],
                kwargs=task_kwargs,
                countdown=index * 30,
            )
        else:
            task_result = update_difficulty_table.delay(table_id, **task_kwargs)
        if child_log_id and getattr(task_result, "id", None):
            await mark_task_id(child_log_id, task_result.id)

    if log_id:
        await refresh_parent_status(log_id)

    logger.info(f"Queued updates for {len(table_ids)} difficulty tables")
    return {"queued": len(table_ids), "table_ids": table_ids}
