"""Tests for the goals router (Task 9) — HTTP CRUD layer over Task 7's
`UserGoal` model and Task 8's `goal_evaluator.py` service.

Router endpoint functions are called directly (bypassing FastAPI's DI layer)
with a real in-memory SQLite session and a `SimpleNamespace` stand-in for
`current_user` — the same convention used in `test_issues_api.py`. The DB
fixture uses raw DDL (mirroring `test_goal_evaluator.py`) rather than
`Base.metadata.create_all`, which chokes on SQLite for Postgres-only
`server_default` expressions (`gen_random_uuid()`, `now()`) and the `JSONB`
type used across the full model set.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.course import Course
from app.models.difficulty_table import DifficultyTable
from app.models.fumen import Fumen, FumenTableEntry
from app.models.goal import UserGoal
from app.models.score import UserPlayerStats, UserScore
from app.routers.goals import (
    GoalCreate,
    create_goal,
    delete_goal,
    list_goal_achievements,
    list_goals,
)
from app.services.ranking_config import (
    BonusConfig,
    RankingConfig,
    ReferenceCondition,
    TableRankingConfig,
)


# ── DB fixture ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for ddl in (
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
            CREATE TABLE courses (
                id CHAR(32) PRIMARY KEY,
                name TEXT NOT NULL,
                source_table_id CHAR(32),
                md5_list JSON NOT NULL,
                sha256_list JSON,
                "constraint" JSON,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                dan_title TEXT NOT NULL DEFAULT '',
                synced_at DATETIME
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
            """
            CREATE TABLE fumens (
                fumen_id CHAR(32) PRIMARY KEY,
                sha256 VARCHAR(64),
                md5 VARCHAR(32),
                title TEXT,
                artist TEXT,
                bpm_min FLOAT,
                bpm_max FLOAT,
                bpm_main FLOAT,
                notes_total INTEGER,
                notes_n INTEGER,
                notes_ln INTEGER,
                notes_s INTEGER,
                notes_ls INTEGER,
                total INTEGER,
                length INTEGER,
                keymode INTEGER,
                youtube_url TEXT,
                file_url TEXT,
                file_url_diff TEXT,
                added_by_user_id CHAR(32),
                created_at DATETIME,
                updated_at DATETIME
            )
            """,
            """
            CREATE TABLE fumen_table_entries (
                fumen_id CHAR(32) NOT NULL,
                table_id CHAR(32) NOT NULL,
                level TEXT NOT NULL,
                created_at DATETIME,
                updated_at DATETIME,
                PRIMARY KEY (fumen_id, table_id)
            )
            """,
            """
            CREATE TABLE difficulty_tables (
                id CHAR(32) PRIMARY KEY,
                name TEXT NOT NULL,
                symbol VARCHAR(32),
                slug VARCHAR(64),
                source_url TEXT,
                site TEXT,
                is_default BOOLEAN NOT NULL DEFAULT 0,
                default_order INTEGER,
                level_order JSON,
                display_level_order JSON,
                non_regular_level_order JSON,
                created_at DATETIME,
                updated_at DATETIME
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
        ):
            await conn.execute(sa.text(ddl))

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _user(user_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or _uid())


