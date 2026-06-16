"""Celery task: generate weekly instances at rollover."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.weekly_generator.generate_weeklies", bind=True, max_retries=2)
def generate_weeklies(self: Any) -> dict:
    """Generate the current-period weekly for every category/bracket (idempotent)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_generate_weeklies())
    except Exception as exc:
        logger.error(f"generate_weeklies failed: {exc}")
        raise self.retry(exc=exc, countdown=600)


async def _async_generate_weeklies() -> dict:
    import random

    from app.core.database import AsyncSessionLocal
    from app.services.weekly_config import load_weekly_config
    from app.services.weekly_generator import generate_weekly
    from app.services.weekly_period import current_period

    cfg = load_weekly_config()
    now = datetime.now(UTC)
    s = cfg.settings
    period_start, period_end = current_period(
        now, s.rollover_day_of_week, s.rollover_hour, s.rollover_minute, s.timezone
    )

    created = 0
    skipped = 0
    rng = random.Random()
    async with AsyncSessionLocal() as db:
        for category in cfg.categories:
            for bracket in category.brackets:
                weekly = await generate_weekly(
                    db,
                    category.key,
                    category.name,
                    bracket,
                    period_start,
                    period_end,
                    forced=False,
                    rng=rng,
                )
                if weekly.created_at and (now - weekly.created_at).total_seconds() < 120:
                    created += 1
                else:
                    skipped += 1
        await db.commit()

    logger.info(f"generate_weeklies: created≈{created} skipped≈{skipped} period={period_start.isoformat()}")
    return {"created": created, "skipped": skipped, "period_start": period_start.isoformat()}
