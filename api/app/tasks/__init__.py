from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ojik_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.table_updater"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "update-difficulty-tables-daily": {
            "task": "app.tasks.table_updater.update_all_difficulty_tables",
            "schedule": 86400.0,  # every 24 hours
        },
    },
)
