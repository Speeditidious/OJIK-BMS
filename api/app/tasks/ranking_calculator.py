"""Celery tasks for ranking recalculation."""
import asyncio
import logging
import uuid

from app.tasks import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine in a new or existing event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(
    name="app.tasks.ranking_calculator.recalculate_user_rankings",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def recalculate_user_rankings(self, user_id: str) -> dict:
    """Recalculate all table rankings for a single user (post-sync trigger)."""
    try:
        return _run_async(_async_recalculate_user(uuid.UUID(user_id)))
    except Exception as exc:
        logger.warning(f"Ranking recalc failed for user {user_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "user_id": user_id, "error": str(exc)}


@celery_app.task(
    name="app.tasks.ranking_calculator.recalculate_all_rankings",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def recalculate_all_rankings(self, table_slug: str | None = None, log_id: str | None = None) -> dict:
    """Recalculate rankings for all users. Optionally limit to a single table by slug."""
    try:
        return _run_async(_async_recalculate_all(table_slug, uuid.UUID(log_id) if log_id else None))
    except Exception as exc:
        logger.error(f"Bulk ranking recalc failed: {exc}")
        if log_id:
            _run_async(_mark_rank_log_failed(uuid.UUID(log_id), str(exc)))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "error": str(exc)}


async def _async_recalculate_user(user_id: uuid.UUID) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.ranking_calculator import recalculate_user
    from app.services.ranking_config import init_ranking_config

    async with AsyncSessionLocal() as db:
        config = await init_ranking_config(db)
        await recalculate_user(user_id, config, db)
        await db.commit()

    logger.info(f"Ranking recalculated for user {user_id}")
    return {"status": "ok", "user_id": str(user_id), "tables": len(config.tables)}


async def _mark_rank_log_failed(log_id: uuid.UUID, error_message: str) -> None:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.admin_action_log import AdminActionLog
    from app.services.admin_action_log import (
        append_line,
        refresh_parent_status,
        set_status,
    )

    await append_line(log_id, f"Ranking recalculation failed: {error_message}", level="error")
    await set_status(log_id, "failed", error_message=error_message)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AdminActionLog.parent_log_id).where(AdminActionLog.id == log_id))
        parent_log_id = result.scalar_one_or_none()
    if parent_log_id:
        await refresh_parent_status(parent_log_id)


async def _async_recalculate_all(table_slug: str | None = None, log_id: uuid.UUID | None = None) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.admin_action_log import (
        append_line,
        refresh_parent_status,
        set_status,
    )
    from app.services.ranking_calculator import (
        recalculate_table_bulk,
        select_ranking_user_ids,
    )
    from app.services.ranking_config import init_ranking_config
    from app.services.rating_derived_data import rebuild_user_rating_derived_data

    total_users = 0
    derived_rebuilds = 0
    if log_id:
        await set_status(log_id, "running")
        await append_line(log_id, f"Starting ranking recalculation: {table_slug or 'all tables'}")
    async with AsyncSessionLocal() as db:
        config = await init_ranking_config(db)
        targets = config.tables
        if table_slug is not None:
            targets = [t for t in targets if t.slug == table_slug]
        if not targets:
            result = {
                "status": "ok",
                "tables": 0,
                "total_users": 0,
                "derived_rebuilds": 0,
            }
            if log_id:
                await append_line(log_id, "No ranking tables matched")
                await set_status(log_id, "success")
                from sqlalchemy import select

                from app.models.admin_action_log import AdminActionLog

                async with AsyncSessionLocal() as parent_db:
                    parent_result = await parent_db.execute(
                        select(AdminActionLog.parent_log_id).where(AdminActionLog.id == log_id)
                    )
                    parent_log_id = parent_result.scalar_one_or_none()
                if parent_log_id:
                    await refresh_parent_status(parent_log_id)
            return result
        for table_cfg in targets:
            if log_id:
                await append_line(log_id, f"Recalculating table {table_cfg.slug}")
            count = await recalculate_table_bulk(table_cfg, config, db, rebuild_derived=False)
            await db.commit()
            total_users += count
            logger.info(f"Bulk ranking recalculated for table '{table_cfg.slug}': {count} users")
            if log_id:
                await append_line(log_id, f"Table {table_cfg.slug}: {count} users")

        for user_id in sorted(await select_ranking_user_ids(db), key=str):
            await rebuild_user_rating_derived_data(user_id, config, db)
            await db.commit()
            derived_rebuilds += 1

    result = {
        "status": "ok",
        "tables": len(targets),
        "total_users": total_users,
        "derived_rebuilds": derived_rebuilds,
    }
    if log_id:
        await append_line(log_id, f"Ranking recalculation complete: {result}")
        await set_status(log_id, "success")
        from sqlalchemy import select

        from app.models.admin_action_log import AdminActionLog

        async with AsyncSessionLocal() as db:
            parent_result = await db.execute(select(AdminActionLog.parent_log_id).where(AdminActionLog.id == log_id))
            parent_log_id = parent_result.scalar_one_or_none()
        if parent_log_id:
            await refresh_parent_status(parent_log_id)
    return result
