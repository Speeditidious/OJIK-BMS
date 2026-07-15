"""Tests for the goal evaluator service (Task 8).

`validate_goal_target` is pure logic and tested without a DB. The
baseline/achievement functions are tested against a real (in-memory SQLite)
DB rather than mocks, per plan/task-brief guidance.

Uses a local `db_session` fixture with raw DDL for the three tables this
module touches (`user_scores`, `courses`, `user_goals`) — mirroring the
pattern in `test_fumen_popularity.py` — because `Base.metadata.create_all`
against SQLite chokes on Postgres-only server_default expressions
(`gen_random_uuid()`, `now()`) and the `JSONB` type used across the full
model set.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.course import Course
from app.models.goal import UserGoal
from app.models.score import UserScore
from app.services.goal_evaluator import (
    GoalAchievementCandidate,
    GoalBaseline,
    compute_chart_baseline,
    compute_course_baseline,
    evaluate_and_mark_achieved,
    validate_goal_target,
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
        ):
            await conn.execute(sa.text(ddl))

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _add_score(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    client_type: str = "beatoraja",
    fumen_sha256: str | None = None,
    fumen_md5: str | None = None,
    fumen_hash_others: str | None = None,
    clear_type: int | None = None,
    min_bp: int | None = None,
    rank: str | None = None,
    rate: float | None = None,
) -> None:
    db.add(
        UserScore(
            id=uuid.uuid4(),
            user_id=user_id,
            client_type=client_type,
            fumen_sha256=fumen_sha256,
            fumen_md5=fumen_md5,
            fumen_hash_others=fumen_hash_others,
            clear_type=clear_type,
            min_bp=min_bp,
            rank=rank,
            rate=rate,
            recorded_at=datetime(2026, 6, 1, tzinfo=UTC),
            synced_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )


def _add_course(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    md5_list: list | None,
    sha256_list: list | None,
) -> None:
    db.add(
        Course(
            id=course_id,
            name="Test Course",
            md5_list=md5_list or [],
            sha256_list=sha256_list,
            constraint=[],
            is_active=True,
            dan_title="",
            synced_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )


def _add_goal(
    db: AsyncSession,
    *,
    goal_id: uuid.UUID | None = None,
    user_id: uuid.UUID,
    goal_type: str = "chart",
    client_type: str = "beatoraja",
    fumen_sha256: str | None = None,
    fumen_md5: str | None = None,
    course_id: uuid.UUID | None = None,
    target_clear_type: int | None = None,
    target_min_bp: int | None = None,
    target_rank: str | None = None,
    target_rate: float | None = None,
    status: str = "active",
) -> uuid.UUID:
    goal_id = goal_id or uuid.uuid4()
    db.add(
        UserGoal(
            goal_id=goal_id,
            user_id=user_id,
            goal_type=goal_type,
            client_type=client_type,
            fumen_sha256=fumen_sha256,
            fumen_md5=fumen_md5,
            course_id=course_id,
            target_clear_type=target_clear_type,
            target_min_bp=target_min_bp,
            target_rank=target_rank,
            target_rate=target_rate,
            status=status,
            baseline_snapshot={},
            created_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )
    return goal_id


# ── validate_goal_target (pure, no DB) ──────────────────────────────────────

def test_validate_clear_only_improvement():
    baseline = GoalBaseline(clear_type=5, min_bp=None, rank=None, rate=None)
    result = validate_goal_target(baseline, target_clear_type=7)
    assert result.ok is True
    assert result.improved_metrics == ["clear_type"]
    assert result.errors == []


def test_validate_bp_only_improvement_lower_is_better():
    baseline = GoalBaseline(clear_type=None, min_bp=50, rank=None, rate=None)
    result = validate_goal_target(baseline, target_min_bp=30)
    assert result.ok is True
    assert result.improved_metrics == ["min_bp"]


def test_validate_bp_no_baseline_bp_is_allowed_but_not_scored_as_improvement():
    """Judgment call (flagged in report): when baseline.min_bp is None, any
    target_min_bp is allowed (never forbidden) but is not itself counted as
    an "improvement" — there's nothing to compare against."""
    baseline = GoalBaseline(clear_type=None, min_bp=None, rank=None, rate=None)
    result = validate_goal_target(baseline, target_min_bp=10)
    assert "min_bp_worse" not in result.errors
    assert "min_bp" not in result.improved_metrics
    # Nothing else selected and no improvement recorded -> overall not ok.
    assert result.ok is False
    assert "no_improvement" in result.errors


