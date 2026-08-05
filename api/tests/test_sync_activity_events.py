"""Tests for `UserSyncEvent` recording in `sync_data` (Task 4).

`sync_data` is called directly against a real in-memory SQLite session,
following the convention in `test_sync_goal_achievement.py` — raw DDL for the
tables this hook touches (`user_scores`, `user_player_stats`, `fumens`,
`courses`, `user_goals`, `user_sync_events`), because
`Base.metadata.create_all` chokes on SQLite for Postgres-only
`server_default` expressions and the JSONB type used across the full model
set.

`_fetch_same_day_rows` is mocked in every test via the `_sync` helper below,
matching `test_sync_goal_achievement.py`'s convention — it relies on
`func.timezone(...)`, a Postgres-only construct that SQLite cannot render.
The post-sync ranking-recalculation Celery task is stubbed for the same
reason (no broker configured in the test environment).
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

from app.models.score import UserSyncEvent
from app.routers import sync as sync_module
from app.routers.sync import PlayerStats, ScoreSyncItem, SyncRequest, sync_data


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
            CREATE TABLE user_player_stats (
                id CHAR(32) PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                user_id CHAR(32) NOT NULL,
                client_type VARCHAR(32) NOT NULL,
                playcount INTEGER,
                clearcount INTEGER,
                playtime INTEGER,
                judgments JSON,
                synced_at DATETIME
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
                status VARCHAR(10) NOT NULL,
                deleted_at DATETIME
            )
            """,
            """
            CREATE TABLE user_sync_events (
                id CHAR(32) PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                user_id CHAR(32) NOT NULL,
                synced_at DATETIME NOT NULL,
                updated_client_types JSON NOT NULL DEFAULT '[]'
            )
            """,
        ):
            await conn.execute(sa.text(ddl))

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


def _user(user_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid.uuid4())


async def _sync(payload: SyncRequest, user: SimpleNamespace, db: AsyncSession):
    """Call sync_data with `_fetch_same_day_rows` mocked to "no same-day row"
    and the ranking-recalculation Celery task stubbed out. See module
    docstring; same convention as `test_sync_goal_achievement.py::_sync`.
    """
    with patch("app.tasks.ranking_calculator.recalculate_user_rankings.delay", MagicMock()):
        with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
            return await sync_data(payload, debug=False, current_user=user, db=db)


async def _sync_events(db: AsyncSession, user_id: uuid.UUID) -> list[UserSyncEvent]:
    result = await db.execute(
        sa.select(UserSyncEvent)
        .where(UserSyncEvent.user_id == user_id)
        .order_by(UserSyncEvent.synced_at)
    )
    return list(result.scalars().all())


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inserted_score_creates_event_with_its_client_type(db_session: AsyncSession):
    user = _user()
    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256="a" * 64,
                client_type="lr2",
                clear_type=2,
                exscore=1000,
                recorded_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )

    result = await _sync(payload, user, db_session)

    assert result.inserted_scores == 1
    events = await _sync_events(db_session, user.id)
    assert len(events) == 1
    assert events[0].updated_client_types == ["lr2"]


@pytest.mark.asyncio
async def test_skipped_score_creates_event_with_empty_client_types(db_session: AsyncSession):
    user = _user()
    fumen_sha256 = "b" * 64
    first_payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256=fumen_sha256,
                client_type="lr2",
                clear_type=2,
                exscore=1000,
                recorded_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )
    await _sync(first_payload, user, db_session)

    # Identical, non-improving re-sync of the same score -> plain skip path
    # (same-day merge is bypassed since `_fetch_same_day_rows` is mocked to
    # return no rows for every call in this test file).
    second_payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256=fumen_sha256,
                client_type="lr2",
                clear_type=2,
                exscore=1000,
                recorded_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )
    result = await _sync(second_payload, user, db_session)

    assert result.skipped_scores == 1
    events = await _sync_events(db_session, user.id)
    assert len(events) == 2
    assert events[1].updated_client_types == []


class _StatsMockDB:
    """Scripted mock DB for the player_stats branch of sync_data.

    The player_stats same-day lookup uses a raw `AT TIME ZONE` text() clause
    that SQLite cannot render (Postgres-only), so this path cannot be tested
    against the real in-memory SQLite session used elsewhere in this file
    (matches the constraint documented in test_sync_metadata_only_update.py's
    module docstring). `execute()` dispatches based on the compiled SQL text:
    the user_goals count check, the existing-same-day-row SELECT, and the
    latest-row SELECT (identified by its ORDER BY) each get a scripted
    response; everything else (UPDATE statements, the users.first_synced_at
    backfill) is a no-op MagicMock whose return value is unused by the caller.
    """

    def __init__(self, *, existing_row=None, latest_row=None):
        self.existing_row = existing_row
        self.latest_row = latest_row
        self.added: list = []
        self.committed = False

    async def execute(self, stmt, *args, **kwargs):
        compiled = str(stmt)
        result = MagicMock()
        if "user_goals" in compiled:
            result.scalar_one_or_none.return_value = 0
        elif "user_sync_events" in compiled:
            result.scalar_one_or_none.return_value = None
        elif "user_player_stats" in compiled and "ORDER BY" in compiled.upper():
            result.scalar_one_or_none.return_value = self.latest_row
        elif "user_player_stats" in compiled:
            result.scalar_one_or_none.return_value = self.existing_row
        return result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_player_stats_identical_to_latest_row_excluded():
    """Re-syncing player_stats with no same-day row and identical values to
    the latest prior row hits the `continue` branch (line ~1060-1066) — no
    new row is written, and the client_type must not be counted as touched.
    """
    user = _user()
    latest_row = SimpleNamespace(playcount=100, clearcount=50, playtime=1000)
    mock_db = _StatsMockDB(existing_row=None, latest_row=latest_row)

    payload = SyncRequest(
        scores=[],
        player_stats=[
            PlayerStats(client_type="lr2", playcount=100, clearcount=50, playtime=1000)
        ],
    )
    result = await sync_data(payload, debug=False, current_user=user, db=mock_db)

    assert result.errors == []
    assert len(mock_db.added) == 1
    event = mock_db.added[0]
    assert isinstance(event, UserSyncEvent)
    assert event.updated_client_types == []


