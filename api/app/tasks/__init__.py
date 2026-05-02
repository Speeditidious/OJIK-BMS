from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.parsers.table_fetcher import get_default_table_configs, get_update_config

UPDATE_ALL_TABLES_TASK = "app.tasks.table_updater.update_all_difficulty_tables"
RECALCULATE_ALL_RANKINGS_TASK = "app.tasks.ranking_calculator.recalculate_all_rankings"

celery_app = Celery(
    "ojik_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.table_updater", "app.tasks.ranking_calculator"],
)


def _scheduled_update_slugs(table_configs: list[dict]) -> list[str]:
    """Return auto-updated table slugs with dedicated schedules."""
    return [
        cfg["slug"]
        for cfg in table_configs
        if cfg.get("auto_update", True)
        and cfg.get("slug")
        and cfg.get("update_schedule")
    ]


def _build_update_schedule(schedule_config: dict):
    """Build a Celery schedule from a table update schedule config."""
    schedule_type = schedule_config.get("type")
    if schedule_type != "weekly":
        raise ValueError(f"Unsupported table update schedule type: {schedule_type}")

    return crontab(
        minute=schedule_config.get("minute", 0),
        hour=schedule_config.get("hour", 0),
        day_of_week=schedule_config["day_of_week"],
    )


def build_beat_schedule(update_config: dict, table_configs: list[dict]) -> dict:
    """Build Celery beat schedule entries for table updates and ranking jobs."""
    update_interval_seconds = update_config.get("update_interval_hours", 168) * 3600
    scheduled_slugs = _scheduled_update_slugs(table_configs)
    beat_schedule = {
        "update-difficulty-tables": {
            "task": UPDATE_ALL_TABLES_TASK,
            "schedule": update_interval_seconds,
            "kwargs": {"exclude_slugs": scheduled_slugs},
        },
        "recalculate-all-rankings": {
            "task": RECALCULATE_ALL_RANKINGS_TASK,
            "schedule": 86400,  # 24 hours
        },
    }

    for cfg in table_configs:
        if not cfg.get("auto_update", True):
            continue
        schedule_config = cfg.get("update_schedule")
        slug = cfg.get("slug")
        if not schedule_config or not slug:
            continue
        beat_schedule[f"update-difficulty-table-{slug}"] = {
            "task": UPDATE_ALL_TABLES_TASK,
            "schedule": _build_update_schedule(schedule_config),
            "kwargs": {"slugs": [slug]},
        }

    return beat_schedule


_update_config = get_update_config()
_default_table_configs = get_default_table_configs()

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=_update_config.get("update_timezone", "Asia/Seoul"),
    enable_utc=True,
    beat_schedule=build_beat_schedule(_update_config, _default_table_configs),
)
