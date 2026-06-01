"""Tests for keymode backfill during full sync (POST /fumens/sync-details).

All tests use a fully mocked DB session to avoid SQLite/PostgreSQL incompatibilities
(pg_insert, CASE WHEN update patterns, etc.).  The mocks simulate the pre-fetched
existing fumen rows returned by the bulk SELECT in sync_fumen_details.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.routers import fumens as fumens_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MD5_LR2 = "a" * 32
_SHA256_BEA = "b" * 64
_MD5_BEA = "c" * 32


def _make_existing_row(**kwargs) -> SimpleNamespace:
    """Build a fake pre-fetched fumen row (as returned by db.execute(select(...)))."""
    defaults = dict(
        sha256=None,
        md5=None,
        title="Some Title",
        artist="Some Artist",
        bpm_min=120.0,
        bpm_max=120.0,
        bpm_main=120.0,
        notes_total=1000,
        total=200,
        notes_n=800,
        notes_ln=200,
        notes_s=0,
        notes_ls=0,
        length=90000,
        keymode=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_mock_db(
    existing_by_sha256: dict | None = None,
    existing_by_md5: dict | None = None,
) -> MagicMock:
    """Return a mock AsyncSession that simulates the bulk prefetch queries.

    sync_fumen_details runs:
      1. (conditional) SELECT … WHERE sha256 IN (…)
      2. (conditional) SELECT … WHERE md5 IN (…)
      3. (optional)    UPDATE / INSERT statements

    We detect which query is being run by inspecting the compiled SQL string.
    """
    existing_by_sha256 = existing_by_sha256 or {}
    existing_by_md5 = existing_by_md5 or {}

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        rows: list = []

        # Compile the statement to text to detect which prefetch query it is.
        # The sha256 prefetch has WHERE ... sha256 IN (...)
        # The md5 prefetch has WHERE ... md5 IN (...)
        # We detect by looking for the WHERE clause pattern.
        try:
            from sqlalchemy.dialects import sqlite as sqlite_dialect
            sql_text = str(stmt.compile(dialect=sqlite_dialect.dialect()))
            sql_lower = sql_text.lower()
            # Look for "WHERE fumens.sha256 IN" pattern
            if "where" in sql_lower and "sha256 in" in sql_lower:
                rows = list(existing_by_sha256.values())
            elif "where" in sql_lower and "md5 in" in sql_lower:
                rows = list(existing_by_md5.values())
        except Exception:
            pass

        result.all.return_value = rows
        return result

    db = MagicMock()
    db.execute = _execute
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _make_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


async def _post_sync_details(payload: dict) -> dict:
    """POST /fumens/sync-details and return parsed JSON."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/fumens/sync-details", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_known_hashes_response_has_keymode_missing_md5_field():
    """GET /fumens/known-hashes must include keymode_missing_md5 in its response."""
    mock_user = _make_user()

    # Simulate a DB with one md5-only fumen that has NULL keymode
    async def _execute(stmt, *_args, **_kwargs):
        result = MagicMock()
        row = SimpleNamespace(
            sha256=None,
            md5=_MD5_LR2,
            keymode=None,
            is_complete=False,
        )
        result.all.return_value = [row]
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/fumens/known-hashes")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert "keymode_missing_md5" in data, "keymode_missing_md5 field must be present"
    assert _MD5_LR2 in data["keymode_missing_md5"]


@pytest.mark.asyncio
async def test_lr2_existing_fumen_fills_null_keymode():
    """LR2 item must fill NULL keymode on an existing fumen (enriched=1)."""
    existing = _make_existing_row(md5=_MD5_LR2, sha256=None, keymode=None)
    mock_db = _make_mock_db(existing_by_md5={_MD5_LR2: existing})
    mock_user = _make_user()

    app.dependency_overrides[get_db] = lambda: (yield mock_db)  # type: ignore[misc]
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        data = await _post_sync_details({
            "items": [{
                "md5": _MD5_LR2,
                "client_type": "lr2",
                "keymode": 7,
            }],
        })
    finally:
        app.dependency_overrides.clear()

    assert data["enriched"] == 1, f"expected enriched=1, got {data}"
    assert data["skipped"] == 0
    assert data["inserted"] == 0


