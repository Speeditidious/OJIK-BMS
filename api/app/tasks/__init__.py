from celery import Celery

from app.core.config import settings
from app.parsers.table_fetcher import get_update_config

celery_app = Celery(
    "ojik_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.table_updater", "app.tasks.ranking_calculator"],
)

_update_interval_seconds = get_update_config().get("update_interval_hours", 168) * 3600

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "update-difficulty-tables": {
            "task": "app.tasks.table_updater.update_all_difficulty_tables",
            "schedule": _update_interval_seconds,
        },
        "recalculate-all-rankings": {
            "task": "app.tasks.ranking_calculator.recalculate_all_rankings",
            "schedule": 86400,  # 24 hours
        },
    },
)
