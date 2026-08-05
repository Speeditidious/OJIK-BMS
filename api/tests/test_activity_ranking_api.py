"""Tests for `GET /activity/ranking` (Task 6).

Same minimal-schema SQLite convention as `test_activity_recent.py` and
`test_activity_ranking_service.py` — the shared `conftest.py` fixture's
`Base.metadata.create_all` fails under SQLite for unrelated Postgres-only
JSONB tables, so this file builds its own `users`, `oauth_accounts`, and
`user_activity_ranking` schema and drives the router over a real ASGI
`AsyncClient`.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.main import app
from app.models.score import UserActivityRanking
from app.models.user import User

pytestmark = pytest.mark.asyncio

WINDOW_END = date(2026, 8, 5)
WINDOW_START = WINDOW_END - timedelta(days=29)


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
            CREATE TABLE oauth_accounts (
                user_id CHAR(32) NOT NULL,
                provider VARCHAR(32) NOT NULL,
                provider_account_id VARCHAR(128) NOT NULL,
                provider_username VARCHAR(128),
                discord_avatar_hash VARCHAR(128),
                discord_avatar_url VARCHAR(512),
                PRIMARY KEY (user_id, provider)
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


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


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


def _add_ranking(db_session, user, metric, rank, value, computed_at=None, range_name="monthly"):
    row = UserActivityRanking(
        range=range_name,
        metric=metric,
        user_id=user.id,
        rank=rank,
        value=value,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        computed_at=computed_at or datetime(2026, 8, 5, 3, 0, 0),
    )
    db_session.add(row)
    return row


async def test_no_snapshot_rows_returns_empty_not_error(client, db_session):
    resp = await client.get("/activity/ranking", params={"metric": "attendance"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["computed_at"] is None
    assert body["window_start"] is None
    assert body["window_end"] is None
    assert body["my_rank"] is None
    assert body["total_count"] == 0
    assert body["page"] == 1


async def test_ranking_ordering_and_pagination_two_pages(client, db_session):
    users = [await _make_user(db_session, f"user{i}") for i in range(15)]
    for i, user in enumerate(users, start=1):
        _add_ranking(db_session, user, "plays", rank=i, value=1000 - i)
    await db_session.commit()

    resp1 = await client.get("/activity/ranking", params={"metric": "plays", "page_size": 10, "page": 1})
    body1 = resp1.json()
    assert [item["rank"] for item in body1["items"]] == list(range(1, 11))
    assert body1["total_count"] == 15
    assert body1["page"] == 1

    resp2 = await client.get(
        "/activity/ranking",
        params={"metric": "plays", "page_size": 10, "page": 2},
    )
    body2 = resp2.json()
    assert [item["rank"] for item in body2["items"]] == list(range(11, 16))
    assert body2["total_count"] == 15
    assert body2["page"] == 2

    assert body1["window_start"] == WINDOW_START.isoformat()
    assert body1["window_end"] == WINDOW_END.isoformat()
    assert body1["computed_at"] is not None
    assert body1["range"] == "monthly"


async def test_weekly_range_is_separate_from_monthly(client, db_session):
    weekly_user = await _make_user(db_session, "weekly_user")
    monthly_user = await _make_user(db_session, "monthly_user")
    _add_ranking(
        db_session,
        weekly_user,
        "attendance",
        rank=1,
        value=7,
        range_name="weekly",
    )
    _add_ranking(
        db_session,
        monthly_user,
        "attendance",
        rank=1,
        value=30,
        range_name="monthly",
    )
    await db_session.commit()

    resp = await client.get("/activity/ranking", params={"range": "weekly", "metric": "attendance"})
    body = resp.json()
    assert body["range"] == "weekly"
    assert [item["username"] for item in body["items"]] == ["weekly_user"]


async def test_logged_in_user_my_rank_out_of_page(client, db_session):
    users = [await _make_user(db_session, f"u{i}") for i in range(15)]
    for i, user in enumerate(users, start=1):
        _add_ranking(db_session, user, "attendance", rank=i, value=30 - i)
    await db_session.commit()

    target_user = users[-1]  # rank 15, not in the first page of 10

    async def override_current_user():
        return target_user

    app.dependency_overrides[get_current_user_optional] = override_current_user
    try:
        resp = await client.get("/activity/ranking", params={"metric": "attendance", "page_size": 10})
    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)

    body = resp.json()
    assert all(item["rank"] != 15 for item in body["items"])
    assert body["my_rank"]["rank"] == 15
    assert body["my_rank"]["value"] == 30 - 15


async def test_logged_in_user_with_no_row_gets_null_my_rank(client, db_session):
    ranked_user = await _make_user(db_session, "ranked")
    unranked_user = await _make_user(db_session, "unranked")
    _add_ranking(db_session, ranked_user, "notes_hit", rank=1, value=500)
    await db_session.commit()

    async def override_current_user():
        return unranked_user

    app.dependency_overrides[get_current_user_optional] = override_current_user
    try:
        resp = await client.get("/activity/ranking", params={"metric": "notes_hit"})
    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)

    assert resp.json()["my_rank"] is None


async def test_unauthenticated_request_gets_null_my_rank_and_200(client, db_session):
    user = await _make_user(db_session, "solo")
    _add_ranking(db_session, user, "plays", rank=1, value=10)
    await db_session.commit()

    resp = await client.get("/activity/ranking", params={"metric": "plays"})
    assert resp.status_code == 200
    assert resp.json()["my_rank"] is None


async def test_invalid_metric_returns_400(client, db_session):
    resp = await client.get("/activity/ranking", params={"metric": "bogus"})
    assert resp.status_code == 400


async def test_invalid_range_returns_400(client, db_session):
    resp = await client.get("/activity/ranking", params={"range": "all_time", "metric": "plays"})
    assert resp.status_code == 400


async def test_deactivated_user_excluded_from_ranking_items(client, db_session):
    """A snapshot row for a since-deactivated user must not appear in the leaderboard."""
    active = await _make_user(db_session, "active_user")
    banned = await _make_user(db_session, "banned_user", is_active=False)
    _add_ranking(db_session, active, "plays", rank=1, value=500)
    _add_ranking(db_session, banned, "plays", rank=2, value=400)
    await db_session.commit()

    resp = await client.get("/activity/ranking", params={"metric": "plays"})
    body = resp.json()
    assert [item["username"] for item in body["items"]] == ["active_user"]
