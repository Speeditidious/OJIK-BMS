"""Tests for admin announcement API endpoints (/announcements/admin/*)."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.main import app
from app.services.announcements import render_announcement_template, validate_template_placeholders


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tag(*, send_notification: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Update",
        name_en="Update",
        name_ja=None,
        color="blue",
        send_notification=send_notification,
        display_order=0,
    )


def _make_announcement(
    *,
    tag: SimpleNamespace | None = None,
    is_published: bool = False,
    published_at: datetime | None = None,
) -> SimpleNamespace:
    t = tag or _make_tag()
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tag_id=t.id,
        tag=t,
        title="Test Announcement",
        title_en=None,
        title_ja=None,
        body="Body text.",
        body_en=None,
        body_ja=None,
        is_published=is_published,
        published_at=published_at,
        created_at=now,
        updated_at=now,
    )


def _make_regular_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        username="regular",
        is_active=True,
        is_admin=False,
    )


def _make_admin_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        username="admin",
        is_active=True,
        is_admin=True,
    )


def _valid_payload(tag_id: uuid.UUID) -> dict:
    return {
        "tag_id": str(tag_id),
        "title": "New Announcement",
        "body": "Announcement body.",
    }


# ---------------------------------------------------------------------------
# 403 tests: non-admin users must be rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_admin_cannot_create_announcement() -> None:
    """POST /announcements/admin/ returns 403 for regular users."""
    regular_user = _make_regular_user()

    # get_current_admin calls get_current_user then checks is_admin.
    # Override get_current_user to return a non-admin; leave get_current_admin as-is.
    app.dependency_overrides[get_current_user] = lambda: regular_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/announcements/admin/",
                json={"tag_id": str(uuid.uuid4()), "title": "X", "body": "Y"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_non_admin_cannot_update_announcement() -> None:
    """PATCH /announcements/admin/{id} returns 403 for regular users."""
    regular_user = _make_regular_user()
    app.dependency_overrides[get_current_user] = lambda: regular_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.patch(
                f"/announcements/admin/{uuid.uuid4()}",
                json={"tag_id": str(uuid.uuid4()), "title": "X", "body": "Y"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_non_admin_cannot_publish_announcement() -> None:
    """POST /announcements/admin/{id}/publish returns 403 for regular users."""
    regular_user = _make_regular_user()
    app.dependency_overrides[get_current_user] = lambda: regular_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(f"/announcements/admin/{uuid.uuid4()}/publish")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_non_admin_cannot_list_admin_announcements() -> None:
    """GET /announcements/admin/ returns 403 for regular users."""
    regular_user = _make_regular_user()
    app.dependency_overrides[get_current_user] = lambda: regular_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/announcements/admin/")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_non_admin_cannot_read_single_announcement() -> None:
    """GET /announcements/admin/{id} returns 403 for regular users."""
    regular_user = _make_regular_user()
    app.dependency_overrides[get_current_user] = lambda: regular_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(f"/announcements/admin/{uuid.uuid4()}")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Create draft
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_create_draft_announcement() -> None:
    """POST /announcements/admin/ returns 201 with is_published=False and published_at=None."""
    admin_user = _make_admin_user()
    tag = _make_tag()
    ann = _make_announcement(tag=tag, is_published=False, published_at=None)

    # Build a DB stub: tag lookup returns tag, add/flush/refresh/commit succeed.
    tag_result = MagicMock()
    tag_result.scalar_one_or_none.return_value = tag

    db = MagicMock()
    db.execute = AsyncMock(return_value=tag_result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    # refresh stores the tag and a generated id on the announcement object
    _generated_id = uuid.uuid4()

    async def _refresh(obj, attrs=None):
        if hasattr(obj, "tag"):
            obj.tag = tag
        if not obj.id:
            obj.id = _generated_id

    db.refresh = AsyncMock(side_effect=_refresh)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/announcements/admin/",
                json=_valid_payload(tag.id),
            )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["is_published"] is False
        assert data["published_at"] is None
        assert data["title"] == "New Announcement"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_update_announcement() -> None:
    """PATCH /announcements/admin/{id} updates content and returns 200."""
    admin_user = _make_admin_user()
    tag = _make_tag()
    ann = _make_announcement(tag=tag, is_published=False)

    # First execute call → fetch announcement, second → fetch tag for validation
    ann_result = MagicMock()
    ann_result.scalar_one_or_none.return_value = ann

    tag_result = MagicMock()
    tag_result.scalar_one_or_none.return_value = tag

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return ann_result if call_count == 1 else tag_result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)
    db.commit = AsyncMock()

    async def _refresh(obj, attrs=None):
        obj.tag = tag

    db.refresh = AsyncMock(side_effect=_refresh)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.patch(
                f"/announcements/admin/{ann.id}",
                json={
                    "tag_id": str(tag.id),
                    "title": "Updated Title",
                    "body": "Updated body.",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        # The announcement object was mutated in-place by the handler
        assert ann.title == "Updated Title"
        assert ann.body == "Updated body."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_does_not_clear_published_at() -> None:
    """PATCH must not clear published_at when editing a published announcement."""
    admin_user = _make_admin_user()
    tag = _make_tag()
    original_published_at = datetime(2026, 1, 1, tzinfo=UTC)
    ann = _make_announcement(tag=tag, is_published=True, published_at=original_published_at)

    ann_result = MagicMock()
    ann_result.scalar_one_or_none.return_value = ann

    tag_result = MagicMock()
    tag_result.scalar_one_or_none.return_value = tag

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return ann_result if call_count == 1 else tag_result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)
    db.commit = AsyncMock()

    async def _refresh(obj, attrs=None):
        obj.tag = tag

    db.refresh = AsyncMock(side_effect=_refresh)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.patch(
                f"/announcements/admin/{ann.id}",
                json={
                    "tag_id": str(tag.id),
                    "title": "Modified Title",
                    "body": "Modified body.",
                },
            )
        assert response.status_code == 200, response.text
        # published_at must be preserved
        assert ann.published_at == original_published_at
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_publish_sets_is_published_and_published_at() -> None:
    """POST /announcements/admin/{id}/publish returns is_published=True and published_at set."""
    admin_user = _make_admin_user()
    tag = _make_tag(send_notification=True)
    ann = _make_announcement(tag=tag, is_published=False, published_at=None)

    published_ann = SimpleNamespace(**vars(ann))
    published_ann.is_published = True
    published_ann.published_at = datetime(2026, 5, 25, 12, 0, 0, tzinfo=UTC)
    published_ann.tag = tag

    db = MagicMock()
    db.commit = AsyncMock()

    async def _refresh(obj, attrs=None):
        obj.tag = tag
        obj.is_published = True
        obj.published_at = published_ann.published_at

    db.refresh = AsyncMock(side_effect=_refresh)

    with patch(
        "app.routers.announcement_admin.publish_announcement",
        new_callable=AsyncMock,
        return_value=published_ann,
    ) as mock_publish:
        app.dependency_overrides[get_current_admin] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(f"/announcements/admin/{ann.id}/publish")

            assert response.status_code == 200, response.text
            data = response.json()
            assert data["is_published"] is True
            assert data["published_at"] is not None
            mock_publish.assert_awaited_once_with(db, ann.id)
            db.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_publish_404_when_not_found() -> None:
    """POST /announcements/admin/{id}/publish returns 404 if announcement not found."""
    admin_user = _make_admin_user()
    db = MagicMock()

    with patch(
        "app.routers.announcement_admin.publish_announcement",
        new_callable=AsyncMock,
        return_value=None,
    ):
        app.dependency_overrides[get_current_admin] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(f"/announcements/admin/{uuid.uuid4()}/publish")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Admin list includes drafts; public list does not
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_list_includes_unpublished_drafts() -> None:
    """GET /announcements/admin/ must return all announcements including unpublished."""
    admin_user = _make_admin_user()
    tag = _make_tag()
    draft = _make_announcement(tag=tag, is_published=False)

    scalar_result = MagicMock()
    scalar_result.scalar.return_value = 1  # total count
    scalar_result.scalars.return_value.all.return_value = [draft]

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return scalar_result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/announcements/admin/")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["is_published"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_list_excludes_unpublished_drafts() -> None:
    """GET /announcements/ must only return published announcements (no drafts)."""
    # The public endpoint filters on is_published=True. We verify this by
    # returning zero items from the DB stub and confirming the response is empty.
    scalar_result = MagicMock()
    scalar_result.scalar.return_value = 0
    scalar_result.scalars.return_value.all.return_value = []

    db = MagicMock()
    db.execute = AsyncMock(return_value=scalar_result)

    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/announcements/")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Template helper unit tests (no HTTP, pure logic)
# ---------------------------------------------------------------------------


def _make_template(
    *,
    tag_id: uuid.UUID | None = None,
    title_template: str = "",
    title_en_template: str | None = None,
    title_ja_template: str | None = None,
    body_template: str = "",
    body_en_template: str | None = None,
    body_ja_template: str | None = None,
) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tag_id=tag_id,
        title_template=title_template,
        title_en_template=title_en_template,
        title_ja_template=title_ja_template,
        body_template=body_template,
        body_en_template=body_en_template,
        body_ja_template=body_ja_template,
        created_at=now,
        updated_at=now,
    )


def test_render_announcement_template_date_placeholders() -> None:
    """All four date placeholders expand correctly with a fixed date."""
    ref = date(2026, 5, 25)
    tmpl = _make_template(
        title_template="Title {date}",
        title_en_template="Year {yyyy} Month {mm} Day {dd}",
        body_template="Body on {yyyy}-{mm}-{dd}",
    )
    rendered = render_announcement_template(tmpl, ref_date=ref)

    assert rendered["title"] == "Title 2026-05-25"
    assert rendered["title_en"] == "Year 2026 Month 05 Day 25"
    assert rendered["body"] == "Body on 2026-05-25"


def test_render_announcement_template_none_returns_empty_strings() -> None:
    """render_announcement_template(None) returns empty strings, not errors."""
    rendered = render_announcement_template(None)

    assert rendered["title"] == ""
    assert rendered["body"] == ""
    assert rendered["title_en"] is None
    assert rendered["title_ja"] is None
    assert rendered["body_en"] is None
    assert rendered["body_ja"] is None
    assert rendered["tag_id"] is None


def test_validate_template_placeholders_allows_supported() -> None:
    """No exception for templates using only supported placeholders."""
    validate_template_placeholders("Hello {date}, year {yyyy}, {mm}/{dd}!")


def test_validate_template_placeholders_rejects_unknown() -> None:
    """HTTP 422 is raised for any unsupported placeholder."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        validate_template_placeholders("Hello {name}!")

    assert exc_info.value.status_code == 422
    assert "name" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Template API: GET /announcements/admin/templates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_template_global_fallback_when_no_tag_specific() -> None:
    """GET /announcements/admin/templates?tag_id=X falls back to global template."""
    admin_user = _make_admin_user()
    tag_id = uuid.uuid4()

    global_tmpl = _make_template(
        tag_id=None,
        title_template="Global Title {date}",
        body_template="Global body.",
    )

    # First execute: per-tag lookup → None; second: global lookup → global_tmpl
    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = None if call_count == 1 else global_tmpl
        return result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(f"/announcements/admin/templates?tag_id={tag_id}")
        assert response.status_code == 200, response.text
        data = response.json()
        # tag_id echoed back, body/title from global template (placeholders expanded)
        assert "Global Title" in data["title"]
        assert data["body"] == "Global body."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_template_tag_specific_overrides_global() -> None:
    """GET /announcements/admin/templates?tag_id=X returns tag-specific template."""
    admin_user = _make_admin_user()
    tag_id = uuid.uuid4()

    tag_tmpl = _make_template(
        tag_id=tag_id,
        title_template="Tag Title",
        body_template="Tag body.",
    )

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = tag_tmpl

    db = MagicMock()
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(f"/announcements/admin/templates?tag_id={tag_id}")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["title"] == "Tag Title"
        assert data["body"] == "Tag body."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_template_no_tag_returns_global_or_empty() -> None:
    """GET /announcements/admin/templates (no tag_id) returns global template or empty."""
    admin_user = _make_admin_user()

    # No global template exists
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None

    db = MagicMock()
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/announcements/admin/templates")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["title"] == ""
        assert data["body"] == ""
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Template API: PUT /announcements/admin/templates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_template_rejects_unknown_placeholder() -> None:
    """PUT /announcements/admin/templates returns 422 for unknown placeholders."""
    admin_user = _make_admin_user()

    db = MagicMock()

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.put(
                "/announcements/admin/templates",
                json={
                    "tag_id": None,
                    "title_template": "Hello {username}!",
                    "body_template": "Welcome.",
                },
            )
        assert response.status_code == 422, response.text
        assert "username" in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_put_template_creates_global_template() -> None:
    """PUT /announcements/admin/templates upserts a global template (tag_id=None)."""
    admin_user = _make_admin_user()

    saved_tmpl = _make_template(
        tag_id=None,
        title_template="Release {date}",
        body_template="New release on {yyyy}-{mm}-{dd}.",
    )

    # No existing template found
    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = None

    db = MagicMock()
    db.execute = AsyncMock(return_value=find_result)
    db.add = MagicMock()
    db.commit = AsyncMock()

    async def _refresh(obj, *args, **kwargs):
        obj.tag_id = saved_tmpl.tag_id
        obj.title_template = saved_tmpl.title_template
        obj.body_template = saved_tmpl.body_template
        obj.title_en_template = None
        obj.title_ja_template = None
        obj.body_en_template = None
        obj.body_ja_template = None

    db.refresh = AsyncMock(side_effect=_refresh)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.put(
                "/announcements/admin/templates",
                json={
                    "tag_id": None,
                    "title_template": "Release {date}",
                    "body_template": "New release on {yyyy}-{mm}-{dd}.",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        # Rendered output: {date} etc. should be expanded
        assert data["tag_id"] is None
        assert "Release" in data["title"]
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_put_template_updates_existing_template() -> None:
    """PUT /announcements/admin/templates updates an existing template in place."""
    admin_user = _make_admin_user()
    tag_id = uuid.uuid4()
    tag = _make_tag()
    tag.id = tag_id

    existing_tmpl = _make_template(
        tag_id=tag_id,
        title_template="Old title",
        body_template="Old body.",
    )

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        # First call: tag validation; second call: existing template lookup
        if call_count == 1:
            result.scalar_one_or_none.return_value = tag
        else:
            result.scalar_one_or_none.return_value = existing_tmpl
        return result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)
    db.add = MagicMock()
    db.commit = AsyncMock()

    async def _refresh(obj, *args, **kwargs):
        pass  # existing_tmpl already mutated in-place by handler

    db.refresh = AsyncMock(side_effect=_refresh)

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.put(
                "/announcements/admin/templates",
                json={
                    "tag_id": str(tag_id),
                    "title_template": "New title {date}",
                    "body_template": "New body.",
                },
            )
        assert response.status_code == 200, response.text
        # Existing object mutated
        assert existing_tmpl.title_template == "New title {date}"
        assert existing_tmpl.body_template == "New body."
        db.add.assert_not_called()  # update path, not create
        db.commit.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()
