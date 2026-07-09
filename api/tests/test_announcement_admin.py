"""Tests for announcement admin configuration."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.admin.views import AnnouncementAdmin, AnnouncementTemplateAdmin
from app.models.announcement import Announcement, AnnouncementTag, AnnouncementTemplate


def _contains_identity(items, target) -> bool:
    return any(item is target for item in items)


def test_announcement_admin_form_does_not_accept_system_timestamps():
    form_fields = AnnouncementAdmin.form_columns

    assert not _contains_identity(form_fields, Announcement.created_at)
    assert not _contains_identity(form_fields, Announcement.updated_at)


def test_announcement_admin_has_publish_action():
    assert callable(getattr(AnnouncementAdmin, "publish_announcements", None))


def test_announcement_admin_uses_scalar_tag_id_in_form():
    assert _contains_identity(AnnouncementAdmin.column_list, Announcement.tag)
    assert not _contains_identity(AnnouncementAdmin.column_list, Announcement.tag_id)
    assert _contains_identity(AnnouncementAdmin.form_columns, Announcement.tag_id)
    assert not _contains_identity(AnnouncementAdmin.form_columns, Announcement.tag)


def test_announcement_tag_displays_name_in_admin_choices():
    tag = AnnouncementTag(name="Update", color="blue", send_notification=True, display_order=10)

    assert str(tag) == "Update"


def test_announcement_template_admin_is_registered() -> None:
    """AnnouncementTemplateAdmin should be registered in the admin views list."""
    from app.admin import create_admin

    import inspect
    source = inspect.getsource(create_admin)
    assert "AnnouncementTemplateAdmin" in source


def test_announcement_template_admin_excludes_timestamps_from_form() -> None:
    """AnnouncementTemplate admin form must not expose system-managed timestamps."""
    excluded = AnnouncementTemplateAdmin.form_excluded_columns

    assert _contains_identity(excluded, AnnouncementTemplate.created_at)
    assert _contains_identity(excluded, AnnouncementTemplate.updated_at)


def test_announcement_template_admin_column_list_includes_tag_relationship() -> None:
    """Column list should show the tag relationship, not raw tag_id."""
    col_list = AnnouncementTemplateAdmin.column_list

    assert _contains_identity(col_list, AnnouncementTemplate.tag)
    assert _contains_identity(col_list, AnnouncementTemplate.title_template)
    assert _contains_identity(col_list, AnnouncementTemplate.updated_at)
    assert not _contains_identity(col_list, AnnouncementTemplate.tag_id)


@pytest.mark.asyncio
async def test_publishing_from_form_stamps_submitted_published_at():
    row = MagicMock(spec=Announcement)
    row.is_published = False
    row.published_at = None
    data = {"is_published": True, "published_at": None}

    before = datetime.now(UTC)
    await AnnouncementAdmin.on_model_change(AnnouncementAdmin, data, row, False, None)

    assert row.published_at is not None
    assert row.published_at >= before
    assert data["published_at"] == row.published_at


# ---------------------------------------------------------------------------
# Service-level tests for app.services.announcements
# ---------------------------------------------------------------------------


def _make_announcement(
    *,
    is_published: bool = False,
    published_at: datetime | None = None,
    announcement_id=None,
) -> MagicMock:
    """Return a MagicMock that looks like an Announcement row."""
    import uuid

    ann = MagicMock(spec=Announcement)
    ann.id = announcement_id or uuid.uuid4()
    ann.is_published = is_published
    ann.published_at = published_at
    ann.updated_at = None
    ann.tag = MagicMock(spec=AnnouncementTag, send_notification=True)
    return ann


def _make_db_returning(announcement: MagicMock) -> AsyncMock:
    """Build a minimal AsyncSession mock that returns *announcement* from execute."""
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = announcement
    scalar_result.scalars.return_value.all.return_value = [announcement]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=scalar_result)
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_publish_announcement_first_publish_stamps_published_at():
    """publish_announcement sets is_published=True and stamps published_at on first call."""
    ann = _make_announcement(is_published=False, published_at=None)
    db = _make_db_returning(ann)

    now = datetime(2026, 5, 25, 12, 0, 0, tzinfo=UTC)

    with patch(
        "app.services.announcements.create_announcement_notification",
        new_callable=AsyncMock,
    ) as mock_notify:
        from app.services.announcements import publish_announcement

        result = await publish_announcement(db, ann.id, now=now)

    assert result is ann
    assert ann.is_published is True
    assert ann.published_at == now
    assert ann.updated_at == now
    mock_notify.assert_awaited_once_with(db, ann)


@pytest.mark.asyncio
async def test_publish_announcement_repeated_publish_keeps_existing_published_at():
    """publish_announcement does not override published_at if already set."""
    original_published_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    ann = _make_announcement(is_published=True, published_at=original_published_at)
    db = _make_db_returning(ann)

    now = datetime(2026, 5, 25, 12, 0, 0, tzinfo=UTC)

    with patch(
        "app.services.announcements.create_announcement_notification",
        new_callable=AsyncMock,
    ):
        from app.services.announcements import publish_announcement

        result = await publish_announcement(db, ann.id, now=now)

    assert result is ann
    assert ann.published_at == original_published_at  # unchanged


@pytest.mark.asyncio
async def test_publish_announcement_returns_none_when_not_found():
    """publish_announcement returns None if the announcement does not exist."""
    import uuid

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=scalar_result)

    with patch(
        "app.services.announcements.create_announcement_notification",
        new_callable=AsyncMock,
    ) as mock_notify:
        from app.services.announcements import publish_announcement

        result = await publish_announcement(db, uuid.uuid4())

    assert result is None
    mock_notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_announcement_calls_notification_service():
    """publish_announcement always calls create_announcement_notification."""
    ann = _make_announcement(is_published=False, published_at=None)
    db = _make_db_returning(ann)

    with patch(
        "app.services.announcements.create_announcement_notification",
        new_callable=AsyncMock,
    ) as mock_notify:
        from app.services.announcements import publish_announcement

        await publish_announcement(db, ann.id)

    mock_notify.assert_awaited_once_with(db, ann)


@pytest.mark.asyncio
async def test_publish_announcements_calls_notification_for_each():
    """publish_announcements calls create_announcement_notification for each item."""
    import uuid

    ann1 = _make_announcement()
    ann2 = _make_announcement()

    scalar_result = MagicMock()
    scalar_result.scalars.return_value.all.return_value = [ann1, ann2]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=scalar_result)

    with patch(
        "app.services.announcements.create_announcement_notification",
        new_callable=AsyncMock,
    ) as mock_notify:
        from app.services.announcements import publish_announcements

        results = await publish_announcements(db, [ann1.id, ann2.id])

    assert len(results) == 2
    assert mock_notify.await_count == 2


@pytest.mark.asyncio
async def test_publish_announcements_empty_list_returns_empty():
    """publish_announcements with an empty list skips DB calls and returns []."""
    db = AsyncMock()

    with patch(
        "app.services.announcements.create_announcement_notification",
        new_callable=AsyncMock,
    ) as mock_notify:
        from app.services.announcements import publish_announcements

        results = await publish_announcements(db, [])

    assert results == []
    db.execute.assert_not_called()
    mock_notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_announcements_deduplication_is_in_notification_service():
    """Calling publish_announcements twice calls the notification service both times.

    Deduplication lives in create_announcement_notification itself — the service
    does not try to short-circuit it.
    """
    ann = _make_announcement()
    scalar_result = MagicMock()
    scalar_result.scalars.return_value.all.return_value = [ann]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=scalar_result)

    with patch(
        "app.services.announcements.create_announcement_notification",
        new_callable=AsyncMock,
    ) as mock_notify:
        from app.services.announcements import publish_announcements

        await publish_announcements(db, [ann.id])
        await publish_announcements(db, [ann.id])

    # notification function is called for each publish_announcements invocation
    assert mock_notify.await_count == 2
