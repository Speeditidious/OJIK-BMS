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
def recalculate_all_rankings(self, table_slug: str | None = None) -> dict:
    """Recalculate rankings for all users. Optionally limit to a single table by slug."""
    try:
        return _run_async(_async_recalculate_all(table_slug))
    except Exception as exc:
        logger.error(f"Bulk ranking recalc failed: {exc}")
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


async def _async_recalculate_all(table_slug: str | None = None) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.ranking_calculator import recalculate_table_bulk
    from app.services.ranking_config import init_ranking_config

    total_users = 0
    async with AsyncSessionLocal() as db:
        config = await init_ranking_config(db)
        targets = config.tables
        if table_slug is not None:
            targets = [t for t in targets if t.slug == table_slug]
        for table_cfg in targets:
            count = await recalculate_table_bulk(table_cfg, config, db)
            await db.commit()
            total_users += count
            logger.info(f"Bulk ranking recalculated for table '{table_cfg.slug}': {count} users")

    return {"status": "ok", "tables": len(targets), "total_users": total_users}
