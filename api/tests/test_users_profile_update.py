"""Unit tests for user profile update behavior."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.routers.users import UserUpdateRequest, update_my_profile


@pytest.mark.asyncio
async def test_update_my_profile_rejects_duplicate_username_with_error_code() -> None:
    """Profile updates must reject usernames already used by another account."""
    current_user = SimpleNamespace(
        id=uuid.uuid4(),
        username="current",
        bio=None,
        is_active=True,
        is_admin=False,
        avatar_url=None,
    )
    conflict_user = SimpleNamespace(id=uuid.uuid4(), username="taken")

    conflict_result = MagicMock()
    conflict_result.scalar_one_or_none.return_value = conflict_user

    db = MagicMock()
    db.execute = AsyncMock(return_value=conflict_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await update_my_profile(
            UserUpdateRequest(username="taken"),
            current_user,
            db,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "USERNAME_ALREADY_EXISTS"
    db.commit.assert_not_awaited()