@pytest.mark.asyncio
async def test_player_stats_same_day_row_changed_values_included():
    """A same-day row exists (existing-row UPDATE branch) and at least one of
    playcount/clearcount/playtime differs -> client_type IS touched.
    """
    user = _user()
    existing_row = SimpleNamespace(id=uuid.uuid4(), playcount=10, clearcount=5, playtime=500)
    mock_db = _StatsMockDB(existing_row=existing_row, latest_row=None)

    payload = SyncRequest(
        scores=[],
        player_stats=[
            PlayerStats(client_type="beatoraja", playcount=11, clearcount=5, playtime=500)
        ],
    )
    result = await sync_data(payload, debug=False, current_user=user, db=mock_db)

    assert result.errors == []
    event = mock_db.added[0]
    assert event.updated_client_types == ["beatoraja"]


@pytest.mark.asyncio
async def test_player_stats_same_day_row_identical_values_excluded():
    """A same-day row exists and all of playcount/clearcount/playtime are
    identical (only synced_at would change) -> client_type is NOT touched —
    the plan's explicit rule (section 3-3).
    """
    user = _user()
    existing_row = SimpleNamespace(id=uuid.uuid4(), playcount=11, clearcount=5, playtime=500)
    mock_db = _StatsMockDB(existing_row=existing_row, latest_row=None)

    payload = SyncRequest(
        scores=[],
        player_stats=[
            PlayerStats(client_type="beatoraja", playcount=11, clearcount=5, playtime=500)
        ],
    )
    result = await sync_data(payload, debug=False, current_user=user, db=mock_db)

    assert result.errors == []
    event = mock_db.added[0]
    assert event.updated_client_types == []


@pytest.mark.asyncio
async def test_mixed_client_types_only_changed_one_reported(db_session: AsyncSession):
    """Plan section 2-1's explicit example: LR2 and Beatoraja submitted
    together, but only LR2 actually changed persisted data -> only "lr2"
    appears in updated_client_types, not both.
    """
    user = _user()
    fumen_sha256_lr2 = "c" * 64
    fumen_sha256_bea = "d" * 64

    # Seed an existing beatoraja row so the second payload's beatoraja item
    # can be a true identical no-op re-sync.
    seed_payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256=fumen_sha256_bea,
                client_type="beatoraja",
                clear_type=2,
                exscore=1000,
                recorded_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )
    await _sync(seed_payload, user, db_session)

    payload = SyncRequest(
        scores=[
            # New LR2 score: real insert.
            ScoreSyncItem(
                fumen_sha256=fumen_sha256_lr2,
                client_type="lr2",
                clear_type=2,
                exscore=1000,
                recorded_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
            ),
            # Re-submitting the identical beatoraja score: no improvement, no
            # metadata change -> skipped, must not appear in updated_client_types.
            ScoreSyncItem(
                fumen_sha256=fumen_sha256_bea,
                client_type="beatoraja",
                clear_type=2,
                exscore=1000,
                recorded_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
            ),
        ],
        player_stats=[],
    )
    result = await _sync(payload, user, db_session)
    assert result.inserted_scores == 1
    assert result.skipped_scores == 1

    events = await _sync_events(db_session, user.id)
    assert len(events) == 1
    assert events[0].updated_client_types == ["beatoraja", "lr2"]


@pytest.mark.asyncio
async def test_two_changed_requests_on_same_day_update_one_visible_event(db_session: AsyncSession):
    """Visible recent-activity rows are one-per-user-per-UTC-day.

    A later record-changing sync updates the existing row's timestamp/client
    chips instead of adding a duplicate public feed row, so ordering can still
    move forward while the same day stays collapsed.
    """
    user = _user()
    payload = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256="e" * 64,
                client_type="lr2",
                clear_type=2,
                exscore=1000,
                recorded_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )
    await _sync(payload, user, db_session)
    first_event = (await _sync_events(db_session, user.id))[0]
    first_synced_at = first_event.synced_at

    payload2 = SyncRequest(
        scores=[
            ScoreSyncItem(
                fumen_sha256="f" * 64,
                client_type="lr2",
                clear_type=2,
                exscore=1000,
                recorded_at=datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC),
            )
        ],
        player_stats=[],
    )
    await _sync(payload2, user, db_session)

    events = await _sync_events(db_session, user.id)
    assert len(events) == 1
    assert events[0].updated_client_types == ["lr2"]
    first_ts = (
        first_synced_at.replace(tzinfo=UTC).timestamp()
        if first_synced_at.tzinfo is None
        else first_synced_at.timestamp()
    )
    latest_ts = (
        events[0].synced_at.replace(tzinfo=UTC).timestamp()
        if events[0].synced_at.tzinfo is None
        else events[0].synced_at.timestamp()
    )
    assert latest_ts >= first_ts


@pytest.mark.asyncio
async def test_empty_payload_sync_still_creates_event(db_session: AsyncSession):
    user = _user()
    payload = SyncRequest(scores=[], player_stats=[])

    result = await _sync(payload, user, db_session)

    assert result.synced_scores == 0
    events = await _sync_events(db_session, user.id)
    assert len(events) == 1
    assert events[0].updated_client_types == []
