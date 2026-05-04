"""Tests for the metadata-only sync path preserving synced_at.

Tests 1 & 2 use a fully mocked DB to avoid SQLite/JSONB incompatibility —
the conftest's in-memory SQLite engine cannot render JSONB columns.
Tests 3 & 4 are pure unit tests for the helper functions.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.sql.dml import Update

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.score import UserScore
from app.routers import sync as sync_module

SYNCED_AT_OLD = datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC)
_ORIG_JUDGMENTS = {"perfect": 100, "great": 50, "good": 10, "bad": 5, "poor": 2}
_NEW_JUDGMENTS = {"perfect": 99, "great": 51, "good": 10, "bad": 5, "poor": 2}


class _FakeNestedTx:
    """Minimal async context-manager stub for db.begin_nested()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _make_mock_db(captured_updates: list):
    """Return a mock session that captures UPDATE statements; all awaitable methods are AsyncMock."""

    async def _execute(stmt, *args, **kwargs):
        if isinstance(stmt, Update):
            captured_updates.append(stmt)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        return result

    db = MagicMock()
    db.execute = _execute
    db.begin_nested.return_value = _FakeNestedTx()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    return db


def _make_best(row_id, judgments=None):
    return {
        "clear_type": 2,
        "exscore": 1000,
        "min_bp": None,
        "max_combo": None,
        "play_count": None,
        "_latest_row_id": row_id,
        "_latest_recorded_at": None,
        "_latest_judgments": judgments,
        "_latest_options": None,
        "_latest_clear_count": None,
    }


@pytest.mark.asyncio
async def test_metadata_only_update_preserves_synced_at():
    """Metadata-only update (judgments differ, score unchanged) must not bump synced_at."""
    row_id = uuid.uuid4()
    fumen_md5 = uuid.uuid4().hex[:32]
    captured_updates: list = []

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_db = _make_mock_db(captured_updates)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch.object(
            sync_module,
            "_fetch_current_bests",
            AsyncMock(return_value={(None, fumen_md5, None, "lr2"): _make_best(row_id, _ORIG_JUDGMENTS)}),
        ):
            with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post(
                        "/sync/",
                        json={
                            "scores": [{
                                "fumen_md5": fumen_md5,
                                "client_type": "lr2",
                                "clear_type": 2,
                                "exscore": 1000,
                                "judgments": _NEW_JUDGMENTS,
                            }],
                            "player_stats": [],
                        },
                    )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata_updated"] == 1
    assert data["inserted_scores"] == 0
    assert data["skipped_scores"] == 0

    # Exactly one UPDATE should have been issued
    assert len(captured_updates) == 1
    from sqlalchemy.dialects import sqlite as sqlite_dialect
    compiled = captured_updates[0].compile(dialect=sqlite_dialect.dialect())
    assert "synced_at" not in compiled.string, (
        "metadata-only UPDATE must not touch synced_at; got: " + compiled.string
    )


@pytest.mark.asyncio
async def test_metadata_only_update_no_diff_skips_without_touching_synced_at():
    """When re-syncing identical data, the row is skipped and no UPDATE is issued."""
    row_id = uuid.uuid4()
    fumen_md5 = uuid.uuid4().hex[:32]
    captured_updates: list = []

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_db = _make_mock_db(captured_updates)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch.object(
            sync_module,
            "_fetch_current_bests",
            AsyncMock(return_value={(None, fumen_md5, None, "lr2"): _make_best(row_id, _ORIG_JUDGMENTS)}),
        ):
            with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post(
                        "/sync/",
                        json={
                            "scores": [{
                                "fumen_md5": fumen_md5,
                                "client_type": "lr2",
                                "clear_type": 2,
                                "exscore": 1000,
                                "judgments": _ORIG_JUDGMENTS,  # identical — no diff
                            }],
                            "player_stats": [],
                        },
                    )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["skipped_scores"] == 1
    assert data["metadata_updated"] == 0
    # No UPDATE should have been issued at all
    assert len(captured_updates) == 0


def test_real_improvement_is_detected_and_triggers_insert_path():
    """_is_improvement returns True only when at least one performance field improves.

    The insert path (not the metadata-only path) always sets synced_at=now,
    so verifying the improvement gate is sufficient to confirm insert-path behaviour.
    """
    from app.routers.sync import ScoreSyncItem, _is_improvement

    existing_best = {
        "clear_type": 2,
        "exscore": 1000,
        "min_bp": None,
        "max_combo": None,
        "play_count": None,
    }
    improved = ScoreSyncItem(fumen_md5="a" * 32, client_type="lr2", exscore=1100)
    not_improved = ScoreSyncItem(fumen_md5="a" * 32, client_type="lr2", exscore=1000)

    assert _is_improvement(improved, 1100, existing_best) is True
    assert _is_improvement(not_improved, 1000, existing_best) is False


def test_same_day_merge_recorded_at_takes_later_timestamp_and_synced_at_not_in_merge_dict():
    """_merge_into_existing takes the later recorded_at and per-field best values.

    Crucially, synced_at is NOT part of the returned dict — the caller adds synced_at=now
    explicitly, ensuring same-day merge always bumps synced_at independently of this fix.
    """
    from app.routers.sync import ScoreSyncItem, _merge_into_existing

    recorded_at_early = datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC)
    recorded_at_late = datetime(2026, 5, 3, 22, 0, 0, tzinfo=UTC)

    existing = UserScore(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        client_type="beatoraja",
        fumen_sha256="b" * 64,
        clear_type=2,
        exscore=1000,
        rate=50.0,
        rank="B",
        min_bp=10,
        max_combo=100,
        play_count=5,
        clear_count=3,
        recorded_at=recorded_at_early,
        judgments={"epg": 50},
        options=None,
        scorehash=None,
    )
    item = ScoreSyncItem(
        fumen_sha256="b" * 64,
        client_type="beatoraja",
        clear_type=2,
        exscore=1100,
        min_bp=8,
        max_combo=110,
        play_count=6,
        clear_count=4,
        recorded_at=recorded_at_late,
        judgments={"epg": 55},
    )

    merged = _merge_into_existing(existing, item, new_exscore=1100, new_rate=55.0, new_rank="A")

    assert merged["recorded_at"] == recorded_at_late
    assert merged["exscore"] == 1100
    assert merged["min_bp"] == 8
    assert merged["max_combo"] == 110
    assert merged["play_count"] == 6
    assert merged["judgments"] == {"epg": 55}
    # synced_at is added by the caller (`.values(**merged, synced_at=now)`), not by this helper
    assert "synced_at" not in merged