def test_validate_rank_only_improvement():
    baseline = GoalBaseline(clear_type=None, min_bp=None, rank="B", rate=None)
    result = validate_goal_target(baseline, target_rank="AA")
    assert result.ok is True
    assert result.improved_metrics == ["rank"]


def test_validate_rate_only_improvement():
    baseline = GoalBaseline(clear_type=None, min_bp=None, rank=None, rate=80.0)
    result = validate_goal_target(baseline, target_rate=90.0)
    assert result.ok is True
    assert result.improved_metrics == ["rate"]


def test_validate_multi_metric_one_improves_one_holds_steady():
    baseline = GoalBaseline(clear_type=5, min_bp=None, rank=None, rate=80.0)
    result = validate_goal_target(baseline, target_clear_type=7, target_rate=80.0)
    assert result.ok is True
    assert result.improved_metrics == ["clear_type"]
    assert result.errors == []


def test_validate_forbidden_clear_type():
    baseline = GoalBaseline(clear_type=5, min_bp=None, rank=None, rate=None)
    result = validate_goal_target(baseline, target_clear_type=3)
    assert result.ok is False
    assert "clear_type_worse" in result.errors


def test_validate_forbidden_bp():
    baseline = GoalBaseline(clear_type=None, min_bp=30, rank=None, rate=None)
    result = validate_goal_target(baseline, target_min_bp=50)
    assert result.ok is False
    assert "min_bp_worse" in result.errors


def test_validate_forbidden_rank():
    baseline = GoalBaseline(clear_type=None, min_bp=None, rank="AA", rate=None)
    result = validate_goal_target(baseline, target_rank="B")
    assert result.ok is False
    assert "rank_worse" in result.errors


def test_validate_forbidden_rate():
    baseline = GoalBaseline(clear_type=None, min_bp=None, rank=None, rate=90.0)
    result = validate_goal_target(baseline, target_rate=80.0)
    assert result.ok is False
    assert "rate_worse" in result.errors


def test_validate_nothing_selected():
    baseline = GoalBaseline(clear_type=None, min_bp=None, rank=None, rate=None)
    result = validate_goal_target(baseline)
    assert result.ok is False
    assert "no_metric_selected" in result.errors


def test_validate_no_improvement_all_held_steady():
    baseline = GoalBaseline(clear_type=5, min_bp=None, rank=None, rate=80.0)
    result = validate_goal_target(baseline, target_clear_type=5, target_rate=80.0)
    assert result.ok is False
    assert result.errors == ["no_improvement"]
    assert result.improved_metrics == []


def test_validate_noplay_only_goal_is_naturally_rejected():
    """Verifies the "NOPLAY-only" rejection falls out of the general rule
    (no special case needed): target_clear_type=0 against a None/0 baseline
    is never an improvement, so overall ok is False."""
    baseline = GoalBaseline(clear_type=None, min_bp=None, rank=None, rate=None)
    result = validate_goal_target(baseline, target_clear_type=0)
    assert result.ok is False
    assert "clear_type" not in result.improved_metrics


# ── compute_chart_baseline ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chart_baseline_no_rows_is_all_none(db_session: AsyncSession):
    baseline = await compute_chart_baseline(
        db_session, _uid(), "beatoraja", fumen_sha256="a" * 64, fumen_md5="b" * 32
    )
    assert baseline == GoalBaseline(None, None, None, None)


