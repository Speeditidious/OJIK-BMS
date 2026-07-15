"""Tests for GET /analysis/heatmap's goal-achievement merge (Task 11).

No prior test file covered `/analysis/heatmap` at all (confirmed by searching
`api/tests/` for "heatmap" before writing this file) — the endpoint's other
four metrics (`updates`, `new_plays`, `plays`, `rating_updates`) previously
had zero direct-endpoint test coverage; only their standalone helper
functions (`_get_daily_plays`, `_rating_count_map`, etc.) were unit-tested
elsewhere (`test_dashboard_backend_impl.py`), several of those via a
DB-mocking `_CaptureSession` rather than a real database, specifically
because `_build_activity_subquery`/`_get_daily_plays` use `func.timezone(...)`
and `cast(..., Date)`, which are Postgres-only and error under SQLite the
moment a real row is evaluated (SQLite has no `timezone()` function).

This file follows `test_goals_api.py`'s convention: call the router function
directly (bypassing FastAPI's DI layer) against a real in-memory SQLite
session built from raw DDL, with a `SimpleNamespace`/`User` stand-in for
`current_user`. To keep the existing four metrics' subqueries safe under
SQLite (empty `user_scores`/`user_player_stats` tables => the unsupported
`timezone()` expression is never evaluated because there are no rows to
project it over), those tables are left empty; this still lets us assert
that those four metrics behave exactly as before (all-zero, unaffected by
this change) and give this endpoint a *first* baseline test as a byproduct.
`get_ranking_config` is monkeypatched to raise `RuntimeError`, mirroring the
endpoint's own `except RuntimeError` fallback branch, so the rating-update
path (which needs a real ranking config + derived-data tables) is skipped
without touching that unrelated machinery.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.goal import UserGoal
from app.models.user import User
from app.routers.analysis import get_activity_heatmap


# ── DB fixture ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # `_build_activity_subquery`/`_get_daily_plays` (unrelated, pre-existing
    # code — not touched by this task) call the Postgres-only `timezone()`
    # SQL function. SQLite has no such builtin, and unlike a missing table
    # row, an unregistered function name fails at *statement-prepare* time
    # even when the table is empty — so every call to `get_activity_heatmap`
    # would fail to even compile without this. Register a pass-through stub
    # purely so the (already SQLite-incompatible) existing subqueries can
    # execute against zero rows; this does not attempt to fix or validate
    # their date-grouping behavior under SQLite, which remains untested and
    # out of this task's scope.
    @event.listens_for(engine.sync_engine, "connect")
    def _register_timezone_stub(dbapi_connection, connection_record):
        dbapi_connection.create_function("timezone", 2, lambda tz, ts: ts)
        dbapi_connection.create_function(
            "greatest", 2, lambda a, b: max(a, b) if a is not None and b is not None else None
        )

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
            CREATE TABLE user_scores (
                id CHAR(32) PRIMARY KEY,
                user_id CHAR(32) NOT NULL,
                client_type VARCHAR(32) NOT NULL,
                scorehash TEXT,
                fumen_sha256 VARCHAR(64),
                fumen_md5 VARCHAR(32),
                fumen_hash_others TEXT,
                fumen_id CHAR(32),
                clear_type INTEGER,
                exscore INTEGER,
                rate FLOAT,
                rank VARCHAR(4),
                max_combo INTEGER,
                min_bp INTEGER,
                play_count INTEGER,
                clear_count INTEGER,
                judgments JSON,
                options JSON,
                recorded_at DATETIME,
                synced_at DATETIME
            )
            """,
            """
            CREATE TABLE user_player_stats (
                id CHAR(32) PRIMARY KEY,
                user_id CHAR(32) NOT NULL,
                client_type VARCHAR(32) NOT NULL,
                synced_at DATETIME,
                playcount INTEGER,
                clearcount INTEGER,
                playtime INTEGER,
                judgments JSON
            )
            """,
            """
            CREATE TABLE user_goals (
                goal_id CHAR(32) PRIMARY KEY,
                user_id CHAR(32) NOT NULL,
                goal_type VARCHAR(8) NOT NULL,
                client_type VARCHAR(32) NOT NULL,
                table_slug VARCHAR,
                fumen_sha256 TEXT,
                fumen_md5 TEXT,
                course_id CHAR(32),
                course_md5_list JSON,
                target_clear_type INTEGER,
                target_min_bp INTEGER,
                target_rank VARCHAR(4),
                target_rate FLOAT,
                projected_rating FLOAT,
                comment TEXT,
                status VARCHAR(10) NOT NULL,
                baseline_snapshot JSON NOT NULL,
                created_at DATETIME,
                achieved_at DATETIME,
                achieved_recorded_at DATETIME,
                deleted_at DATETIME
            )
            """,
        ):
            await conn.execute(sa.text(ddl))

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


