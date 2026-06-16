from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.services.weekly_period import current_period, period_for_offset


KST = ZoneInfo("Asia/Seoul")


def test_current_period_starts_on_monday_4am_kst():
    # 2026-06-13 is a Saturday (UTC). KST is UTC+9.
    now = datetime(2026, 6, 13, 5, 0, tzinfo=timezone.utc)
    start, end = current_period(now, "mon", 4, 0, "Asia/Seoul")
    # Most recent Monday 04:00 KST before now -> 2026-06-08 04:00 KST
    assert start.astimezone(KST) == datetime(2026, 6, 8, 4, 0, tzinfo=KST)
    assert end == start + timedelta(days=7)


def test_period_for_offset_minus_one_is_previous_week():
    now = datetime(2026, 6, 13, 5, 0, tzinfo=timezone.utc)
    cur_start, _ = current_period(now, "mon", 4, 0, "Asia/Seoul")
    prev_start, prev_end = period_for_offset(now, -1, "mon", 4, 0, "Asia/Seoul")
    assert prev_end == cur_start
    assert prev_start == cur_start - timedelta(days=7)


def test_exactly_on_rollover_boundary_starts_new_period():
    # Monday 04:00 KST exactly
    now = datetime(2026, 6, 8, 4, 0, tzinfo=KST).astimezone(timezone.utc)
    start, _ = current_period(now, "mon", 4, 0, "Asia/Seoul")
    assert start.astimezone(KST) == datetime(2026, 6, 8, 4, 0, tzinfo=KST)
