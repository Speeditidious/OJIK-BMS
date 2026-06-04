"""Tests for derived fumen play popularity maintenance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.models.fumen import (
    Fumen,
    FumenPlayPopularity,
    FumenPopularityDirty,
    FumenPopularityWindow,
)
from app.models.score import UserScore
from app.services.fumen_popularity import (
    mark_fumens_dirty,
    rebuild_popularity_window,
    refresh_dirty_fumen_popularity,
    refresh_popularity_window_for_fumens,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_type, _compiler, **_kw):
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for ddl in (
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
            CREATE TABLE fumen_play_popularity (
                fumen_id CHAR(32) PRIMARY KEY,
                played_user_count INTEGER NOT NULL DEFAULT 0,
                total_play_count INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME
            )
            """,
            """
            CREATE TABLE fumen_popularity_dirty (
                fumen_id CHAR(32) PRIMARY KEY,
                queued_at DATETIME
            )
            """,
            """
            CREATE TABLE fumen_popularity_window (
                window VARCHAR(16) NOT NULL,
                fumen_id CHAR(32) NOT NULL,
                rank INTEGER NOT NULL,
                played_user_count INTEGER NOT NULL DEFAULT 0,
                play_count INTEGER NOT NULL DEFAULT 0,
                computed_at DATETIME,
                PRIMARY KEY (window, fumen_id)
            )
            """,
        ):
            await conn.execute(sa.text(ddl))

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


def _fid() -> uuid.UUID:
    return uuid.uuid4()


async def _add_score(
    db: AsyncSession,
    *,
    fumen_id: uuid.UUID | None,
    user_id: uuid.UUID,
    play_count: int | None,
    client_type: str = "beatoraja",
    synced_at: datetime | None = None,
    sha256: str | None = None,
    md5: str | None = None,
    other_hash: str | None = None,
) -> None:
    db.add(
        UserScore(
            id=uuid.uuid4(),
            user_id=user_id,
            client_type=client_type,
            fumen_id=fumen_id,
            fumen_sha256=sha256,
            fumen_md5=md5,
            fumen_hash_others=other_hash,
            play_count=play_count,
            synced_at=synced_at or datetime.now(UTC),
        )
    )


@pytest.mark.asyncio
async def test_mark_fumens_dirty_is_idempotent(db_session: AsyncSession):
    fumen_id = _fid()
    db_session.add(Fumen(fumen_id=fumen_id, sha256="a" * 64, title="Air"))
    await db_session.flush()

    await mark_fumens_dirty(db_session, [fumen_id, fumen_id, None])
    await mark_fumens_dirty(db_session, [])
    await mark_fumens_dirty(db_session, [fumen_id])
    await db_session.flush()

    count = (
        await db_session.execute(sa.select(sa.func.count()).select_from(FumenPopularityDirty))
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_refresh_dirty_popularity_counts_distinct_users_and_current_plays(db_session: AsyncSession):
    fumen_id = _fid()
    user_a = _fid()
    user_b = _fid()
    db_session.add(Fumen(fumen_id=fumen_id, sha256="b" * 64, title="Air"))
    await db_session.flush()
    await _add_score(db_session, fumen_id=fumen_id, user_id=user_a, play_count=3)
    await _add_score(db_session, fumen_id=fumen_id, user_id=user_a, play_count=5)
    await _add_score(db_session, fumen_id=fumen_id, user_id=user_b, play_count=2)
    await _add_score(db_session, fumen_id=fumen_id, user_id=_fid(), play_count=99, other_hash="course")
    await mark_fumens_dirty(db_session, [fumen_id])
    await db_session.flush()

    processed = await refresh_dirty_fumen_popularity(db_session)

    row = (
        await db_session.execute(
            sa.select(FumenPlayPopularity).where(FumenPlayPopularity.fumen_id == fumen_id)
        )
    ).scalar_one()
    assert processed == 1
    assert row.played_user_count == 2
    assert row.total_play_count == 7
    dirty_count = (
        await db_session.execute(sa.select(sa.func.count()).select_from(FumenPopularityDirty))
    ).scalar_one()
    assert dirty_count == 0
    assert await refresh_dirty_fumen_popularity(db_session) == 0


@pytest.mark.asyncio
async def test_refresh_dirty_popularity_resolves_hash_only_scores(db_session: AsyncSession):
    sha_fumen_id = _fid()
    md5_fumen_id = _fid()
    db_session.add_all(
        [
            Fumen(fumen_id=sha_fumen_id, sha256="c" * 64, title="Sha"),
            Fumen(fumen_id=md5_fumen_id, md5="d" * 32, title="Md5"),
        ]
    )
    await db_session.flush()
    await _add_score(db_session, fumen_id=None, user_id=_fid(), play_count=4, sha256="c" * 64)
    await _add_score(db_session, fumen_id=None, user_id=_fid(), play_count=None, md5="d" * 32)
    await mark_fumens_dirty(db_session, [sha_fumen_id, md5_fumen_id])
    await db_session.flush()

    assert await refresh_dirty_fumen_popularity(db_session) == 2

    rows = {
        row.fumen_id: row
        for row in (
            await db_session.execute(sa.select(FumenPlayPopularity))
        ).scalars()
    }
    assert rows[sha_fumen_id].played_user_count == 1
    assert rows[sha_fumen_id].total_play_count == 4
    assert rows[md5_fumen_id].played_user_count == 1
    assert rows[md5_fumen_id].total_play_count == 0


@pytest.mark.asyncio
async def test_window_refresh_uses_play_count_delta_from_before_window_and_reranks(db_session: AsyncSession):
    first_id = _fid()
    second_id = _fid()
    user = _fid()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Fumen(fumen_id=first_id, sha256="e" * 64, title="First"),
            Fumen(fumen_id=second_id, sha256="f" * 64, title="Second"),
        ]
    )
    await db_session.flush()
    await _add_score(db_session, fumen_id=first_id, user_id=user, play_count=4, synced_at=now - timedelta(days=8))
    await _add_score(db_session, fumen_id=first_id, user_id=user, play_count=6, synced_at=now)
    await _add_score(db_session, fumen_id=second_id, user_id=_fid(), play_count=1, synced_at=now - timedelta(days=8))
    await db_session.flush()

    refreshed = await refresh_popularity_window_for_fumens(db_session, "weekly", [first_id, second_id])

    rows = (
        await db_session.execute(
            sa.select(FumenPopularityWindow).order_by(FumenPopularityWindow.rank)
        )
    ).scalars().all()
    assert refreshed == 2
    assert [(r.fumen_id, r.rank, r.played_user_count, r.play_count) for r in rows] == [
        (first_id, 1, 1, 2)
    ]


