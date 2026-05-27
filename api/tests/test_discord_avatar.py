"""Tests for Discord avatar URL handling."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers.auth import build_discord_avatar_url
from app.routers.users import _resolve_avatar


def test_build_discord_avatar_url_uses_gif_for_animated_hash() -> None:
    """Animated Discord avatar hashes must render as GIF URLs."""
    assert (
        build_discord_avatar_url("1234", "a_deadbeef")
        == "https://cdn.discordapp.com/avatars/1234/a_deadbeef.gif"
    )


def test_build_discord_avatar_url_uses_png_for_static_hash() -> None:
    """Static Discord avatar hashes must render as PNG URLs."""
    assert (
        build_discord_avatar_url("1234", "deadbeef")
        == "https://cdn.discordapp.com/avatars/1234/deadbeef.png"
    )


def test_build_discord_avatar_url_returns_none_without_hash() -> None:
    """A Discord account without an avatar must not keep a stale CDN URL."""
    assert build_discord_avatar_url("1234", None) is None


@pytest.mark.asyncio
async def test_resolve_avatar_prefers_discord_hash_over_stored_url() -> None:
    """Resolved Discord avatars should be built from the current hash when present."""
    user = SimpleNamespace(avatar_url=None, id="user-id")
    oauth = SimpleNamespace(
        provider_account_id="1234",
        discord_avatar_hash="a_current",
        discord_avatar_url="https://cdn.discordapp.com/avatars/1234/stale.png",
    )

    result_stub = MagicMock()
    result_stub.scalar_one_or_none.return_value = oauth
    db = MagicMock()
    db.execute = AsyncMock(return_value=result_stub)

    assert (
        await _resolve_avatar(user, db)
        == "https://cdn.discordapp.com/avatars/1234/a_current.gif"
    )