def _uid() -> uuid.UUID:
    return uuid.uuid4()


async def _add_user(db: AsyncSession, *, user_id: uuid.UUID | None = None, is_active: bool = True) -> User:
    user = User(id=user_id or _uid(), username=f"user-{uuid.uuid4().hex[:8]}", is_active=is_active)
    db.add(user)
    await db.flush()
    return user


async def _add_achieved_goal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    achieved_recorded_at: datetime,
    status: str = "achieved",
    deleted_at: datetime | None = None,
) -> None:
    db.add(
        UserGoal(
            goal_id=uuid.uuid4(),
            user_id=user_id,
            goal_type="chart",
            client_type="beatoraja",
            fumen_sha256="a" * 64,
            fumen_md5="b" * 32,
            status=status,
            baseline_snapshot={},
            achieved_at=achieved_recorded_at,
            achieved_recorded_at=achieved_recorded_at,
            deleted_at=deleted_at,
        )
    )
    await db.flush()


def _raise_runtime_error():
    raise RuntimeError("ranking config not configured")


@pytest.fixture(autouse=True)
def _skip_ranking_config(monkeypatch):
    """Bypass the rating-update path entirely (out of scope for this task) —
    mirrors the endpoint's own `except RuntimeError` fallback branch.
    """
    monkeypatch.setattr("app.routers.analysis.get_ranking_config", _raise_runtime_error)


# ── goals_achieved: correctness ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_heatmap_returns_correct_goals_achieved_counts_for_self(db_session: AsyncSession):
    user = await _add_user(db_session)
    await _add_achieved_goal(db_session, user_id=user.id, achieved_recorded_at=datetime(2026, 1, 5, 10, 0, tzinfo=UTC))
    await _add_achieved_goal(db_session, user_id=user.id, achieved_recorded_at=datetime(2026, 1, 5, 15, 0, tzinfo=UTC))
    await _add_achieved_goal(db_session, user_id=user.id, achieved_recorded_at=datetime(2026, 1, 10, 9, 0, tzinfo=UTC))

    result = await get_activity_heatmap(
        year=2026, client_type=None, user_id=None, current_user=user, db=db_session
    )

    by_date = {row["date"]: row["goals_achieved"] for row in result["data"]}
    assert by_date.get("2026-01-05") == 2
    assert by_date.get("2026-01-10") == 1
    # Every other date present must default to 0.
    assert all(v == 0 for d, v in by_date.items() if d not in ("2026-01-05", "2026-01-10"))


@pytest.mark.asyncio
async def test_heatmap_excludes_soft_deleted_achieved_goals(db_session: AsyncSession):
    user = await _add_user(db_session)
    await _add_achieved_goal(
        db_session,
        user_id=user.id,
        achieved_recorded_at=datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        deleted_at=datetime(2026, 1, 6, tzinfo=UTC),
    )

    result = await get_activity_heatmap(
        year=2026, client_type=None, user_id=None, current_user=user, db=db_session
    )

    assert all(row["goals_achieved"] == 0 for row in result["data"])


