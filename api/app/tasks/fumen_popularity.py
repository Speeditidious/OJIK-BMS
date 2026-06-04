"""Celery tasks for fumen popularity maintenance."""

from __future__ import annotations

import uuid

from app.core.database import AsyncSessionLocal
from app.services.fumen_popularity import (
    rebuild_popularity_window,
    refresh_dirty_fumen_popularity,
    refresh_popularity_window_for_fumens,
)
from app.tasks import celery_app
from app.tasks.ranking_calculator import _run_async

_BATCH_SIZE = 5000
_MAX_BATCHES_PER_RUN = 20


async def _drain_dirty() -> int:
    total = 0
    for _ in range(_MAX_BATCHES_PER_RUN):
        async with AsyncSessionLocal() as db:
            async with db.begin():
                processed = await refresh_dirty_fumen_popularity(db, _BATCH_SIZE)
        total += processed
        if processed < _BATCH_SIZE:
            break
    return total


@celery_app.task(name="app.tasks.fumen_popularity.refresh_dirty_fumen_popularity")
def refresh_dirty_fumen_popularity_task() -> dict:
    """Drain queued fumens and refresh all-time popularity counts."""
    return {"processed": _run_async(_drain_dirty())}


async def _refresh_windows_for_fumens(fumen_ids: list[str]) -> dict:
    parsed_ids = [uuid.UUID(fid) for fid in fumen_ids]
    out = {}
    for window in ("weekly", "monthly"):
        async with AsyncSessionLocal() as db:
            async with db.begin():
                out[window] = await refresh_popularity_window_for_fumens(db, window, parsed_ids)
    return out


@celery_app.task(name="app.tasks.fumen_popularity.refresh_fumen_popularity_windows_for_fumens")
def refresh_fumen_popularity_windows_for_fumens_task(fumen_ids: list[str]) -> dict:
    """Refresh weekly/monthly cache only for fumens touched by one sync."""
    return _run_async(_refresh_windows_for_fumens(fumen_ids))


async def _rebuild_windows() -> dict:
    out = {}
    for window in ("weekly", "monthly"):
        async with AsyncSessionLocal() as db:
            async with db.begin():
                out[window] = await rebuild_popularity_window(db, window)
    return out


@celery_app.task(name="app.tasks.fumen_popularity.rebuild_fumen_popularity_windows")
def rebuild_fumen_popularity_windows_task() -> dict:
    """Daily full rebuild for moving weekly/monthly windows."""
    return _run_async(_rebuild_windows())
