"""Tests for difficulty table auto-update schedule configuration."""

from celery.schedules import crontab

from app.parsers.table_fetcher import get_default_table_configs, get_update_config
from app.tasks import UPDATE_ALL_TABLES_TASK, build_beat_schedule


STELLAVERSE_SLUGS = {"satellite", "stella", "solar", "supernova"}


def test_difficulty_table_update_config_includes_timezone_and_schedule_overrides():
    """The real config keeps a default interval and adds Stellaverse schedules."""
    update_config = get_update_config()
    table_configs = get_default_table_configs()

    assert update_config["update_interval_hours"] == 168
    assert update_config["update_timezone"] == "Asia/Seoul"

    schedules_by_slug = {
        cfg["slug"]: cfg["update_schedule"]
        for cfg in table_configs
        if cfg.get("update_schedule")
    }

    assert set(schedules_by_slug) == STELLAVERSE_SLUGS
    for schedule_config in schedules_by_slug.values():
        assert schedule_config == {
            "type": "weekly",
            "day_of_week": "mon",
            "hour": 0,
            "minute": 0,
        }


def test_build_beat_schedule_keeps_default_interval_for_non_overridden_tables():
    """Default beat stays interval-based and skips tables with dedicated schedules."""
    beat_schedule = build_beat_schedule(
        get_update_config(),
        get_default_table_configs(),
    )

    default_entry = beat_schedule["update-difficulty-tables"]

    assert default_entry["task"] == UPDATE_ALL_TABLES_TASK
    assert default_entry["schedule"] == 168 * 3600
    assert set(default_entry["kwargs"]["exclude_slugs"]) == STELLAVERSE_SLUGS


def test_build_beat_schedule_adds_stellaverse_weekly_midnight_entries():
    """Stellaverse tables update at Monday 00:00 in the configured beat timezone."""
    beat_schedule = build_beat_schedule(
        get_update_config(),
        get_default_table_configs(),
    )

    for slug in STELLAVERSE_SLUGS:
        entry = beat_schedule[f"update-difficulty-table-{slug}"]
        schedule = entry["schedule"]

        assert entry["task"] == UPDATE_ALL_TABLES_TASK
        assert entry["kwargs"] == {"slugs": [slug]}
        assert isinstance(schedule, crontab)
        assert schedule._orig_day_of_week == "mon"
        assert schedule._orig_hour == 0
        assert schedule._orig_minute == 0


def test_build_beat_schedule_does_not_schedule_disabled_tables():
    """auto_update=false entries are not scheduled even when they define overrides."""
    beat_schedule = build_beat_schedule(
        {"update_interval_hours": 12},
        [
            {"slug": "default-table"},
            {
                "slug": "weekly-table",
                "update_schedule": {
                    "type": "weekly",
                    "day_of_week": "mon",
                    "hour": 0,
                    "minute": 0,
                },
            },
            {
                "slug": "disabled-table",
                "auto_update": False,
                "update_schedule": {
                    "type": "weekly",
                    "day_of_week": "mon",
                    "hour": 0,
                    "minute": 0,
                },
            },
        ],
    )

    assert beat_schedule["update-difficulty-tables"]["schedule"] == 12 * 3600
    assert beat_schedule["update-difficulty-tables"]["kwargs"] == {
        "exclude_slugs": ["weekly-table"],
    }
    assert "update-difficulty-table-weekly-table" in beat_schedule
    assert "update-difficulty-table-disabled-table" not in beat_schedule
