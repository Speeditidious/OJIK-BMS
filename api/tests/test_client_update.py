"""Tests for client update endpoints.

Uses mocking to avoid SQLite/JSONB incompatibility in the test engine.
"""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.admin.views import ClientUpdateAnnouncementAdmin
from app.main import app
from app.models.client_update import ClientUpdateAnnouncement

pytestmark = pytest.mark.asyncio

_INGEST_TOKEN = "test-ingest-token"

_VALID_INGEST_PAYLOAD = {
    "version": "1.0.0-beta.2",
    "channel": "stable",
    "target_os": "windows",
    "arch": "x86_64",
    "installer_kind": "nsis",
    "title": "OJIK BMS Client v1.0.0-beta.2",
    "body_markdown": "CI-generated draft.",
    "release_page_url": "https://github.com/Speeditidious/OJIK-BMS/releases/tag/v1.0.0-beta.2",
    "update_url": "https://github.com/Speeditidious/OJIK-BMS/releases/download/v1.0.0-beta.2/ojikbms-client-setup.exe",
    "tauri_signature": "dW50cnVzdGVkIGNvbW1lbnQ6IHRlc3Qgc2lnbmF0dXJlCg==",
    "asset_size_bytes": 12345678,
    "asset_sha256": "a" * 64,
    "mandatory": False,
    "min_supported_version": None,
}


def _make_row(
    version: str = "2.0.0",
    is_published: bool = True,
    tauri_signature: str | None = "sig",
) -> ClientUpdateAnnouncement:
    row = MagicMock(spec=ClientUpdateAnnouncement)
    row.id = uuid.uuid4()
    row.version = version
    row.channel = "stable"
    row.target_os = "windows"
    row.arch = "x86_64"
    row.installer_kind = "nsis"
    row.title = "Test"
    row.body_markdown = "Notes"
    row.body_markdown_en = None
    row.body_markdown_ja = None
    row.release_page_url = None
    row.update_url = "https://github.com/o/r/releases/download/v2/setup.exe"
    row.tauri_signature = tauri_signature
    row.asset_size_bytes = 1234
    row.asset_sha256 = "a" * 64
    row.mandatory = False
    row.min_supported_version = None
    row.is_published = is_published
    row.published_at = datetime.now(UTC)
    row.publish_after = None
    row.created_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    return row


def _fake_db_no_rows() -> MagicMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    return db


def _fake_db_with_rows(rows: list) -> MagicMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    if rows:
        result.scalar_one_or_none.return_value = rows[0]
    else:
        result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    return db


def _ingest_headers(token: str = _INGEST_TOKEN) -> dict:
    return {"X-OJIK-Internal-Token": token}


@pytest.fixture
def patch_token(monkeypatch):
    from app.core import config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "CLIENT_UPDATE_INGEST_TOKEN", _INGEST_TOKEN)


# ---------------------------------------------------------------------------
# sqladmin Client Updates
# ---------------------------------------------------------------------------

class TestClientUpdateAdmin:
    async def test_create_validates_update_url_from_submitted_form_data(self):
        row = _make_row(version="1.0.0-beta.2", is_published=False)
        row.update_url = None

        await ClientUpdateAnnouncementAdmin.on_model_change(
            ClientUpdateAnnouncementAdmin,
            {"update_url": "https://github.com/o/r/releases/download/v1/setup.exe"},
            row,
            True,
            None,
        )

    async def test_publish_sets_default_publish_after_delay(self):
        row = _make_row(version="1.0.0-beta.2", is_published=False)
        row.published_at = None
        row.publish_after = None

        before = datetime.now(UTC)
        with patch("app.admin.views._trigger_revalidate", AsyncMock()):
            await ClientUpdateAnnouncementAdmin.on_model_change(
                ClientUpdateAnnouncementAdmin,
                {"is_published": True},
                row,
                False,
                None,
            )

        assert row.published_at is not None
        assert row.publish_after is not None
        assert row.publish_after >= before + timedelta(minutes=9, seconds=50)


# ---------------------------------------------------------------------------
# client update notifications
# ---------------------------------------------------------------------------

class TestClientUpdateNotifications:
    async def test_notification_created_at_uses_publish_after_when_scheduled(self):
        row = _make_row(version="1.0.0-beta.2", is_published=True)
        row.publish_after = datetime(2026, 5, 27, 12, 30, tzinfo=UTC)

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result
        db.add = MagicMock()

        from app.services.notifications import create_client_update_notification

        await create_client_update_notification(db, row)

        notification = db.add.call_args.args[0]
        assert notification.created_at == row.publish_after