@pytest.mark.asyncio
async def test_window_refresh_counts_new_weekly_fumen_from_zero_for_existing_user(db_session: AsyncSession):
    old_id = _fid()
    new_id = _fid()
    user = _fid()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Fumen(fumen_id=old_id, sha256="1" * 64, title="Old"),
            Fumen(fumen_id=new_id, sha256="2" * 64, title="New"),
        ]
    )
    await db_session.flush()
    await _add_score(db_session, fumen_id=old_id, user_id=user, play_count=10, synced_at=now - timedelta(days=8))
    await _add_score(db_session, fumen_id=new_id, user_id=user, play_count=3, synced_at=now)
    await db_session.flush()

    refreshed = await refresh_popularity_window_for_fumens(db_session, "weekly", [new_id])

    rows = (
        await db_session.execute(
            sa.select(FumenPopularityWindow).order_by(FumenPopularityWindow.rank)
        )
    ).scalars().all()
    assert refreshed == 1
    assert [(r.fumen_id, r.rank, r.played_user_count, r.play_count) for r in rows] == [
        (new_id, 1, 1, 3)
    ]


@pytest.mark.asyncio
async def test_window_refresh_ignores_first_sync_baseline_but_counts_later_increase(db_session: AsyncSession):
    fumen_id = _fid()
    other_id = _fid()
    user = _fid()
    now = datetime.now(UTC)
    first_sync_at = now - timedelta(days=2)
    db_session.add_all(
        [
            Fumen(fumen_id=fumen_id, sha256="3" * 64, title="First Sync"),
            Fumen(fumen_id=other_id, sha256="4" * 64, title="Other"),
        ]
    )
    await db_session.flush()
    await _add_score(db_session, fumen_id=other_id, user_id=user, play_count=99, synced_at=first_sync_at)
    await _add_score(db_session, fumen_id=fumen_id, user_id=user, play_count=20, synced_at=first_sync_at)
    await _add_score(db_session, fumen_id=fumen_id, user_id=user, play_count=23, synced_at=now)
    await db_session.flush()

    refreshed = await refresh_popularity_window_for_fumens(db_session, "weekly", [fumen_id, other_id])

    rows = (
        await db_session.execute(
            sa.select(FumenPopularityWindow).order_by(FumenPopularityWindow.rank)
        )
    ).scalars().all()
    assert refreshed == 2
    assert [(r.fumen_id, r.rank, r.played_user_count, r.play_count) for r in rows] == [
        (fumen_id, 1, 1, 3)
    ]