@pytest.mark.asyncio
async def test_chart_baseline_finds_lr2_md5_only_rows(db_session: AsyncSession):
    user_id = _uid()
    sha256 = "a" * 64
    md5 = "b" * 32
    # LR2 row: fumen_sha256 is NULL, only md5 is set.
    _add_score(db_session, user_id=user_id, client_type="lr2", fumen_md5=md5, clear_type=7, rate=85.0)
    await db_session.flush()

    baseline = await compute_chart_baseline(db_session, user_id, "lr2", fumen_sha256=sha256, fumen_md5=md5)

    assert baseline.clear_type == 7
    assert baseline.rate == 85.0


@pytest.mark.asyncio
async def test_chart_baseline_mixed_sha256_and_md5_rows(db_session: AsyncSession):
    user_id = _uid()
    sha256 = "a" * 64
    md5 = "b" * 32
    _add_score(db_session, user_id=user_id, client_type="beatoraja", fumen_sha256=sha256, fumen_md5=md5, clear_type=5)
    _add_score(db_session, user_id=user_id, client_type="beatoraja", fumen_md5=md5, clear_type=8)
    await db_session.flush()

    baseline = await compute_chart_baseline(db_session, user_id, "beatoraja", fumen_sha256=sha256, fumen_md5=md5)

    assert baseline.clear_type == 8


@pytest.mark.asyncio
async def test_chart_baseline_per_metric_independence(db_session: AsyncSession):
    """Best clear from one row, best rate from a different row — the
    baseline must not collapse to a single 'best row'."""
    user_id = _uid()
    sha256 = "a" * 64
    md5 = "b" * 32
    _add_score(
        db_session, user_id=user_id, client_type="beatoraja", fumen_sha256=sha256, fumen_md5=md5,
        clear_type=9, rate=70.0, min_bp=100, rank="C",
    )
    _add_score(
        db_session, user_id=user_id, client_type="beatoraja", fumen_sha256=sha256, fumen_md5=md5,
        clear_type=5, rate=98.5, min_bp=2, rank="AAA",
    )
    await db_session.flush()

    baseline = await compute_chart_baseline(db_session, user_id, "beatoraja", fumen_sha256=sha256, fumen_md5=md5)

    assert baseline.clear_type == 9      # from row 1
    assert baseline.rate == 98.5         # from row 2
    assert baseline.min_bp == 2          # from row 2 (lower is better)
    assert baseline.rank == "AAA"        # from row 2


@pytest.mark.asyncio
async def test_chart_baseline_excludes_course_rows(db_session: AsyncSession):
    """A row with fumen_hash_others set belongs to a course, not this chart."""
    user_id = _uid()
    sha256 = "a" * 64
    _add_score(db_session, user_id=user_id, fumen_sha256=sha256, fumen_hash_others="course-hash", clear_type=9)
    await db_session.flush()

    baseline = await compute_chart_baseline(db_session, user_id, "beatoraja", fumen_sha256=sha256, fumen_md5=None)

    assert baseline == GoalBaseline(None, None, None, None)


# ── compute_course_baseline ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_course_baseline_no_rows_is_all_none(db_session: AsyncSession):
    course_id = _uid()
    _add_course(db_session, course_id=course_id, md5_list=["m" * 32, "n" * 32], sha256_list=None)
    await db_session.flush()

    baseline = await compute_course_baseline(db_session, _uid(), "lr2", course_id)

    assert baseline == GoalBaseline(None, None, None, None)


@pytest.mark.asyncio
async def test_course_baseline_missing_course_returns_all_none(db_session: AsyncSession):
    baseline = await compute_course_baseline(db_session, _uid(), "lr2", _uid())
    assert baseline == GoalBaseline(None, None, None, None)


