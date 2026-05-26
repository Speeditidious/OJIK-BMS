"""Tests for OAuth username fallback behavior."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers.auth import _generate_unique_username


def _username_lookup_result(username: str, existing: set[str]) -> MagicMock:
    """Return a scalar result stub for the given username lookup."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = (
        SimpleNamespace(username=username) if username in existing else None
    )
    return result


@pytest.mark.asyncio
async def test_generate_unique_username_appends_number_when_taken() -> None:
    """New OAuth users get a numbered fallback when the provider username exists."""
    existing = {"RED", "RED2"}

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=lambda statement: _username_lookup_result(
            statement.whereclause.right.value,
            existing,
        )
    )

    assert await _generate_unique_username(db, "RED") == "RED3"


@pytest.mark.asyncio
async def test_generate_unique_username_truncates_base_before_number_suffix() -> None:
    """Fallback usernames must stay within the users.username 64-character limit."""
    base = "a" * 64
    existing = {base}

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=lambda statement: _username_lookup_result(
            statement.whereclause.right.value,
            existing,
        )
    )

    assert await _generate_unique_username(db, base) == f"{'a' * 63}2"