@pytest.mark.asyncio
async def test_window_refresh_treats_initial_sync_window_as_baseline(db_session: AsyncSession):
    fumen_id = _fid()
    first_seen_id = _fid()
    user = _fid()
    now = datetime.now(UTC)
    first_sync_at = now - timedelta(days=20)
    initial_chunk_at = first_sync_at + timedelta(hours=2)
    db_session.add_all(
        [
            Fumen(fumen_id=fumen_id, sha256="5" * 64, title="Chunked Initial Sync"),
            Fumen(fumen_id=first_seen_id, sha256="6" * 64, title="First Seen"),
        ]
    )
    await db_session.flush()
    await _add_score(db_session, fumen_id=first_seen_id, user_id=user, play_count=99, synced_at=first_sync_at)
    await _add_score(db_session, fumen_id=fumen_id, user_id=user, play_count=20, synced_at=initial_chunk_at)
    await _add_score(db_session, fumen_id=fumen_id, user_id=user, play_count=23, synced_at=now)
    await db_session.flush()

    refreshed = await refresh_popularity_window_for_fumens(db_session, "monthly", [fumen_id, first_seen_id])

    rows = (
        await db_session.execute(
            sa.select(FumenPopularityWindow).order_by(FumenPopularityWindow.rank)
        )
    ).scalars().all()
    assert refreshed == 2
    assert [(r.fumen_id, r.rank, r.played_user_count, r.play_count) for r in rows] == [
        (fumen_id, 1, 1, 3)
    ]


@pytest.mark.asyncio
async def test_window_refresh_keeps_client_play_count_timelines_separate(db_session: AsyncSession):
    fumen_id = _fid()
    user = _fid()
    now = datetime.now(UTC)
    db_session.add(Fumen(fumen_id=fumen_id, sha256="7" * 64, title="Mixed Client"))
    await db_session.flush()
    await _add_score(
        db_session,
        fumen_id=fumen_id,
        user_id=user,
        client_type="lr2",
        play_count=11,
        synced_at=now - timedelta(days=28),
    )
    await _add_score(
        db_session,
        fumen_id=fumen_id,
        user_id=user,
        client_type="beatoraja",
        play_count=2,
        synced_at=now - timedelta(days=26),
    )
    await _add_score(
        db_session,
        fumen_id=fumen_id,
        user_id=user,
        client_type="lr2",
        play_count=12,
        synced_at=now - timedelta(days=6),
    )
    await _add_score(
        db_session,
        fumen_id=fumen_id,
        user_id=user,
        client_type="lr2",
        play_count=18,
        synced_at=now,
    )
    await db_session.flush()

    await refresh_popularity_window_for_fumens(db_session, "weekly", [fumen_id])
    weekly = (
        await db_session.execute(
            sa.select(FumenPopularityWindow).where(FumenPopularityWindow.window == "weekly")
        )
    ).scalar_one()
    await refresh_popularity_window_for_fumens(db_session, "monthly", [fumen_id])
    monthly = (
        await db_session.execute(
            sa.select(FumenPopularityWindow).where(FumenPopularityWindow.window == "monthly")
        )
    ).scalar_one()

    assert (weekly.played_user_count, weekly.play_count) == (1, 7)
    assert (monthly.played_user_count, monthly.play_count) == (1, 7)


@pytest.mark.asyncio
async def test_rebuild_popularity_window_replaces_cache_with_window_deltas(db_session: AsyncSession):
    old_id = _fid()
    new_id = _fid()
    db_session.add_all(
        [
            Fumen(fumen_id=old_id, sha256="1" * 64, title="Old"),
            Fumen(fumen_id=new_id, sha256="2" * 64, title="New"),
            FumenPopularityWindow(window="monthly", fumen_id=old_id, rank=1, played_user_count=99, play_count=99),
        ]
    )
    await db_session.flush()
    user = _fid()
    now = datetime.now(UTC)
    await _add_score(db_session, fumen_id=old_id, user_id=user, play_count=4, synced_at=now - timedelta(days=31))
    await _add_score(db_session, fumen_id=new_id, user_id=user, play_count=1, synced_at=now - timedelta(days=31))
    await _add_score(db_session, fumen_id=new_id, user_id=user, play_count=7, synced_at=now)
    await db_session.flush()

    rebuilt = await rebuild_popularity_window(db_session, "monthly")

    rows = (
        await db_session.execute(sa.select(FumenPopularityWindow))
    ).scalars().all()
    assert rebuilt == 1
    assert [(r.window, r.fumen_id, r.rank, r.played_user_count, r.play_count) for r in rows] == [
        ("monthly", new_id, 1, 1, 6)
    ]
