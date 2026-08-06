"""Tests for the 30-day user activity leaderboard aggregation service.

Exercises `rebuild_activity_ranking` against the shared in-memory SQLite
`db_session` fixture (see `conftest.py`). All scenarios listed in the task
brief (plan section 9) are covered: attendance same-day dedup, plays LAG
delta parity with `analysis.py::_get_daily_plays`'s formula, per-client-type
summation, baseline-before-window seeding, notes_hit key mapping, first-ever
sync skip, lr2_stats_unreliable_sql exclusion, tie-break ordering, zero-value
exclusion, and DELETE-then-INSERT idempotency on repeated calls.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.score import UserActivityRanking, UserPlayerStats
from app.models.user import User
from app.services.activity_ranking import rebuild_activity_ranking

pytestmark = pytest.mark.asyncio


# The shared `db_session` fixture (conftest.py) builds the *entire* real schema
# via `Base.metadata.create_all` against in-memory SQLite, and several unrelated
# tables (e.g. `courses.constraint` with a `'[]'::jsonb` Postgres-only server
# default) fail to even CREATE TABLE under SQLite — a pre-existing gap in that
# shared fixture, not something introduced by this task. Following the same
# precedent as `tests/test_fumen_popularity.py` and `tests/test_analysis_heatmap.py`,
# this file uses its own minimal-schema SQLite engine covering only the tables
# this service touches (users, user_player_stats, user_activity_ranking).
@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for ddl in (
            """
            CREATE TABLE users (
                id CHAR(32) PRIMARY KEY,
                username TEXT NOT NULL,
                bio TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                is_admin BOOLEAN NOT NULL DEFAULT 0,
                avatar_url TEXT,
                first_synced_at JSON,
                preferences JSON,
                created_at DATETIME,
                updated_at DATETIME
            )
            """,
            """
            CREATE TABLE user_player_stats (
                id CHAR(32) PRIMARY KEY,
                user_id CHAR(32) NOT NULL,
                client_type VARCHAR(32) NOT NULL,
                synced_at DATETIME NOT NULL,
                playcount INTEGER,
                clearcount INTEGER,
                playtime INTEGER,
                judgments JSON
            )
            """,
            """
            CREATE TABLE user_activity_ranking (
                range VARCHAR(16) NOT NULL,
                metric VARCHAR(16) NOT NULL,
                user_id CHAR(32) NOT NULL,
                rank INTEGER NOT NULL,
                value INTEGER NOT NULL DEFAULT 0,
                window_start DATE NOT NULL,
                window_end DATE NOT NULL,
                computed_at DATETIME,
                PRIMARY KEY (range, metric, user_id)
            )
            """,
        ):
            await conn.execute(sa.text(ddl))

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


WINDOW_END = date(2026, 8, 5)
WINDOW_START = WINDOW_END - timedelta(days=29)


def _dt(d: date, hour: int = 12) -> datetime:
    """Naive UTC-ish datetime helper for `synced_at` values."""
    return datetime(d.year, d.month, d.day, hour)


def _stat(user: User, d: date, client_type: str = "beatoraja", hour: int = 12) -> UserPlayerStats:
    return UserPlayerStats(
        id=uuid.uuid4(),
        user_id=user.id,
        client_type=client_type,
        synced_at=_dt(d, hour),
        playcount=100,
        playtime=10000,
        judgments={},
    )


async def _make_user(db_session, username: str, *, is_active: bool = True) -> User:
    user = User(id=uuid.uuid4(), username=username, is_active=is_active)
    db_session.add(user)
    await db_session.flush()
    return user


async def _rows_for(db_session, metric: str, range_name: str = "monthly") -> list[UserActivityRanking]:
    result = await db_session.execute(
        sa.select(UserActivityRanking)
        .where(UserActivityRanking.range == range_name, UserActivityRanking.metric == metric)
        .order_by(UserActivityRanking.rank)
    )
    return list(result.scalars().all())


# ── attendance ────────────────────────────────────────────────────────────

async def test_attendance_dedups_same_day_multiple_syncs(db_session):
    user = await _make_user(db_session, "alice")
    day1 = WINDOW_START + timedelta(days=1)
    # Two client stats same UTC day -> still 1 attendance day.
    db_session.add_all(
        [
            _stat(user, day1, "lr2", 9),
            _stat(user, day1, "beatoraja", 15),
            _stat(user, day1 + timedelta(days=1), "lr2", 9),
        ]
    )
    await db_session.flush()

    written = await rebuild_activity_ranking(db_session, today=WINDOW_END)
    assert written["monthly"]["attendance"] == 1

    rows = await _rows_for(db_session, "attendance")
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].value == 2


async def test_attendance_events_outside_window_excluded(db_session):
    user = await _make_user(db_session, "bob")
    before = WINDOW_START - timedelta(days=1)
    after = WINDOW_END + timedelta(days=1)
    db_session.add_all(
        [
            _stat(user, before),
            _stat(user, after),
        ]
    )
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    rows = await _rows_for(db_session, "attendance")
    assert rows == []


async def test_weekly_and_monthly_windows_are_both_written(db_session):
    user = await _make_user(db_session, "range_user")
    weekly_day = WINDOW_END - timedelta(days=2)
    monthly_only_day = WINDOW_END - timedelta(days=20)
    db_session.add_all(
        [
            _stat(user, weekly_day),
            _stat(user, monthly_only_day),
        ]
    )
    await db_session.flush()

    written = await rebuild_activity_ranking(db_session, today=WINDOW_END)
    assert written["weekly"]["attendance"] == 1
    assert written["monthly"]["attendance"] == 1

    weekly_rows = await _rows_for(db_session, "attendance", "weekly")
    monthly_rows = await _rows_for(db_session, "attendance", "monthly")
    assert weekly_rows[0].value == 1
    assert monthly_rows[0].value == 2


# ── plays ─────────────────────────────────────────────────────────────────

async def test_plays_lag_delta_matches_analysis_formula(db_session):
    """GREATEST(0, playcount - COALESCE(lag, playcount)) summed over in-window rows."""
    user = await _make_user(db_session, "carol")
    d0 = WINDOW_START
    d1 = WINDOW_START + timedelta(days=1)
    d2 = WINDOW_START + timedelta(days=2)
    # playcount sequence: 100 (first sync, baseline inside window itself is fine
    # here since there's no earlier row) -> 110 -> 105 (regression, clamps to 0).
    db_session.add_all(
        [
            UserPlayerStats(id=uuid.uuid4(), user_id=user.id, client_type="lr2", synced_at=_dt(d0), playcount=100, playtime=100000, judgments={}),
            UserPlayerStats(id=uuid.uuid4(), user_id=user.id, client_type="lr2", synced_at=_dt(d1), playcount=110, playtime=110000, judgments={}),
            UserPlayerStats(id=uuid.uuid4(), user_id=user.id, client_type="lr2", synced_at=_dt(d2), playcount=105, playtime=110500, judgments={}),
        ]
    )
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    rows = await _rows_for(db_session, "plays")

    # By hand, matching _get_daily_plays's GREATEST(0, pc - COALESCE(lag_pc, pc)):
    #   row0: lag=NULL -> COALESCE(NULL, 100)=100 -> GREATEST(0, 100-100)=0
    #   row1: lag=100 -> GREATEST(0, 110-100)=10
    #   row2: lag=110 -> GREATEST(0, 105-110)=0 (clamped)
    expected = 0 + 10 + 0
    assert len(rows) == 1
    assert rows[0].value == expected


async def test_plays_baseline_before_window_seeds_first_in_window_delta(db_session):
    user = await _make_user(db_session, "dave")
    before = WINDOW_START - timedelta(days=3)
    first_in_window = WINDOW_START
    db_session.add_all(
        [
            UserPlayerStats(id=uuid.uuid4(), user_id=user.id, client_type="beatoraja", synced_at=_dt(before), playcount=50, playtime=50000, judgments={}),
            UserPlayerStats(id=uuid.uuid4(), user_id=user.id, client_type="beatoraja", synced_at=_dt(first_in_window), playcount=70, playtime=70000, judgments={}),
        ]
    )
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    rows = await _rows_for(db_session, "plays")

    # If baseline correctly seeds, delta = 70-50=20 (NOT 0, which would happen
    # if the first in-window row were treated as delta-from-NULL).
    assert len(rows) == 1
    assert rows[0].value == 20


async def test_plays_and_notes_hit_sum_across_client_types(db_session):
    user = await _make_user(db_session, "erin")
    d0 = WINDOW_START
    d1 = WINDOW_START + timedelta(days=1)
    db_session.add_all(
        [
            UserPlayerStats(
                id=uuid.uuid4(),
                user_id=user.id, client_type="lr2", synced_at=_dt(d0), playcount=10, playtime=10000,
                judgments={"perfect": 100, "great": 50, "good": 10, "bad": 1, "poor": 5},
            ),
            UserPlayerStats(
                id=uuid.uuid4(),
                user_id=user.id, client_type="lr2", synced_at=_dt(d1), playcount=15, playtime=15000,
                judgments={"perfect": 120, "great": 55, "good": 12, "bad": 2, "poor": 9},
            ),
            UserPlayerStats(
                id=uuid.uuid4(),
                user_id=user.id, client_type="beatoraja", synced_at=_dt(d0), playcount=20, playtime=20000,
                judgments={"epg": 200, "lpg": 10, "egr": 5, "lgr": 1, "egd": 1, "lgd": 0, "ebd": 0, "lbd": 0, "epr": 0, "lpr": 0, "ems": 0, "lms": 0},
            ),
            UserPlayerStats(
                id=uuid.uuid4(),
                user_id=user.id, client_type="beatoraja", synced_at=_dt(d1), playcount=25, playtime=25000,
                judgments={"epg": 210, "lpg": 12, "egr": 6, "lgr": 1, "egd": 2, "lgd": 0, "ebd": 0, "lbd": 0, "epr": 5, "lpr": 0, "ems": 0, "lms": 0},
            ),
        ]
    )
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    plays_rows = await _rows_for(db_session, "plays")
    notes_rows = await _rows_for(db_session, "notes_hit")

    # plays: lr2 first-row delta 0 + second-row delta 5 = 5; beatoraja 0 + 5 = 5 -> total 10
    assert len(plays_rows) == 1
    assert plays_rows[0].value == 10

    # notes_hit: only second rows count (first row has no previous).
    # lr2: (120-100)+(55-50)+(12-10)+(2-1) = 20+5+2+1 = 28 (poor excluded)
    # beatoraja: (210-200)+(12-10)+(6-5)+(1-1)+(2-1)+(0-0)+(0-0)+(0-0) = 10+2+1+0+1 = 14 (epr/lpr/ems/lms excluded)
    expected_notes = 28 + 14
    assert len(notes_rows) == 1
    assert notes_rows[0].value == expected_notes


async def test_notes_hit_first_ever_sync_row_contributes_zero(db_session):
    user = await _make_user(db_session, "frank")
    db_session.add(
        UserPlayerStats(
                id=uuid.uuid4(),
            user_id=user.id, client_type="lr2", synced_at=_dt(WINDOW_START), playcount=10, playtime=10000,
            judgments={"perfect": 100, "great": 50, "good": 10, "bad": 1, "poor": 5},
        )
    )
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    # value 0 for both plays and notes_hit -> user excluded entirely from both metrics.
    assert await _rows_for(db_session, "plays") == []
    assert await _rows_for(db_session, "notes_hit") == []


async def test_lr2_unreliable_rows_excluded(db_session):
    user = await _make_user(db_session, "grace")
    d0 = WINDOW_START
    d1 = WINDOW_START + timedelta(days=1)
    db_session.add_all(
        [
            # Reliable baseline.
            UserPlayerStats(
                id=uuid.uuid4(),
                user_id=user.id, client_type="lr2", synced_at=_dt(d0), playcount=10, playtime=10000,
                judgments={"perfect": 10, "great": 0, "good": 0, "bad": 0, "poor": 0},
            ),
            # Unreliable: playcount high, playtime implausibly low (< 10s/play).
            UserPlayerStats(
                id=uuid.uuid4(),
                user_id=user.id, client_type="lr2", synced_at=_dt(d1), playcount=1000, playtime=5,
                judgments={"perfect": 900, "great": 0, "good": 0, "bad": 0, "poor": 0},
            ),
        ]
    )
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    # The unreliable row is dropped entirely, leaving only the reliable baseline
    # row (delta 0, since it has no earlier reliable row) -> no ranking rows.
    assert await _rows_for(db_session, "plays") == []
    assert await _rows_for(db_session, "notes_hit") == []


# ── ranking / tie-break / zero exclusion ────────────────────────────────────

async def test_tie_break_by_username_ascending(db_session):
    user_b = await _make_user(db_session, "bob")
    user_a = await _make_user(db_session, "alice")
    day1 = WINDOW_START
    for user in (user_a, user_b):
        db_session.add(_stat(user, day1))
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    rows = await _rows_for(db_session, "attendance")

    assert len(rows) == 2
    assert [r.user_id for r in rows] == [user_a.id, user_b.id]
    assert [r.rank for r in rows] == [1, 2]
    assert rows[0].value == rows[1].value == 1


async def test_zero_value_users_excluded(db_session):
    user = await _make_user(db_session, "hank")
    # Single player-stat row outside the window entirely -> attendance 0 -> excluded.
    db_session.add(_stat(user, WINDOW_START - timedelta(days=5)))
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    assert await _rows_for(db_session, "attendance") == []


# ── idempotency ──────────────────────────────────────────────────────────

async def test_rebuild_replaces_previous_snapshot(db_session):
    user1 = await _make_user(db_session, "ivan")
    db_session.add(_stat(user1, WINDOW_START))
    await db_session.flush()
    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    assert len(await _rows_for(db_session, "attendance")) == 1

    # Second user added, rebuild again -> old snapshot fully replaced, not appended.
    user2 = await _make_user(db_session, "judy")
    db_session.add(_stat(user2, WINDOW_START))
    await db_session.flush()
    await rebuild_activity_ranking(db_session, today=WINDOW_END)

    rows = await _rows_for(db_session, "attendance")
    assert len(rows) == 2
    assert {r.user_id for r in rows} == {user1.id, user2.id}
    assert [r.rank for r in rows] == [1, 2]


async def test_window_start_and_end_recorded_on_rows(db_session):
    user = await _make_user(db_session, "karen")
    db_session.add(_stat(user, WINDOW_START))
    await db_session.flush()

    await rebuild_activity_ranking(db_session, today=WINDOW_END)
    rows = await _rows_for(db_session, "attendance")
    assert rows[0].window_start == WINDOW_START
    assert rows[0].window_end == WINDOW_END


# ── deactivated users ─────────────────────────────────────────────────────

async def test_deactivated_user_not_ranked_for_attendance(db_session):
    """A deactivated user is excluded from the candidate set, not just hidden."""
    active = await _make_user(db_session, "active_one")
    banned = await _make_user(db_session, "banned_one", is_active=False)
    day1 = WINDOW_START + timedelta(days=1)
    db_session.add_all(
        [
            _stat(active, day1, "lr2", 9),
            _stat(banned, day1, "lr2", 9),
            _stat(banned, day1 + timedelta(days=1), "lr2", 9),
        ]
    )
    await db_session.flush()

    written = await rebuild_activity_ranking(db_session, today=WINDOW_END)
    assert written["monthly"]["attendance"] == 1

    rows = await _rows_for(db_session, "attendance")
    assert [r.user_id for r in rows] == [active.id]
    # Ranks are reassigned over the active-only set, so the survivor is rank 1.
    assert rows[0].rank == 1


async def test_deactivated_user_not_ranked_for_plays_and_notes_hit(db_session):
    active = await _make_user(db_session, "active_two")
    banned = await _make_user(db_session, "banned_two", is_active=False)
    d0 = WINDOW_START
    d1 = WINDOW_START + timedelta(days=1)
    for user, base in ((active, 10), (banned, 1000)):
        db_session.add_all(
            [
                UserPlayerStats(
                    id=uuid.uuid4(),
                    user_id=user.id, client_type="lr2", synced_at=_dt(d0), playcount=base, playtime=base * 100,
                    judgments={"perfect": 100, "great": 50, "good": 10, "bad": 1, "poor": 5},
                ),
                UserPlayerStats(
                    id=uuid.uuid4(),
                    user_id=user.id, client_type="lr2", synced_at=_dt(d1), playcount=base + 5, playtime=(base + 5) * 100,
                    judgments={"perfect": 120, "great": 55, "good": 12, "bad": 2, "poor": 9},
                ),
            ]
        )
    await db_session.flush()

    written = await rebuild_activity_ranking(db_session, today=WINDOW_END)
    assert written["monthly"]["plays"] == 1
    assert written["monthly"]["notes_hit"] == 1

    for metric in ("plays", "notes_hit"):
        rows = await _rows_for(db_session, metric)
        assert [r.user_id for r in rows] == [active.id], metric