# ---------------------------------------------------------------------------
# /client/update-policy: supports_auto_install field
# ---------------------------------------------------------------------------

class TestUpdatePolicySupportsAutoInstall:
    async def test_returns_localized_body_fields(self):
        row = _make_row(version="2.0.0", tauri_signature="real-sig")
        row.body_markdown_en = "English notes"
        row.body_markdown_ja = "Japanese notes"

        with (
            patch("app.routers.client.get_latest_visible_update", AsyncMock(return_value=row)),
            patch("app.routers.client.get_visible_release_by_version", AsyncMock(return_value=None)),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/client/update-policy", params={
                    "version": "1.0.0", "target": "windows", "arch": "x86_64",
                    "channel": "stable", "installer_kind": "nsis",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["announcement"]["body_markdown"] == "Notes"
        assert data["announcement"]["body_markdown_en"] == "English notes"
        assert data["announcement"]["body_markdown_ja"] == "Japanese notes"

    async def test_supports_auto_install_false_when_no_signature(self):
        unsigned_row = _make_row(version="2.0.0", tauri_signature=None)

        with (
            patch("app.routers.client.get_latest_visible_update", AsyncMock(return_value=unsigned_row)),
            patch("app.routers.client.get_visible_release_by_version", AsyncMock(return_value=None)),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/client/update-policy", params={
                    "version": "1.0.0", "target": "windows", "arch": "x86_64",
                    "channel": "stable", "installer_kind": "nsis",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["update_available"] is True
        assert data["announcement"]["supports_auto_install"] is False

    async def test_supports_auto_install_true_when_signature_present(self):
        signed_row = _make_row(version="2.0.0", tauri_signature="real-sig")

        with (
            patch("app.routers.client.get_latest_visible_update", AsyncMock(return_value=signed_row)),
            patch("app.routers.client.get_visible_release_by_version", AsyncMock(return_value=None)),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/client/update-policy", params={
                    "version": "1.0.0", "target": "windows", "arch": "x86_64",
                    "channel": "stable", "installer_kind": "nsis",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["update_available"] is True
        assert data["announcement"]["supports_auto_install"] is True

    async def test_returns_current_version_size_for_delta_display(self):
        update_row = _make_row(version="2.0.0", tauri_signature="real-sig")
        update_row.asset_size_bytes = 7_000_000
        current_row = _make_row(version="1.0.0", tauri_signature="real-sig")
        current_row.asset_size_bytes = 6_900_000

        with (
            patch("app.routers.client.get_latest_visible_update", AsyncMock(return_value=update_row)),
            patch("app.routers.client.get_visible_release_by_version", AsyncMock(return_value=current_row)),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/client/update-policy", params={
                    "version": "1.0.0", "target": "windows", "arch": "x86_64",
                    "channel": "stable", "installer_kind": "nsis",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["announcement"]["asset_size_bytes"] == 7_000_000
        assert data["announcement"]["current_asset_size_bytes"] == 6_900_000


# ---------------------------------------------------------------------------
# /client/tauri-update/*: 204 for unsigned, 200 for signed
# ---------------------------------------------------------------------------

class TestTauriUpdateEndpoint:
    async def test_returns_204_for_unsigned_update(self):
        unsigned_row = _make_row(version="2.0.0", tauri_signature=None)

        with patch("app.routers.client.get_latest_visible_update", AsyncMock(return_value=unsigned_row)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/client/tauri-update/windows/x86_64/1.0.0")

        assert resp.status_code == 204

    async def test_returns_signed_metadata(self):
        signed_row = _make_row(version="2.0.0", tauri_signature="real-sig")

        with patch("app.routers.client.get_latest_visible_update", AsyncMock(return_value=signed_row)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/client/tauri-update/windows/x86_64/1.0.0")

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "2.0.0"
        assert data["signature"] == "real-sig"
        assert "url" in data

    async def test_returns_204_when_no_update(self):
        with patch("app.routers.client.get_latest_visible_update", AsyncMock(return_value=None)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/client/tauri-update/windows/x86_64/99.0.0")

        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# /internal/client-updates/from-release
# ---------------------------------------------------------------------------

class TestIngestEndpoint:
    async def test_missing_token_returns_404(self, patch_token):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/internal/client-updates/from-release", json=_VALID_INGEST_PAYLOAD)
        assert resp.status_code == 404

    async def test_wrong_token_returns_404(self, patch_token):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/internal/client-updates/from-release",
                json=_VALID_INGEST_PAYLOAD,
                headers=_ingest_headers("wrong-token"),
            )
        assert resp.status_code == 404

    async def test_valid_payload_creates_unpublished_row(self, patch_token):
        created_row = _make_row(version="1.0.0-beta.2", is_published=False)

        db = AsyncMock()
        db.add = MagicMock()  # synchronous in SQLAlchemy
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        with patch("app.routers.internal_client_updates.AsyncSessionLocal") as mock_session_cls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = db
            ctx.__aexit__.return_value = False
            mock_session_cls.return_value = ctx

            async def fake_refresh(row):
                row.id = created_row.id
                row.version = row.version or "1.0.0-beta.2"
                row.is_published = False

            db.refresh = fake_refresh

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(
                    "/internal/client-updates/from-release",
                    json=_VALID_INGEST_PAYLOAD,
                    headers=_ingest_headers(),
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_published"] is False
        assert data["created"] is True

    async def test_resend_for_published_row_returns_409(self, patch_token):
        published_row = _make_row(version="1.0.0-beta.2", is_published=True)

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = published_row
        db.execute.return_value = result

        with patch("app.routers.internal_client_updates.AsyncSessionLocal") as mock_session_cls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = db
            ctx.__aexit__.return_value = False
            mock_session_cls.return_value = ctx

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(
                    "/internal/client-updates/from-release",
                    json=_VALID_INGEST_PAYLOAD,
                    headers=_ingest_headers(),
                )

        assert resp.status_code == 409

    async def test_resend_updates_unpublished_row(self, patch_token):
        existing_row = _make_row(version="1.0.0-beta.2", is_published=False)
        existing_row.title = "Old title"

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing_row
        db.execute.return_value = result

        with patch("app.routers.internal_client_updates.AsyncSessionLocal") as mock_session_cls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = db
            ctx.__aexit__.return_value = False
            mock_session_cls.return_value = ctx

            updated = {**_VALID_INGEST_PAYLOAD, "title": "Updated title"}
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(
                    "/internal/client-updates/from-release",
                    json=updated,
                    headers=_ingest_headers(),
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] is False

    async def test_resend_without_localized_bodies_preserves_existing_translations(self, patch_token):
        existing_row = _make_row(version="1.0.0-beta.2", is_published=False)
        existing_row.body_markdown_en = "Existing English notes"
        existing_row.body_markdown_ja = "Existing Japanese notes"

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing_row
        db.execute.return_value = result

        with patch("app.routers.internal_client_updates.AsyncSessionLocal") as mock_session_cls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = db
            ctx.__aexit__.return_value = False
            mock_session_cls.return_value = ctx

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(
                    "/internal/client-updates/from-release",
                    json=_VALID_INGEST_PAYLOAD,
                    headers=_ingest_headers(),
                )

        assert resp.status_code == 200
        assert existing_row.body_markdown_en == "Existing English notes"
        assert existing_row.body_markdown_ja == "Existing Japanese notes"

    async def test_invalid_update_url_tag_rejected(self, patch_token):
        bad = {**_VALID_INGEST_PAYLOAD, "update_url": "https://github.com/o/r/releases/tag/v1"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/internal/client-updates/from-release",
                json=bad,
                headers=_ingest_headers(),
            )
        assert resp.status_code == 422

    async def test_http_update_url_rejected(self, patch_token):
        bad = {**_VALID_INGEST_PAYLOAD, "update_url": "http://example.com/setup.exe"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/internal/client-updates/from-release",
                json=bad,
                headers=_ingest_headers(),
            )
        assert resp.status_code == 422

    async def test_invalid_sha256_rejected(self, patch_token):
        bad = {**_VALID_INGEST_PAYLOAD, "asset_sha256": "not-a-sha256"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/internal/client-updates/from-release",
                json=bad,
                headers=_ingest_headers(),
            )
        assert resp.status_code == 422

    async def test_empty_signature_rejected(self, patch_token):
        bad = {**_VALID_INGEST_PAYLOAD, "tauri_signature": "   "}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/internal/client-updates/from-release",
                json=bad,
                headers=_ingest_headers(),
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def _async_gen(value):
    yield value