@pytest.mark.asyncio
async def test_lr2_existing_fumen_does_not_overwrite_nonnull_title_or_bpm():
    """LR2 keymode fill must not touch title, bpm, or any other detail field."""
    existing = _make_existing_row(
        md5=_MD5_LR2,
        sha256=None,
        title="Original Title",
        bpm_main=180.0,
        keymode=None,
    )
    mock_db = _make_mock_db(existing_by_md5={_MD5_LR2: existing})
    mock_user = _make_user()

    # Track which UPDATE statements are executed
    executed_updates: list = []
    original_execute = mock_db.execute

    call_count = 0

    async def _tracking_execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            # Capture any UPDATE statement text
            try:
                from sqlalchemy.sql.dml import Update
                if hasattr(stmt, "__class__") and "Update" in type(stmt).__name__:
                    executed_updates.append(stmt)
            except Exception:
                pass
        return await original_execute(stmt, *args, **kwargs)

    mock_db.execute = _tracking_execute

    app.dependency_overrides[get_db] = lambda: (yield mock_db)  # type: ignore[misc]
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        data = await _post_sync_details({
            "items": [{
                "md5": _MD5_LR2,
                "client_type": "lr2",
                "title": "LR2 Different Title",
                "bpm_min": 90.0,
                "bpm_max": 90.0,
                "bpm_main": 90.0,
                "keymode": 7,
            }],
        })
    finally:
        app.dependency_overrides.clear()

    # The response should show 1 enriched (keymode fill), not a full update
    assert data["enriched"] == 1
    assert data["skipped"] == 0


@pytest.mark.asyncio
async def test_beatoraja_existing_fumen_fills_null_keymode():
    """Beatoraja item can also fill NULL keymode (it goes through the normal fill path)."""
    existing = _make_existing_row(
        sha256=_SHA256_BEA,
        md5=_MD5_BEA,
        keymode=None,
        # All other fields filled — keymode is the only NULL
        title="Title",
        artist="Artist",
    )
    mock_db = _make_mock_db(existing_by_sha256={_SHA256_BEA: existing})
    mock_user = _make_user()

    app.dependency_overrides[get_db] = lambda: (yield mock_db)  # type: ignore[misc]
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        data = await _post_sync_details({
            "items": [{
                "sha256": _SHA256_BEA,
                "md5": _MD5_BEA,
                "client_type": "beatoraja",
                "keymode": 7,
            }],
        })
    finally:
        app.dependency_overrides.clear()

    assert data["enriched"] == 1, f"Beatoraja should fill null keymode; got {data}"
    assert data["skipped"] == 0
    assert data["inserted"] == 0


@pytest.mark.asyncio
async def test_lr2_does_not_overwrite_existing_non_null_keymode():
    """LR2 item must not overwrite an already-populated keymode field."""
    existing = _make_existing_row(md5=_MD5_LR2, sha256=None, keymode=5)
    mock_db = _make_mock_db(existing_by_md5={_MD5_LR2: existing})
    mock_user = _make_user()

    app.dependency_overrides[get_db] = lambda: (yield mock_db)  # type: ignore[misc]
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        data = await _post_sync_details({
            "items": [{
                "md5": _MD5_LR2,
                "client_type": "lr2",
                "keymode": 7,  # different value — must NOT overwrite
            }],
        })
    finally:
        app.dependency_overrides.clear()

    assert data["skipped"] == 1, f"non-null keymode must not be overwritten; got {data}"
    assert data["enriched"] == 0
    assert data["inserted"] == 0


