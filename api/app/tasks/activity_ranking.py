"""Celery task for rebuilding the user activity leaderboard."""

from __future__ import annotations

from app.core.database import AsyncSessionLocal
from app.services.activity_ranking import rebuild_activity_ranking
from app.tasks import celery_app
from app.tasks.ranking_calculator import _run_async


async def _rebuild() -> dict:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            return await rebuild_activity_ranking(db)


@celery_app.task(name="app.tasks.activity_ranking.rebuild_activity_ranking")
def rebuild_activity_ranking_task() -> dict:
    """Recompute the 30-day attendance/plays/notes_hit leaderboard snapshot."""
    return _run_async(_rebuild())