async def _add_score(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    client_type: str = "beatoraja",
    fumen_sha256: str | None = None,
    fumen_md5: str | None = None,
    clear_type: int | None = None,
    rate: float | None = None,
) -> None:
    db.add(
        UserScore(
            id=uuid.uuid4(),
            user_id=user_id,
            client_type=client_type,
            fumen_sha256=fumen_sha256,
            fumen_md5=fumen_md5,
            clear_type=clear_type,
            rate=rate,
            recorded_at=datetime(2026, 6, 1, tzinfo=UTC),
            synced_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )
    await db.flush()


async def _add_course(db: AsyncSession, *, course_id: uuid.UUID, name: str = "Test Course") -> Course:
    course = Course(
        id=course_id,
        name=name,
        md5_list=["m" * 32, "n" * 32],
        sha256_list=None,
        constraint=[],
        is_active=True,
        dan_title="Test Dan",
        synced_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    db.add(course)
    await db.flush()
    return course


async def _add_fumen(
    db: AsyncSession,
    *,
    sha256: str | None,
    md5: str | None,
    title: str = "Test Song",
    artist: str = "Test Artist",
) -> Fumen:
    fumen = Fumen(fumen_id=uuid.uuid4(), sha256=sha256, md5=md5, title=title, artist=artist)
    db.add(fumen)
    await db.flush()
    return fumen


async def _add_table_entry(db: AsyncSession, *, fumen_id: uuid.UUID, table_slug: str, level: str) -> None:
    table_id = uuid.uuid4()
    db.add(DifficultyTable(id=table_id, name="Test Table", slug=table_slug))
    db.add(FumenTableEntry(fumen_id=fumen_id, table_id=table_id, level=level))
    await db.flush()


def _table_cfg(slug: str = "test-table") -> TableRankingConfig:
    return TableRankingConfig(
        slug=slug,
        table_id=uuid.uuid4(),
        display_name="Test Table",
        display_order=1,
        level_order=["LEVEL 1"],
        level_weights={"LEVEL 1": 1.0},
        base_lamp_mult={"NOPLAY": 0.0, "HARD": 1.0, "FC": 1.0},
        upper_lamp_bonus={"NOPLAY": 0.0, "HARD": 0.0, "FC": 0.0},
        rank_mult={"F": 0.0, "AA": 1.0, "AAA": 1.08},
        bonus=BonusConfig(
            bp_weight=0.15, rate_weight=0.40, bp_floor=150.0, bp_slope=1.0, rate_floor=0.70, rate_slope=1.0,
        ),
        reference_20=ReferenceCondition(level="LEVEL 1", lamp="HARD", bp=0, rank="AA", rate=1.0),
        c_table=100.0,
        top_n=10,
        max_level=200,
    )


def _config() -> RankingConfig:
    return RankingConfig(tables=[_table_cfg()], exp_level_step=100.0, high_tier_rating_anchor=1000.0)


# ── list_goals ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_goals_empty(db_session: AsyncSession):
    result = await list_goals(goal_status="active", current_user=_user(), db=db_session)
    assert result == {"goals": [], "default_client_type": None}


@pytest.mark.asyncio
async def test_list_goals_reports_default_client_type_from_latest_sync(db_session: AsyncSession):
    user = _user()
    db_session.add(UserPlayerStats(id=uuid.uuid4(), user_id=user.id, client_type="lr2", synced_at=datetime(2026, 6, 1, tzinfo=UTC)))
    db_session.add(UserPlayerStats(id=uuid.uuid4(), user_id=user.id, client_type="beatoraja", synced_at=datetime(2026, 6, 5, tzinfo=UTC)))
    await db_session.flush()

    result = await list_goals(goal_status="active", current_user=user, db=db_session)

    assert result["default_client_type"] == "beatoraja"


# ── create_goal ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_chart_goal_success(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.routers.goals.get_ranking_config", _config)

    user = _user()
    sha256, md5 = "a" * 64, "b" * 32
    fumen = await _add_fumen(db_session, sha256=sha256, md5=md5)
    await _add_table_entry(db_session, fumen_id=fumen.fumen_id, table_slug="test-table", level="LEVEL 1")
    await _add_score(db_session, user_id=user.id, fumen_sha256=sha256, fumen_md5=md5, clear_type=5, rate=70.0)

    body = GoalCreate(
        goal_type="chart", client_type="beatoraja", table_slug="test-table",
        fumen_sha256=sha256, fumen_md5=md5, target_clear_type=7,
    )
    created = await create_goal(body, current_user=user, db=db_session)

    assert created["goal_type"] == "chart"
    assert created["status"] == "active"
    assert created["target_clear_type"] == 7
    assert created["title"] == "Test Song"
    assert created["artist"] == "Test Artist"
    assert created["level"] == "LEVEL 1"
    assert created["fumen_sha256"] == sha256
    assert created["fumen_md5"] == md5
    assert created["baseline_snapshot"]["clear_type"] == 5
    # projected_rating uses the target clear_type (7 == HARD) with baseline
    # rank/bp/rate fallback (rank None -> "F", rate 70.0 -> 0.70).
    assert created["projected_rating"] is not None
    assert created["projected_rating"] > 0

    row = (await db_session.execute(sa.select(UserGoal))).scalar_one()
    assert row.status == "active"
    assert row.user_id == user.id


@pytest.mark.asyncio
async def test_create_course_goal_success(db_session: AsyncSession):
    user = _user()
    course_id = _uid()
    course = await _add_course(db_session, course_id=course_id)
    md5_a, md5_b = course.md5_list
    course_hash = "headerhash" + md5_a + md5_b
    await _add_score(db_session, user_id=user.id, client_type="lr2", clear_type=5, rate=60.0)
    # Attach the course-shaped fumen_hash_others directly since _add_score
    # doesn't expose that kwarg.
    row = (await db_session.execute(sa.select(UserScore))).scalar_one()
    row.fumen_hash_others = course_hash
    await db_session.flush()

    body = GoalCreate(goal_type="course", client_type="lr2", course_id=course_id, target_clear_type=7)
    created = await create_goal(body, current_user=user, db=db_session)

    assert created["goal_type"] == "course"
    assert created["course_id"] == str(course_id)
    assert created["course_name"] == "Test Course"
    assert created["dan_title"] == "Test Dan"
    assert created["projected_rating"] is None  # rating never applies to courses


@pytest.mark.asyncio
async def test_create_goal_rejected_by_validation_returns_400(db_session: AsyncSession):
    user = _user()
    sha256 = "a" * 64
    await _add_score(db_session, user_id=user.id, fumen_sha256=sha256, clear_type=7)

    body = GoalCreate(
        goal_type="chart", client_type="beatoraja",
        fumen_sha256=sha256, target_clear_type=5,  # worse than baseline (7)
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_goal(body, current_user=user, db=db_session)

    assert exc_info.value.status_code == 400
    assert "clear_type_worse" in exc_info.value.detail["errors"]

    count = (await db_session.execute(sa.select(sa.func.count()).select_from(UserGoal))).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_create_duplicate_active_goal_returns_409(db_session: AsyncSession):
    user = _user()
    sha256 = "a" * 64
    await _add_score(db_session, user_id=user.id, fumen_sha256=sha256, clear_type=3)

    body = GoalCreate(goal_type="chart", client_type="beatoraja", fumen_sha256=sha256, target_clear_type=5)
    await create_goal(body, current_user=user, db=db_session)

    with pytest.raises(HTTPException) as exc_info:
        await create_goal(body, current_user=user, db=db_session)

    assert exc_info.value.status_code == 409

    count = (await db_session.execute(sa.select(sa.func.count()).select_from(UserGoal))).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_create_chart_goal_requires_hash() -> None:
    body = GoalCreate(goal_type="chart", client_type="beatoraja", target_clear_type=5)
    with pytest.raises(HTTPException) as exc_info:
        await create_goal(body, current_user=_user(), db=None)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_course_goal_requires_course_id() -> None:
    body = GoalCreate(goal_type="course", client_type="lr2", target_clear_type=5)
    with pytest.raises(HTTPException) as exc_info:
        await create_goal(body, current_user=_user(), db=None)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400


# ── delete_goal ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_goal_soft_deletes_and_hides_from_active_list(db_session: AsyncSession):
    user = _user()
    sha256 = "a" * 64
    await _add_score(db_session, user_id=user.id, fumen_sha256=sha256, clear_type=3)
    body = GoalCreate(goal_type="chart", client_type="beatoraja", fumen_sha256=sha256, target_clear_type=5)
    created = await create_goal(body, current_user=user, db=db_session)
    goal_id = uuid.UUID(created["goal_id"])

    await delete_goal(goal_id, current_user=user, db=db_session)

    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    assert row.deleted_at is not None  # soft delete: row still exists

    result = await list_goals(goal_status="active", current_user=user, db=db_session)
    assert result["goals"] == []


@pytest.mark.asyncio
async def test_delete_goal_not_owned_returns_404(db_session: AsyncSession):
    owner = _user()
    other = _user()
    sha256 = "a" * 64
    await _add_score(db_session, user_id=owner.id, fumen_sha256=sha256, clear_type=3)
    body = GoalCreate(goal_type="chart", client_type="beatoraja", fumen_sha256=sha256, target_clear_type=5)
    created = await create_goal(body, current_user=owner, db=db_session)
    goal_id = uuid.UUID(created["goal_id"])

    with pytest.raises(HTTPException) as exc_info:
        await delete_goal(goal_id, current_user=other, db=db_session)

    assert exc_info.value.status_code == 404

    # Row is untouched.
    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    assert row.deleted_at is None


# ── list_goal_achievements ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_achievements_by_date_filters_to_matching_day(db_session: AsyncSession):
    user = _user()
    achieved_goal_id = _uid()
    other_day_goal_id = _uid()
    active_goal_id = _uid()

    db_session.add(UserGoal(
        goal_id=achieved_goal_id, user_id=user.id, goal_type="chart", client_type="beatoraja",
        fumen_sha256="a" * 64, target_clear_type=7, status="achieved",
        baseline_snapshot={}, achieved_recorded_at=datetime(2026, 6, 15, 10, 0, tzinfo=UTC),
    ))
    db_session.add(UserGoal(
        goal_id=other_day_goal_id, user_id=user.id, goal_type="chart", client_type="beatoraja",
        fumen_sha256="c" * 64, target_clear_type=7, status="achieved",
        baseline_snapshot={}, achieved_recorded_at=datetime(2026, 6, 16, 10, 0, tzinfo=UTC),
    ))
    db_session.add(UserGoal(
        goal_id=active_goal_id, user_id=user.id, goal_type="chart", client_type="beatoraja",
        fumen_sha256="d" * 64, target_clear_type=7, status="active",
        baseline_snapshot={},
    ))
    await db_session.flush()

    result = await list_goal_achievements(date=date(2026, 6, 15), current_user=user, db=db_session)

    assert [g["goal_id"] for g in result["goals"]] == [str(achieved_goal_id)]


@pytest.mark.asyncio
async def test_achievements_by_date_excludes_soft_deleted(db_session: AsyncSession):
    user = _user()
    goal_id = _uid()
    db_session.add(UserGoal(
        goal_id=goal_id, user_id=user.id, goal_type="chart", client_type="beatoraja",
        fumen_sha256="a" * 64, target_clear_type=7, status="achieved",
        baseline_snapshot={}, achieved_recorded_at=datetime(2026, 6, 15, 10, 0, tzinfo=UTC),
        deleted_at=datetime(2026, 6, 16, tzinfo=UTC),
    ))
    await db_session.flush()

    result = await list_goal_achievements(date=date(2026, 6, 15), current_user=user, db=db_session)

    assert result["goals"] == []