@pytest.mark.asyncio
async def test_course_baseline_lr2_suffix_match(db_session: AsyncSession):
    user_id = _uid()
    course_id = _uid()
    md5_a, md5_b = "m" * 32, "n" * 32
    _add_course(db_session, course_id=course_id, md5_list=[md5_a, md5_b], sha256_list=None)
    # LR2 course hash is a header hash prefix + the joined stage md5s.
    course_hash = "headerhash" + md5_a + md5_b
    _add_score(db_session, user_id=user_id, client_type="lr2", fumen_hash_others=course_hash, clear_type=6, rate=75.0)
    await db_session.flush()

    baseline = await compute_course_baseline(db_session, user_id, "lr2", course_id)

    assert baseline.clear_type == 6
    assert baseline.rate == 75.0


@pytest.mark.asyncio
async def test_course_baseline_lr2_md5_list_with_hole_still_matches(db_session: AsyncSession):
    """`match_course_from_hash` (score_row_detail.py) is deliberately lenient
    for lr2: it drops falsy/None entries from md5_list before joining, and
    still matches as long as at least one truthy value remains — per
    table_import.py, per-stage md5/sha256 entries can legitimately be None.
    `_course_hash_condition` must mirror this exactly, not reject the whole
    course just because one stage's md5 is missing."""
    user_id = _uid()
    course_id = _uid()
    md5_a, md5_b = "m" * 32, "n" * 32
    # Hole in the middle of md5_list (e.g. a stage with unknown md5).
    _add_course(db_session, course_id=course_id, md5_list=[md5_a, None, md5_b], sha256_list=None)
    # A real sync would only ever combine the truthy stage hashes.
    course_hash = "headerhash" + md5_a + md5_b
    _add_score(db_session, user_id=user_id, client_type="lr2", fumen_hash_others=course_hash, clear_type=5, rate=60.0)
    await db_session.flush()

    baseline = await compute_course_baseline(db_session, user_id, "lr2", course_id)

    assert baseline.clear_type == 5
    assert baseline.rate == 60.0


@pytest.mark.asyncio
async def test_course_baseline_beatoraja_exact_match(db_session: AsyncSession):
    user_id = _uid()
    course_id = _uid()
    sha_a, sha_b = "s" * 64, "t" * 64
    _add_course(db_session, course_id=course_id, md5_list=[], sha256_list=[sha_a, sha_b])
    _add_score(
        db_session, user_id=user_id, client_type="beatoraja",
        fumen_hash_others=sha_a + sha_b, clear_type=7,
    )
    await db_session.flush()

    baseline = await compute_course_baseline(db_session, user_id, "beatoraja", course_id)

    assert baseline.clear_type == 7


@pytest.mark.asyncio
async def test_course_baseline_incomplete_hash_list_returns_all_none(db_session: AsyncSession):
    """If the course has no sha256_list data for beatoraja, there's no
    well-defined expected hash — must not silently match unrelated rows."""
    course_id = _uid()
    _add_course(db_session, course_id=course_id, md5_list=["m" * 32], sha256_list=None)
    await db_session.flush()

    baseline = await compute_course_baseline(db_session, _uid(), "beatoraja", course_id)

    assert baseline == GoalBaseline(None, None, None, None)


# ── evaluate_and_mark_achieved ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fully_satisfied_goal_is_transitioned_and_returned(db_session: AsyncSession):
    user_id = _uid()
    sha256 = "a" * 64
    goal_id = _add_goal(
        db_session, user_id=user_id, client_type="beatoraja",
        fumen_sha256=sha256, target_clear_type=7, target_rate=80.0,
    )
    await db_session.commit()

    candidate = GoalAchievementCandidate(
        user_id=user_id, client_type="beatoraja", goal_type="chart",
        fumen_sha256=sha256, fumen_md5=None, course_id=None,
        clear_type=7, min_bp=None, rank=None, rate=85.0,
        recorded_at=datetime(2026, 6, 2, tzinfo=UTC),
    )

    achieved = await evaluate_and_mark_achieved(db_session, [candidate])
    await db_session.commit()

    assert achieved == [goal_id]

    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    assert row.status == "achieved"
    # SQLite round-trips DATETIME as tz-naive; compare the naive components only.
    assert row.achieved_recorded_at.replace(tzinfo=UTC) == datetime(2026, 6, 2, tzinfo=UTC)
    assert row.achieved_at is not None