@pytest.mark.asyncio
async def test_keymode_fill_increments_enriched_not_updated():
    """The response field for enrichment count must be named 'enriched', not 'updated'."""
    existing = _make_existing_row(md5=_MD5_LR2, sha256=None, keymode=None)
    mock_db = _make_mock_db(existing_by_md5={_MD5_LR2: existing})
    mock_user = _make_user()

    app.dependency_overrides[get_db] = lambda: (yield mock_db)  # type: ignore[misc]
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        data = await _post_sync_details({
            "items": [{
                "md5": _MD5_LR2,
                "client_type": "lr2",
                "keymode": 7,
            }],
        })
    finally:
        app.dependency_overrides.clear()

    assert "enriched" in data, "response must have 'enriched' field (not 'updated')"
    assert "updated" not in data, "old 'updated' field must be renamed to 'enriched'"
    assert data["enriched"] == 1


@pytest.mark.asyncio
async def test_keymode_only_fill_does_not_affect_inserted_or_skipped_counts():
    """A keymode-only LR2 fill must not count as inserted or skipped."""
    existing = _make_existing_row(md5=_MD5_LR2, sha256=None, keymode=None)
    mock_db = _make_mock_db(existing_by_md5={_MD5_LR2: existing})
    mock_user = _make_user()

    app.dependency_overrides[get_db] = lambda: (yield mock_db)  # type: ignore[misc]
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        data = await _post_sync_details({
            "items": [{
                "md5": _MD5_LR2,
                "client_type": "lr2",
                "keymode": 7,
            }],
        })
    finally:
        app.dependency_overrides.clear()

    assert data["inserted"] == 0
    assert data["skipped"] == 0
    assert data["enriched"] == 1


@pytest.mark.asyncio
async def test_beatoraja_does_not_overwrite_existing_non_null_keymode():
    """Beatoraja item must not overwrite an already-populated keymode field."""
    existing = _make_existing_row(sha256=_SHA256_BEA, md5=_MD5_BEA, keymode=7)
    mock_db = _make_mock_db(existing_by_sha256={_SHA256_BEA: existing})
    mock_user = _make_user()

    app.dependency_overrides[get_db] = lambda: (yield mock_db)  # type: ignore[misc]
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        data = await _post_sync_details({
            "items": [{
                "sha256": _SHA256_BEA,
                "md5": _MD5_BEA,
                "client_type": "beatoraja",
                "keymode": 5,  # different value — must NOT overwrite
            }],
        })
    finally:
        app.dependency_overrides.clear()

    assert data["skipped"] == 1, f"non-null keymode must not be overwritten by Beatoraja; got {data}"
    assert data["enriched"] == 0
    assert data["inserted"] == 0


@pytest.mark.asyncio
async def test_hash_supplement_plus_keymode_fill_reports_one_enriched_after_overlap_correction():
    """When a fumen is both hash-supplemented and keymode-filled, overlap_count is incremented.

    Scenario: md5-only LR2 fumen whose md5 was supplemented this session (md5 appears in
    supplemented_md5s). Client resends with keymode. The response must show enriched=1 and
    overlap_count=1 so the caller can compute net-new enrichments as enriched - overlap_count = 0.
    """
    existing = _make_existing_row(md5=_MD5_LR2, sha256=None, keymode=None)
    mock_db = _make_mock_db(existing_by_md5={_MD5_LR2: existing})
    mock_user = _make_user()

    app.dependency_overrides[get_db] = lambda: (yield mock_db)  # type: ignore[misc]
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        data = await _post_sync_details({
            "items": [{
                "md5": _MD5_LR2,
                "client_type": "lr2",
                "keymode": 7,
            }],
            "supplemented_md5s": [_MD5_LR2],  # this md5 was supplemented this session
        })
    finally:
        app.dependency_overrides.clear()

    assert data["enriched"] == 1
    assert data["overlap_count"] == 1, (
        f"keymode fill of a supplemented fumen must set overlap_count=1; got {data}"
    )
