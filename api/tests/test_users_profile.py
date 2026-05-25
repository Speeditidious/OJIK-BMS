"""Tests for /users/me profile endpoint."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app


def _make_mock_user(*, is_admin: bool = False) -> SimpleNamespace:
    """Return a minimal user stub matching the fields accessed in get_my_profile."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        username="testuser",
        bio=None,
        is_active=True,
        is_admin=is_admin,
        avatar_url=None,
    )


def _make_mock_db(avatar_url: str | None = None):
    """Return a minimal async DB session stub.

    The GET /users/me handler calls _resolve_avatar which does a DB execute
    to look up an OAuthAccount. We stub that out so the test doesn't need a
    real DB.
    """
    oauth = None
    if avatar_url is not None:
        oauth = SimpleNamespace(discord_avatar_url=avatar_url)

    result_stub = MagicMock()
    result_stub.scalar_one_or_none.return_value = oauth

    db = MagicMock()
    db.execute = AsyncMock(return_value=result_stub)
    return db


@pytest.mark.asyncio
async def test_get_my_profile_includes_is_admin_false() -> None:
    """/users/me must include is_admin=False for a regular user."""
    mock_user = _make_mock_user(is_admin=False)
    mock_db = _make_mock_db()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        assert "is_admin" in data, "Response must include 'is_admin' field"
        assert data["is_admin"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_profile_includes_is_admin_true() -> None:
    """/users/me must include is_admin=True for an admin user."""
    mock_user = _make_mock_user(is_admin=True)
    mock_db = _make_mock_db()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        assert "is_admin" in data, "Response must include 'is_admin' field"
        assert data["is_admin"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_profile_includes_expected_fields() -> None:
    """/users/me must include all required profile fields."""
    mock_user = _make_mock_user(is_admin=False)
    mock_db = _make_mock_db()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        required_fields = {"id", "username", "bio", "is_active", "is_admin", "avatar_url"}
        assert required_fields.issubset(data.keys()), (
            f"Missing fields: {required_fields - data.keys()}"
        )
        assert data["username"] == "testuser"
        assert data["is_active"] is True
    finally:
        app.dependency_overrides.clear()