@pytest.mark.asyncio
async def test_partially_satisfied_goal_is_not_transitioned(db_session: AsyncSession):
    user_id = _uid()
    sha256 = "a" * 64
    goal_id = _add_goal(
        db_session, user_id=user_id, client_type="beatoraja",
        fumen_sha256=sha256, target_clear_type=7, target_min_bp=10,
    )
    await db_session.commit()

    # clear_type target satisfied, but min_bp target (10) is not (candidate has 50).
    candidate = GoalAchievementCandidate(
        user_id=user_id, client_type="beatoraja", goal_type="chart",
        fumen_sha256=sha256, fumen_md5=None, course_id=None,
        clear_type=9, min_bp=50, rank=None, rate=None,
        recorded_at=datetime(2026, 6, 2, tzinfo=UTC),
    )

    achieved = await evaluate_and_mark_achieved(db_session, [candidate])
    await db_session.commit()

    assert achieved == []
    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    assert row.status == "active"


@pytest.mark.asyncio
async def test_missing_bp_candidate_does_not_satisfy_bp_target(db_session: AsyncSession):
    """A goal with target_min_bp set is not satisfied if candidate.min_bp is None."""
    user_id = _uid()
    sha256 = "a" * 64
    goal_id = _add_goal(
        db_session, user_id=user_id, client_type="beatoraja",
        fumen_sha256=sha256, target_min_bp=10,
    )
    await db_session.commit()

    candidate = GoalAchievementCandidate(
        user_id=user_id, client_type="beatoraja", goal_type="chart",
        fumen_sha256=sha256, fumen_md5=None, course_id=None,
        clear_type=None, min_bp=None, rank=None, rate=None,
        recorded_at=datetime(2026, 6, 2, tzinfo=UTC),
    )

    achieved = await evaluate_and_mark_achieved(db_session, [candidate])
    await db_session.commit()

    assert achieved == []
    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    assert row.status == "active"


@pytest.mark.asyncio
async def test_retry_with_same_candidate_only_transitions_once(db_session: AsyncSession):
    """Simulates a sync retry: calling evaluate_and_mark_achieved twice with
    the same candidate must only transition the goal once — the second call
    is a no-op thanks to the `WHERE status='active'` guard."""
    user_id = _uid()
    sha256 = "a" * 64
    goal_id = _add_goal(
        db_session, user_id=user_id, client_type="beatoraja",
        fumen_sha256=sha256, target_clear_type=7,
    )
    await db_session.commit()

    candidate = GoalAchievementCandidate(
        user_id=user_id, client_type="beatoraja", goal_type="chart",
        fumen_sha256=sha256, fumen_md5=None, course_id=None,
        clear_type=9, min_bp=None, rank=None, rate=None,
        recorded_at=datetime(2026, 6, 2, tzinfo=UTC),
    )

    first = await evaluate_and_mark_achieved(db_session, [candidate])
    await db_session.commit()
    second = await evaluate_and_mark_achieved(db_session, [candidate])
    await db_session.commit()

    assert first == [goal_id]
    assert second == []


@pytest.mark.asyncio
async def test_course_candidate_matches_course_goal(db_session: AsyncSession):
    user_id = _uid()
    course_id = _uid()
    goal_id = _add_goal(
        db_session, user_id=user_id, goal_type="course", client_type="lr2",
        course_id=course_id, target_clear_type=5,
    )
    await db_session.commit()

    candidate = GoalAchievementCandidate(
        user_id=user_id, client_type="lr2", goal_type="course",
        fumen_sha256=None, fumen_md5=None, course_id=course_id,
        clear_type=6, min_bp=None, rank=None, rate=None,
        recorded_at=datetime(2026, 6, 2, tzinfo=UTC),
    )

    achieved = await evaluate_and_mark_achieved(db_session, [candidate])
    await db_session.commit()

    assert achieved == [goal_id]
