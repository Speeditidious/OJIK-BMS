"""Tests for the sync.py achievement-detection hook (Task 10).

`sync_data` is called directly (bypassing FastAPI's DI layer) against a real
in-memory SQLite session, mirroring the convention in `test_goals_api.py` /
`test_goal_evaluator.py` — raw DDL for the tables this hook touches
(`user_scores`, `courses`, `user_goals`, `fumens`), because
`Base.metadata.create_all` chokes on SQLite for Postgres-only
`server_default` expressions and the JSONB type used across the full model
set.

`_fetch_same_day_rows` is mocked for the same-day-merge test only, matching
`test_sync_metadata_only_update.py`'s convention — it relies on
`func.timezone(...)`, a Postgres-only construct that SQLite cannot render.
All other helpers run against the real DB so `evaluate_and_mark_achieved`'s
goal matching is exercised end-to-end, not mocked.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.course import Course
from app.models.goal import UserGoal
from app.models.score import UserScore
from app.routers import sync as sync_module
from app.routers.sync import ScoreSyncItem, SyncRequest, sync_data


# ── DB fixture ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for ddl in (
            """
            CREATE TABLE user_scores (
                id CHAR(32) PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
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
            # Matches the partial unique index sync.py's ON CONFLICT target
            # relies on (`_scorehash_conflict_index_elements`) — SQLite
            # requires a real matching index/constraint to exist for the
            # insert-path's `ON CONFLICT ... DO UPDATE` to be valid SQL.
            """
            CREATE UNIQUE INDEX uq_user_scores_scorehash
            ON user_scores (
                scorehash, user_id, client_type,
                COALESCE(fumen_sha256, ''), COALESCE(fumen_md5, ''), COALESCE(fumen_hash_others, '')
            )
            WHERE scorehash IS NOT NULL
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


async def _add_goal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    goal_type: str = "chart",
    client_type: str = "lr2",
    fumen_sha256: str | None = None,
    fumen_md5: str | None = None,
    course_id: uuid.UUID | None = None,
    target_clear_type: int | None = None,
    target_min_bp: int | None = None,
    target_rank: str | None = None,
    target_rate: float | None = None,
    status: str = "active",
) -> uuid.UUID:
    goal_id = uuid.uuid4()
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
    await db.flush()
    return goal_id


async def _add_course(
    db: AsyncSession,
    *,
    md5_list: list | None = None,
    sha256_list: list | None = None,
) -> Course:
    course = Course(
        id=uuid.uuid4(),
        name="Test Course",
        md5_list=md5_list or [],
        sha256_list=sha256_list,
        constraint=[],
        is_active=True,
        dan_title="Test Dan",
        synced_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    db.add(course)
    await db.flush()
    return course


async def _goal_status(db: AsyncSession, goal_id: uuid.UUID) -> str:
    row = (await db.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    return row.status


async def _sync(payload: SyncRequest, user: SimpleNamespace, db: AsyncSession):
    """Call sync_data with `_fetch_same_day_rows` mocked to "no same-day row".

    `_fetch_same_day_rows` uses `func.timezone(...)`, a Postgres-only
    construct SQLite cannot render (see module docstring) — every test that
    doesn't specifically exercise the same-day-merge path routes through here
    instead of calling `sync_data` directly.

    Also stubs out the post-sync ranking-recalculation Celery task: sync_data
    fires `recalculate_user_rankings.delay(...)` whenever any score is
    synced/inserted, and with no broker configured in the test environment
    that call hangs instead of failing fast (unlike the fumen-popularity
    refresh task, which sync_data itself wraps in try/except and — being
    unreachable here since we never populate `touched_fumen_ids` — never
    fires). Same convention as `test_table_import.py`'s
    `recalculate_all_rankings.delay` monkeypatch.
    """
    with patch("app.tasks.ranking_calculator.recalculate_user_rankings.delay", MagicMock()):
        with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
            return await sync_data(payload, debug=False, current_user=user, db=db)


# ── No active goals: pure regression check ──────────────────────────────────

@pytest.mark.asyncio
async def test_no_active_goals_sync_proceeds_unchanged(db_session: AsyncSession):
    """A user with no active goals: sync behaves exactly as before this hook."""
    user = _user()

    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_md5="a" * 32,
                client_type="lr2",
                clear_type=2,
                notes=1000,
                judgments={"perfect": 500, "great": 0, "good": 0, "bad": 0, "poor": 0},
                recorded_at=datetime(2026, 6, 1, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )

    result = await _sync(payload, user, db_session)

    assert result.synced_scores == 1
    assert result.inserted_scores == 1
    # No user_goals rows exist at all — nothing to have changed.
    rows = (await db_session.execute(sa.select(UserGoal))).scalars().all()
    assert rows == []


# ── Chart goal achieved by a newly-synced improving score ───────────────────

@pytest.mark.asyncio
async def test_chart_goal_achieved_by_improving_score(db_session: AsyncSession):
    user = _user()
    sha256 = "a" * 64
    recorded_at = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
    goal_id = await _add_goal(
        db_session, user_id=user.id, client_type="lr2",
        fumen_sha256=sha256, target_clear_type=5,
    )

    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256=sha256,
                client_type="lr2",
                clear_type=7,
                notes=1000,
                judgments={"perfect": 500, "great": 0, "good": 0, "bad": 0, "poor": 0},
                recorded_at=recorded_at,
            )
        ],
        player_stats=[],
    )

    result = await _sync(payload, user, db_session)

    assert result.synced_scores == 1
    assert await _goal_status(db_session, goal_id) == "achieved"
    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    assert row.achieved_recorded_at.replace(tzinfo=UTC) == recorded_at


@pytest.mark.asyncio
async def test_chart_goal_achieved_recorded_at_falls_back_to_now_when_absent(db_session: AsyncSession):
    """A record with no recorded_at attributes achievement to server receipt time."""
    user = _user()
    sha256 = "b" * 64
    goal_id = await _add_goal(
        db_session, user_id=user.id, client_type="lr2",
        fumen_sha256=sha256, target_clear_type=5,
    )

    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256=sha256,
                client_type="lr2",
                clear_type=7,
                notes=1000,
                judgments={"perfect": 500, "great": 0, "good": 0, "bad": 0, "poor": 0},
                recorded_at=None,
            )
        ],
        player_stats=[],
    )

    before = datetime.now(UTC)
    result = await _sync(payload, user, db_session)
    after = datetime.now(UTC)

    assert result.synced_scores == 1
    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    achieved_recorded_at = row.achieved_recorded_at.replace(tzinfo=UTC)
    assert before <= achieved_recorded_at <= after


# ── Chart goal not yet met ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chart_goal_not_met_stays_active(db_session: AsyncSession):
    user = _user()
    sha256 = "c" * 64
    goal_id = await _add_goal(
        db_session, user_id=user.id, client_type="lr2",
        fumen_sha256=sha256, target_clear_type=9,
    )

    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256=sha256,
                client_type="lr2",
                clear_type=6,  # improves from no-baseline, but short of target 9
                notes=1000,
                judgments={"perfect": 500, "great": 0, "good": 0, "bad": 0, "poor": 0},
                recorded_at=datetime(2026, 6, 5, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )

    result = await _sync(payload, user, db_session)

    assert result.synced_scores == 1
    assert await _goal_status(db_session, goal_id) == "active"


# ── Metadata-only re-sync must NOT trigger achievement ──────────────────────

@pytest.mark.asyncio
async def test_metadata_only_resync_does_not_trigger_achievement(db_session: AsyncSession):
    """Proves the hook sits before `synced_scores += 1`, not after every DB
    write: a goal whose target is already satisfied by the stored best must
    only transition when a genuinely improving score triggers it — not on a
    later metadata-only re-sync (judgments changed, score did not improve)."""
    user = _user()
    sha256 = "d" * 64
    recorded_at = datetime(2026, 6, 5, tzinfo=UTC)

    # First sync establishes the baseline row (clear_type=7) — no goal exists yet.
    baseline_payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256=sha256,
                client_type="lr2",
                clear_type=7,
                notes=1000,
                judgments={"perfect": 500, "great": 0, "good": 0, "bad": 0, "poor": 0},
                recorded_at=recorded_at,
            )
        ],
        player_stats=[],
    )
    baseline_result = await _sync(baseline_payload, user, db_session)
    assert baseline_result.inserted_scores == 1

    # Goal created after the fact — its target (clear_type=7) is already met
    # by the stored best, simulating a goal whose baseline check was bypassed
    # (or a target equal to a pre-existing score).
    goal_id = await _add_goal(
        db_session, user_id=user.id, client_type="lr2",
        fumen_sha256=sha256, target_clear_type=7,
    )

    # Re-sync with identical clear_type/exscore (no improvement) but changed
    # judgments — this is the metadata-only `continue` branch.
    metadata_payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256=sha256,
                client_type="lr2",
                clear_type=7,
                # No notes/exscore supplied -> exscore stays None -> _is_improvement
                # cannot see an exscore improvement; clear_type is equal (not
                # strictly greater) -> not an improvement.
                judgments={"perfect": 400, "great": 100, "good": 0, "bad": 0, "poor": 0},
                recorded_at=recorded_at,
            )
        ],
        player_stats=[],
    )
    result = await _sync(metadata_payload, user, db_session)

    assert result.metadata_updated == 1
    assert result.synced_scores == 0
    assert await _goal_status(db_session, goal_id) == "active", (
        "metadata-only re-sync must not achieve a goal even though the "
        "already-stored value would technically satisfy it"
    )


# ── Same-day merge DOES trigger achievement with merged values ──────────────

@pytest.mark.asyncio
async def test_same_day_merge_triggers_achievement_with_merged_values(db_session: AsyncSession):
    """Proves the hook reads the reassigned post-merge item/rank/rate, not the
    raw incoming payload: the submitted item's own clear_type (3) does NOT
    satisfy the goal, but the merged value (7, inherited from the existing
    same-day row) does."""
    user = _user()
    md5 = "e" * 32
    recorded_at = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
    row_id = uuid.uuid4()

    goal_id = await _add_goal(
        db_session, user_id=user.id, client_type="lr2",
        fumen_md5=md5, target_clear_type=7,
    )

    existing_same_day = UserScore(
        id=row_id,
        user_id=user.id,
        client_type="lr2",
        fumen_md5=md5,
        clear_type=7,
        exscore=500,
        recorded_at=recorded_at,
    )

    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_md5=md5,
                client_type="lr2",
                clear_type=3,  # lower than existing (7) -- must NOT satisfy alone
                exscore=600,   # higher than existing (500) -- triggers the improvement gate
                recorded_at=recorded_at,
            )
        ],
        player_stats=[],
    )

    with patch.object(
        sync_module,
        "_fetch_current_bests",
        AsyncMock(return_value={
            (None, md5, None, "lr2"): {
                "clear_type": 7, "exscore": 500, "min_bp": None, "max_combo": None, "play_count": None,
                "_latest_row_id": row_id, "_latest_recorded_at": recorded_at, "_latest_synced_at": recorded_at,
                "_latest_sort_key": (recorded_at, str(row_id)),
                "_latest_judgments": None, "_latest_options": None, "_latest_clear_count": None,
                "_latest_scorehash": None, "_latest_fumen_id": None,
            }
        }),
    ):
        with patch.object(
            sync_module,
            "_fetch_same_day_rows",
            AsyncMock(return_value={(md5, "lr2", recorded_at.date()): existing_same_day}),
        ):
            with patch("app.tasks.ranking_calculator.recalculate_user_rankings.delay", MagicMock()):
                result = await sync_data(payload, debug=False, current_user=user, db=db_session)

    assert result.synced_scores == 1
    assert await _goal_status(db_session, goal_id) == "achieved"


# ── Course goal achieved via matching fumen_hash_others ──────────────────────

@pytest.mark.asyncio
async def test_course_goal_achieved_lr2_suffix_match(db_session: AsyncSession):
    user = _user()
    md5_a, md5_b = "m" * 32, "n" * 32
    course = await _add_course(db_session, md5_list=[md5_a, md5_b], sha256_list=None)
    goal_id = await _add_goal(
        db_session, user_id=user.id, goal_type="course", client_type="lr2",
        course_id=course.id, target_clear_type=5,
    )

    # LR2 course hash: a header hash prefix + the joined stage md5s (see
    # score_row_detail.match_course_from_hash's lr2 suffix rule).
    course_hash = "headerhash" + md5_a + md5_b
    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_hash_others=course_hash,
                client_type="lr2",
                clear_type=6,
                recorded_at=datetime(2026, 6, 5, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )

    result = await _sync(payload, user, db_session)

    assert result.synced_scores == 1
    assert await _goal_status(db_session, goal_id) == "achieved"


@pytest.mark.asyncio
async def test_course_score_with_no_matching_course_does_not_crash(db_session: AsyncSession):
    """A course score whose fumen_hash_others matches no Course row must not
    crash sync and must not add an achievement candidate."""
    user = _user()
    # Seed an unrelated course goal so has_active_goals is True and the course
    # table gets fetched, exercising the "no match found" branch.
    course = await _add_course(db_session, md5_list=["x" * 32], sha256_list=None)
    goal_id = await _add_goal(
        db_session, user_id=user.id, goal_type="course", client_type="lr2",
        course_id=course.id, target_clear_type=5,
    )

    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_hash_others="headerhash" + "z" * 32,  # matches no course
                client_type="lr2",
                clear_type=6,
                recorded_at=datetime(2026, 6, 5, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )

    result = await _sync(payload, user, db_session)

    assert result.synced_scores == 1
    assert result.errors == []
    assert await _goal_status(db_session, goal_id) == "active"


# ── Sync retry: goal transitions only once, no error on the retry ──────────

@pytest.mark.asyncio
async def test_sync_retry_transitions_goal_only_once(db_session: AsyncSession):
    user = _user()
    sha256 = "f" * 64
    recorded_at = datetime(2026, 6, 5, tzinfo=UTC)
    goal_id = await _add_goal(
        db_session, user_id=user.id, client_type="lr2",
        fumen_sha256=sha256, target_clear_type=6,
    )

    def make_payload() -> SyncRequest:
        return SyncRequest(
            scores=[
                ScoreSyncItem(
                    fumen_sha256=sha256,
                    client_type="lr2",
                    clear_type=7,
                    notes=1000,
                    judgments={"perfect": 500, "great": 0, "good": 0, "bad": 0, "poor": 0},
                    recorded_at=recorded_at,
                )
            ],
            player_stats=[],
        )

    first_result = await _sync(make_payload(), user, db_session)
    assert first_result.synced_scores == 1
    assert await _goal_status(db_session, goal_id) == "achieved"
    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    first_achieved_at = row.achieved_at

    # Simulated client re-send of the same payload — must not error and must
    # not re-transition (or otherwise disturb) the already-achieved goal.
    second_result = await _sync(make_payload(), user, db_session)

    assert second_result.errors == []
    assert await _goal_status(db_session, goal_id) == "achieved"
    row = (await db_session.execute(sa.select(UserGoal).where(UserGoal.goal_id == goal_id))).scalar_one()
    assert row.achieved_at == first_achieved_at
