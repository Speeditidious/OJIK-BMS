"""Warm up rating-derived tables for recently active users after deploy.

Usage:
    docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T api \
        python -m scripts.deploy_rating_warmup --recent-days 30 --limit 500 --time-budget-seconds 480
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services.ranking_calculator import recalculate_user
from app.services.ranking_config import init_ranking_config

logger = logging.getLogger(__name__)


async def select_recent_active_user_ids(
    db: AsyncSession,
    recent_days: int,
    limit: int,
) -> list[uuid.UUID]:
    """Return recently active users sorted by latest sync timestamp DESC."""
    cutoff = datetime.now(UTC) - timedelta(days=recent_days)
    result = await db.execute(
        text("""
            WITH recent_activity AS (
                SELECT user_id, MAX(synced_at) AS last_synced_at
                FROM user_scores
                WHERE synced_at >= :cutoff
                GROUP BY user_id
                UNION ALL
                SELECT user_id, MAX(synced_at) AS last_synced_at
                FROM user_player_stats
                WHERE synced_at >= :cutoff
                GROUP BY user_id
            ),
            merged AS (
                SELECT user_id, MAX(last_synced_at) AS last_synced_at
                FROM recent_activity
                GROUP BY user_id
            )
            SELECT user_id
            FROM merged
            ORDER BY last_synced_at DESC, user_id ASC
            LIMIT :limit
        """),
        {"cutoff": cutoff, "limit": limit},
    )
    return [uuid.UUID(str(row["user_id"])) for row in result.mappings().all()]


async def run_deploy_rating_warmup(
    recent_days: int = 30,
    limit: int = 500,
    time_budget_seconds: int | None = None,
) -> dict[str, int | float | str | bool | None]:
    """Warm up ranking and derived rating tables for recently active users."""
    started_at = time.perf_counter()
    processed = 0
    succeeded = 0
    failed = 0
    time_budget_exhausted = False
    last_user_id: str | None = None

    async with AsyncSessionLocal() as db:
        config = await init_ranking_config(db)
        user_ids = await select_recent_active_user_ids(db, recent_days=recent_days, limit=limit)

        if not user_ids:
            logger.info(
                "Deploy rating warm-up skipped: no active users found in the last %s days",
                recent_days,
            )
        else:
            for user_id in user_ids:
                if (
                    time_budget_seconds is not None
                    and time.perf_counter() - started_at >= time_budget_seconds
                ):
                    time_budget_exhausted = True
                    logger.warning(
                        "Deploy rating warm-up stopped early after %.3fs: processed=%s remaining=%s time_budget_seconds=%s",
                        time.perf_counter() - started_at,
                        processed,
                        len(user_ids) - processed,
                        time_budget_seconds,
                    )
                    break
                processed += 1
                last_user_id = str(user_id)
                try:
                    await recalculate_user(user_id, config, db)
                    await db.commit()
                    succeeded += 1
                    logger.info(
                        "Deploy rating warm-up processed user %s (%s/%s)",
                        user_id,
                        processed,
                        len(user_ids),
                    )
                except Exception:
                    failed += 1
                    await db.rollback()
                    logger.exception("Deploy rating warm-up failed for user %s", user_id)

    enqueue_succeeded = False
    enqueue_task_id: str | None = None
    try:
        from app.tasks.ranking_calculator import recalculate_all_rankings

        task_result = recalculate_all_rankings.delay()
        enqueue_succeeded = True
        enqueue_task_id = str(task_result.id)
        logger.info(
            "Deploy rating warm-up enqueued full ranking recalc task_id=%s",
            enqueue_task_id,
        )
    except Exception:
        logger.exception("Deploy rating warm-up failed to enqueue full ranking recalc")

    duration_seconds = round(time.perf_counter() - started_at, 3)
    logger.info(
        "Deploy rating warm-up complete: processed=%s succeeded=%s failed=%s duration=%.3fs last_user_id=%s time_budget_exhausted=%s enqueue_succeeded=%s enqueue_task_id=%s",
        processed,
        succeeded,
        failed,
        duration_seconds,
        last_user_id,
        time_budget_exhausted,
        enqueue_succeeded,
        enqueue_task_id,
    )
    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "recent_days": recent_days,
        "limit": limit,
        "time_budget_seconds": time_budget_seconds,
        "time_budget_exhausted": time_budget_exhausted,
        "last_user_id": last_user_id,
        "duration_seconds": duration_seconds,
        "enqueue_succeeded": enqueue_succeeded,
        "enqueue_task_id": enqueue_task_id,
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI args for deploy warm-up."""
    parser = argparse.ArgumentParser(
        description="Warm up ranking-derived tables for recently active users after deploy.",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=30,
        help="Only warm up users with score/player sync activity in the last N days (default: 30).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum number of users to warm up (default: 500).",
    )
    parser.add_argument(
        "--time-budget-seconds",
        type=int,
        default=None,
        help=(
            "Stop the best-effort warm-up after this many seconds, then enqueue the full "
            "background recalculation as usual (default: no time budget)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args()
    asyncio.run(
        run_deploy_rating_warmup(
            recent_days=args.recent_days,
            limit=args.limit,
            time_budget_seconds=args.time_budget_seconds,
        )
    )


if __name__ == "__main__":
    main()
