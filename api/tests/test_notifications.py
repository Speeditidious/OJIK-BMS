"""Tests for notification visibility rules."""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers.notifications import unread_count

pytestmark = pytest.mark.asyncio


async def test_unread_count_excludes_future_notifications() -> None:
    """Unread-count polling must not surface scheduled notifications early."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.created_at = datetime(2026, 5, 1, tzinfo=UTC)

    state_result = MagicMock()
    state_result.scalar_one_or_none.return_value = None
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    db = AsyncMock()
    db.execute.side_effect = [state_result, count_result]

    await unread_count(user, db)

    count_query = db.execute.await_args_list[1].args[0]
    assert "notifications.created_at <= " in str(count_query)


async def test_create_client_update_notification_includes_localized_bodies() -> None:
    """metadata must carry body_en and body_ja for the frontend dialog."""
    from app.services.notifications import create_client_update_notification
    from app.models.client_update import ClientUpdateAnnouncement

    update = MagicMock(spec=ClientUpdateAnnouncement)
    update.is_published = True
    update.channel = "stable"
    update.version = "1.2.3"
    update.title = "테스트 업데이트"
    update.body_markdown = "한국어 본문"
    update.body_markdown_en = "English body"
    update.body_markdown_ja = "日本語本文"
    update.publish_after = None

    # Simulate "no existing notification" so it creates a new one
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute.return_value = existing_result

    notification = await create_client_update_notification(db, update)

    assert notification is not None
    assert notification.metadata_["body_en"] == "English body"
    assert notification.metadata_["body_ja"] == "日本語本文"
