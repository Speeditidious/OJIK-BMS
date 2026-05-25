"""Tests for /users/me profile endpoint."""
import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_patch_mock_db():
    """Return a DB stub suitable for PATCH /users/me.

    The handler calls db.execute (username uniqueness check), db.commit(),
    and db.refresh(), then _resolve_avatar which calls db.execute again.
    Both execute calls return a stub whose scalar_one_or_none returns None
    (no conflict, no Discord avatar).
    """
    result_stub = MagicMock()
    result_stub.scalar_one_or_none.return_value = None

    db = MagicMock()
    db.execute = AsyncMock(return_value=result_stub)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _make_avatar_mock_db():
    """Return a DB stub suitable for POST /users/me/avatar.

    The handler calls db.commit() and db.refresh() but does NOT call
    _resolve_avatar (it uses current_user.avatar_url directly).
    """
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
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


@pytest.mark.asyncio
async def test_patch_my_profile_includes_is_admin() -> None:
    """PATCH /users/me must include is_admin in its response."""
    mock_user = _make_mock_user(is_admin=True)
    mock_db = _make_patch_mock_db()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.patch("/users/me", json={"bio": "hello"})

        assert response.status_code == 200
        data = response.json()
        assert "is_admin" in data, "PATCH /users/me response must include 'is_admin' field"
        assert data["is_admin"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_avatar_includes_is_admin() -> None:
    """POST /users/me/avatar must include is_admin in its response."""
    mock_user = _make_mock_user(is_admin=False)
    mock_db = _make_avatar_mock_db()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    # Patch filesystem operations so no actual file is written during the test.
    fake_contents = b"\xff\xd8\xff\xe0" + b"\x00" * 16  # minimal JPEG-like bytes
    with (
        patch("app.routers.users.AVATAR_DIR") as mock_dir,
        patch("pathlib.Path.write_bytes"),
    ):
        mock_dir.__truediv__ = lambda self, name: MagicMock(write_bytes=MagicMock())
        mock_dir.mkdir = MagicMock()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.post(
                "/users/me/avatar",
                files={"file": ("avatar.jpg", io.BytesIO(fake_contents), "image/jpeg")},
            )

    assert response.status_code == 200
    data = response.json()
    assert "is_admin" in data, "POST /users/me/avatar response must include 'is_admin' field"
    assert data["is_admin"] is False
    app.dependency_overrides.clear()
