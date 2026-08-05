"""Tests for `GET /activity/recent` (Task 6).

Following the established convention in `test_activity_ranking_service.py` and
`test_sync_activity_events.py`: the shared `conftest.py` `client`/`db_session`
fixtures build the *entire* real schema via `Base.metadata.create_all`, which
fails under SQLite because several unrelated tables use Postgres-only JSONB
columns and `server_default` expressions (verified directly: `CREATE TABLE
difficulty_tables` errors with `Compiler ... can't render element of type
JSONB`). This file therefore uses its own minimal-schema SQLite engine
covering only `users` and `user_sync_events`, and drives the router through a
real ASGI `AsyncClient` (matching `test_fumen_keymode_sync.py`'s HTTP-level
pattern) with `get_db` overridden to the minimal-schema session.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app
from app.routers import activity as activity_router
from app.models.score import UserSyncEvent
from app.models.user import User

pytestmark = pytest.mark.asyncio


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
            CREATE TABLE user_sync_events (
                id CHAR(32) PRIMARY KEY,
                user_id CHAR(32) NOT NULL,
                synced_at DATETIME NOT NULL,
                updated_client_types JSON NOT NULL
            )
            """,
        ):
            await conn.execute(sa.text(ddl))

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
def _disable_response_cache(monkeypatch):
    """Neutralize the Redis response cache so tests hit the DB deterministically.

    `/activity/recent` caches per `(page_size, cursor)`, so several tests here
    would otherwise share the key `activity:recent:10:` and see each other's
    responses whenever a real Redis happens to be reachable. The cache's
    fail-open behavior is covered separately in `test_activity_recent_cache.py`.
    """
    monkeypatch.setattr(activity_router, "_cache_get", lambda key: _noop_get())
    monkeypatch.setattr(activity_router, "_cache_set", lambda key, payload: _noop_set())


async def _noop_get():
    return None


async def _noop_set():
    return None


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _make_user(db_session: AsyncSession, username: str, *, is_active: bool = True) -> User:
    user = User(
        id=uuid.uuid4(),
        username=username,
        avatar_url=f"https://example.com/{username}.png",
        is_active=is_active,
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _add_event(
    db_session: AsyncSession,
    user: User,
    synced_at: datetime,
    updated_client_types: list[str],
) -> UserSyncEvent:
    event = UserSyncEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        synced_at=synced_at,
        updated_client_types=updated_client_types,
    )
    db_session.add(event)
    return event


async def test_events_older_than_30_days_excluded(client, db_session):
    user = await _make_user(db_session, "alice")
    old = _now() - timedelta(days=31)
    recent = _now() - timedelta(days=1)
    _add_event(db_session, user, old, ["lr2"])
    _add_event(db_session, user, recent, ["lr2"])
    await db_session.commit()

    resp = await client.get("/activity/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["synced_at"].startswith(recent.isoformat()[:10])
    assert body["window_days"] == 30


async def test_events_with_empty_updated_client_types_excluded(client, db_session):
    user = await _make_user(db_session, "bob")
    _add_event(db_session, user, _now(), [])
    _add_event(db_session, user, _now() - timedelta(minutes=1), ["beatoraja"])
    await db_session.commit()

    resp = await client.get("/activity/recent")
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["updated_client_types"] == ["beatoraja"]


async def test_only_lr2_changed_shows_lr2_only(client, db_session):
    user = await _make_user(db_session, "carol")
    _add_event(db_session, user, _now(), ["lr2"])
    await db_session.commit()

    resp = await client.get("/activity/recent")
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["updated_client_types"] == ["lr2"]
    assert item["username"] == "carol"
    assert item["user_id"] == str(user.id)
    assert item["is_admin"] is False
    assert item["avatar_url"] == "https://example.com/carol.png"


async def test_same_user_multiple_syncs_same_day_are_separate_lines_newest_first(client, db_session):
    user = await _make_user(db_session, "dave")
    base = _now().replace(hour=10, minute=0, second=0, microsecond=0)
    e1 = _add_event(db_session, user, base, ["lr2"])
    e2 = _add_event(db_session, user, base + timedelta(hours=2), ["beatoraja"])
    await db_session.commit()

    resp = await client.get("/activity/recent")
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] == str(e2.id)
    assert body["items"][1]["id"] == str(e1.id)


async def test_pagination_cursor_no_overlap_no_gap(client, db_session):
    user = await _make_user(db_session, "erin")
    base = _now().replace(hour=8, minute=0, second=0, microsecond=0)
    events = []
    for i in range(15):
        ev = _add_event(db_session, user, base + timedelta(minutes=i), ["lr2"])
        events.append(ev)
    await db_session.commit()

    resp1 = await client.get("/activity/recent", params={"page_size": 10})
    body1 = resp1.json()
    assert len(body1["items"]) == 10
    assert body1["has_next_page"] is True
    assert body1["next_cursor"] is not None

    page1_ids = {item["id"] for item in body1["items"]}
    # Newest-first: the 10 most recent of the 15 events.
    expected_page1_ids = {str(e.id) for e in sorted(events, key=lambda e: e.synced_at, reverse=True)[:10]}
    assert page1_ids == expected_page1_ids

    resp2 = await client.get("/activity/recent", params={"page_size": 10, "cursor": body1["next_cursor"]})
    body2 = resp2.json()
    assert len(body2["items"]) == 5
    assert body2["has_next_page"] is False
    assert body2["next_cursor"] is None

    page2_ids = {item["id"] for item in body2["items"]}
    assert page1_ids | page2_ids == {str(e.id) for e in events}
    assert page1_ids.isdisjoint(page2_ids)


async def test_deactivated_user_events_excluded(client, db_session):
    """A deactivated account must be invisible in the public feed."""
    active = await _make_user(db_session, "grace")
    banned = await _make_user(db_session, "mallory", is_active=False)
    _add_event(db_session, active, _now(), ["lr2"])
    _add_event(db_session, banned, _now() - timedelta(minutes=1), ["beatoraja"])
    await db_session.commit()

    resp = await client.get("/activity/recent")
    body = resp.json()
    assert [item["username"] for item in body["items"]] == ["grace"]


async def test_empty_updates_filtered_in_sql_so_has_next_page_is_exact(client, db_session):
    """The empty-`updated_client_types` filter runs in SQL, so `limit` is exact.

    Previously this filter ran in Python over an over-fetched batch, which could
    under-report `has_next_page`. With 10 qualifying events interleaved among 40
    empty ones, page 1 must report exactly 10 items and `has_next_page` false.
    """
    user = await _make_user(db_session, "heidi")
    base = _now().replace(hour=9, minute=0, second=0, microsecond=0)
    qualifying = []
    for i in range(50):
        types = ["lr2"] if i % 5 == 0 else []
        ev = _add_event(db_session, user, base + timedelta(minutes=i), types)
        if types:
            qualifying.append(ev)
    await db_session.commit()
    assert len(qualifying) == 10

    resp = await client.get("/activity/recent", params={"page_size": 10})
    body = resp.json()
    assert len(body["items"]) == 10
    assert body["has_next_page"] is False
    assert body["next_cursor"] is None
    assert {item["id"] for item in body["items"]} == {str(e.id) for e in qualifying}


async def test_unauthenticated_request_returns_200(client, db_session):
    user = await _make_user(db_session, "frank")
    _add_event(db_session, user, _now(), ["lr2"])
    await db_session.commit()

    resp = await client.get("/activity/recent")
    assert resp.status_code == 200