@pytest.mark.asyncio
async def test_heatmap_excludes_active_not_yet_achieved_goals(db_session: AsyncSession):
    user = await _add_user(db_session)
    # An "active" goal has no achieved_recorded_at yet in real usage, but even
    # if one were set, status != 'achieved' must exclude it from the count.
    await _add_achieved_goal(
        db_session,
        user_id=user.id,
        achieved_recorded_at=datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        status="active",
    )

    result = await get_activity_heatmap(
        year=2026, client_type=None, user_id=None, current_user=user, db=db_session
    )

    assert all(row["goals_achieved"] == 0 for row in result["data"])


# ── privacy ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_heatmap_privacy_other_user_view_returns_zero_and_skips_query(db_session: AsyncSession, monkeypatch):
    target = await _add_user(db_session)
    viewer = await _add_user(db_session)
    await _add_achieved_goal(db_session, user_id=target.id, achieved_recorded_at=datetime(2026, 1, 5, tzinfo=UTC))

    calls: list = []
    from app.routers import analysis as analysis_module

    original = analysis_module._get_daily_goals_achieved

    async def _spy(*args, **kwargs):
        calls.append(1)
        return await original(*args, **kwargs)

    monkeypatch.setattr(analysis_module, "_get_daily_goals_achieved", _spy)

    result = await get_activity_heatmap(
        year=2026, client_type=None, user_id=target.id, current_user=viewer, db=db_session
    )

    assert all(row["goals_achieved"] == 0 for row in result["data"])
    assert calls == [], "goal-count query must be skipped entirely for a non-self view"


@pytest.mark.asyncio
async def test_heatmap_anonymous_view_returns_zero_and_skips_query(db_session: AsyncSession, monkeypatch):
    target = await _add_user(db_session)
    await _add_achieved_goal(db_session, user_id=target.id, achieved_recorded_at=datetime(2026, 1, 5, tzinfo=UTC))

    calls: list = []
    from app.routers import analysis as analysis_module

    original = analysis_module._get_daily_goals_achieved

    async def _spy(*args, **kwargs):
        calls.append(1)
        return await original(*args, **kwargs)

    monkeypatch.setattr(analysis_module, "_get_daily_goals_achieved", _spy)

    result = await get_activity_heatmap(
        year=2026, client_type=None, user_id=target.id, current_user=None, db=db_session
    )

    assert all(row["goals_achieved"] == 0 for row in result["data"])
    assert calls == [], "goal-count query must be skipped entirely for an anonymous view"


# ── existing heatmap behavior unaffected ────────────────────────────────────

@pytest.mark.asyncio
async def test_heatmap_existing_metrics_unaffected_with_no_scores(db_session: AsyncSession):
    """With no user_scores/user_player_stats rows, updates/new_plays/plays/
    rating_updates must remain all-zero exactly as before this change — this
    is the pre-existing (empty-data) baseline behavior of the endpoint.
    """
    user = await _add_user(db_session)

    result = await get_activity_heatmap(
        year=2026, client_type=None, user_id=None, current_user=user, db=db_session
    )

    assert result["year"] == 2026
    assert result["rating_updates_pending"] is False
    assert result["data"] == []


@pytest.mark.asyncio
async def test_heatmap_data_shape_includes_all_five_keys_when_goal_present(db_session: AsyncSession):
    user = await _add_user(db_session)
    await _add_achieved_goal(db_session, user_id=user.id, achieved_recorded_at=datetime(2026, 3, 1, tzinfo=UTC))

    result = await get_activity_heatmap(
        year=2026, client_type=None, user_id=None, current_user=user, db=db_session
    )

    assert len(result["data"]) == 1
    row = result["data"][0]
    assert row["date"] == "2026-03-01"
    assert set(row.keys()) == {"date", "updates", "new_plays", "plays", "rating_updates", "goals_achieved"}
    assert row["updates"] == 0
    assert row["new_plays"] == 0
    assert row["plays"] == 0
    assert row["rating_updates"] == 0
    assert row["goals_achieved"] == 1
