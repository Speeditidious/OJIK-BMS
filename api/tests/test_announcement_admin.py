"""Tests for announcement admin configuration."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.admin.views import AnnouncementAdmin
from app.models.announcement import Announcement, AnnouncementTag


def _contains_identity(items, target) -> bool:
    return any(item is target for item in items)


def test_announcement_admin_form_does_not_accept_system_timestamps():
    form_fields = set(AnnouncementAdmin.form_columns)

    assert Announcement.created_at not in form_fields
    assert Announcement.updated_at not in form_fields


def test_announcement_admin_has_publish_action():
    assert callable(getattr(AnnouncementAdmin, "publish_announcements", None))


def test_announcement_admin_uses_tag_relationship_for_selection():
    assert _contains_identity(AnnouncementAdmin.column_list, Announcement.tag)
    assert not _contains_identity(AnnouncementAdmin.column_list, Announcement.tag_id)
    assert _contains_identity(AnnouncementAdmin.form_columns, Announcement.tag)
    assert not _contains_identity(AnnouncementAdmin.form_columns, Announcement.tag_id)


def test_announcement_tag_displays_name_in_admin_choices():
    tag = AnnouncementTag(name="Update", color="blue", send_notification=True, display_order=10)

    assert str(tag) == "Update"


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
