"""Tests for historical clear distribution snapshots via the as_of query parameter.

Strategy: mock the DB session to avoid SQLite/JSONB incompatibility,
following the established pattern in this test suite.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.main import app

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SHA256_A = "a" * 64
_MD5_A = "a" * 32
_SHA256_B = "b" * 64
_MD5_B = "b" * 32
_MD5_LR2 = "c" * 32   # LR2-only fumen: md5 only, sha256=NULL

_TABLE_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()
_FUMEN_ID_A = uuid.uuid4()
_FUMEN_ID_B = uuid.uuid4()
_FUMEN_ID_LR2 = uuid.uuid4()


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fake model stubs
# ---------------------------------------------------------------------------

def _make_table() -> SimpleNamespace:
    return SimpleNamespace(
        id=_TABLE_ID,
        name="Test Table",
        symbol="★",
        level_order=["1", "2"],
        display_level_order=None,
        non_regular_level_order=None,
    )


def _make_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=_USER_ID,
        username="testuser",
        is_active=True,
        is_admin=False,
        first_synced_at=None,
    )


def _make_fumen(fumen_id, sha256, md5, title) -> SimpleNamespace:
    return SimpleNamespace(
        fumen_id=fumen_id,
        sha256=sha256,
        md5=md5,
        title=title,
        artist="",
    )


def _make_score(
    sha256,
    md5,
    clear_type,
    recorded_at,
    synced_at,
    fumen_hash_others=None,
    client_type="lr2",
) -> SimpleNamespace:
    return SimpleNamespace(
        fumen_sha256=sha256,
        fumen_md5=md5,
        fumen_hash_others=fumen_hash_others,
        client_type=client_type,
        clear_type=clear_type,
        exscore=1000,
        rate=80.0,
        rank="A",
        min_bp=10,
        max_combo=200,
        play_count=5,
        options=None,
        recorded_at=recorded_at,
        synced_at=synced_at,
    )


# ---------------------------------------------------------------------------
# Fake DB builder
# ---------------------------------------------------------------------------

def _make_db(fumen_rows, score_rows) -> MagicMock:
    """Build a mock AsyncSession that returns seeded data for execute() calls."""

    table = _make_table()

    # Prepare result objects
    table_result = MagicMock()
    table_result.scalar_one_or_none.return_value = table

    fumen_result = MagicMock()
    fumen_result.all.return_value = fumen_rows

    score_result = MagicMock()
    score_result.all.return_value = score_rows

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[table_result, fumen_result, score_result])
    return db


# ---------------------------------------------------------------------------
# Shared score fixtures
# ---------------------------------------------------------------------------

def _make_all_score_rows():
    """Score rows as they exist in the DB (all time)."""
    return [
        # Fumen A: HARD clear AFTER 2026-05-01
        _make_score(
            sha256=_SHA256_A,
            md5=_MD5_A,
            clear_type=7,  # HARD
            recorded_at=_dt(2026, 5, 10),
            synced_at=_dt(2026, 5, 10),
        ),
        # Fumen B: EASY clear BEFORE 2026-05-01
        _make_score(
            sha256=_SHA256_B,
            md5=_MD5_B,
            clear_type=2,  # EASY
            recorded_at=_dt(2026, 4, 15),
            synced_at=_dt(2026, 4, 15),
        ),
        # LR2-only fumen: EASY before 2026-05-01
        _make_score(
            sha256=None,
            md5=_MD5_LR2,
            clear_type=2,  # EASY
            recorded_at=_dt(2026, 4, 20),
            synced_at=_dt(2026, 4, 20),
        ),
    ]


def _make_historical_score_rows():
    """Score rows visible as of 2026-05-01 (excludes fumen A's HARD clear)."""
    return [
        # Fumen A: no score before 2026-05-01 → NO PLAY
        # Fumen B: EASY clear
        _make_score(
            sha256=_SHA256_B,
            md5=_MD5_B,
            clear_type=2,
            recorded_at=_dt(2026, 4, 15),
            synced_at=_dt(2026, 4, 15),
        ),
        # LR2-only: EASY
        _make_score(
            sha256=None,
            md5=_MD5_LR2,
            clear_type=2,
            recorded_at=_dt(2026, 4, 20),
            synced_at=_dt(2026, 4, 20),
        ),
    ]


def _make_fumen_rows():
    return [
        (_make_fumen(_FUMEN_ID_A, _SHA256_A, _MD5_A, "Song A"), "1"),
        (_make_fumen(_FUMEN_ID_B, _SHA256_B, _MD5_B, "Song B"), "1"),
        (_make_fumen(_FUMEN_ID_LR2, None, _MD5_LR2, "LR2 Song"), "2"),
    ]


# ---------------------------------------------------------------------------
# Helper to build the test client with mocked dependencies
# ---------------------------------------------------------------------------

def _make_client_ctx(user, db):
    """Context manager that returns an AsyncClient with overridden dependencies."""

    class _Ctx:
        async def __aenter__(self):
            app.dependency_overrides[get_current_user_optional] = lambda: user
            app.dependency_overrides[get_db] = lambda: db
            self._client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            return await self._client.__aenter__()

        async def __aexit__(self, *args):
            await self._client.__aexit__(*args)
            app.dependency_overrides.clear()

    return _Ctx()


# ---------------------------------------------------------------------------
# Tests: snapshot metadata fields
# ---------------------------------------------------------------------------


async def test_historical_snapshot_metadata_mode_is_historical() -> None:
    """as_of response must carry snapshot_mode='historical' and is_current_snapshot=False."""
    user = _make_user()
    db = _make_db(_make_fumen_rows(), _make_historical_score_rows())

    async with _make_client_ctx(user, db) as ac:
        resp = await ac.get(
            f"/analysis/table/{_TABLE_ID}/clear-distribution",
            params={"as_of": "2026-05-01", "user_id": str(_USER_ID)},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["snapshot_mode"] == "historical", f"Expected 'historical', got: {data.get('snapshot_mode')}"
    assert data["snapshot_date"] == "2026-05-01"
    assert data["is_current_snapshot"] is False


async def test_current_snapshot_metadata_mode_is_current() -> None:
    """No as_of → snapshot_mode='current', snapshot_date=None, is_current_snapshot=True."""
    user = _make_user()
    db = _make_db(_make_fumen_rows(), _make_all_score_rows())

    async with _make_client_ctx(user, db) as ac:
        resp = await ac.get(
            f"/analysis/table/{_TABLE_ID}/clear-distribution",
            params={"user_id": str(_USER_ID)},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["snapshot_mode"] == "current", f"Expected 'current', got: {data.get('snapshot_mode')}"
    assert data["snapshot_date"] is None
    assert data["is_current_snapshot"] is True


# ---------------------------------------------------------------------------
# Tests: historical filtering behaviour
# ---------------------------------------------------------------------------


async def test_historical_snapshot_fumen_a_shows_no_play_before_hard_date() -> None:
    """Fumen A scored HARD on 2026-05-10; as_of=2026-05-01 must show it as NO PLAY (0)."""
    user = _make_user()
    db = _make_db(_make_fumen_rows(), _make_historical_score_rows())

    async with _make_client_ctx(user, db) as ac:
        resp = await ac.get(
            f"/analysis/table/{_TABLE_ID}/clear-distribution",
            params={"as_of": "2026-05-01", "user_id": str(_USER_ID)},
        )

    assert resp.status_code == 200, resp.text
    songs = {s["sha256"]: s for s in resp.json()["songs"]}

    assert _SHA256_A in songs, "Song A must appear in songs list"
    assert songs[_SHA256_A]["clear_type"] == 0, (
        f"Expected NO PLAY (0) for Song A in historical view, got {songs[_SHA256_A]['clear_type']}"
    )


async def test_historical_snapshot_fumen_b_shows_easy_before_hard_date() -> None:
    """Fumen B scored EASY on 2026-04-15; as_of=2026-05-01 must show it as EASY (2)."""
    user = _make_user()
    db = _make_db(_make_fumen_rows(), _make_historical_score_rows())

    async with _make_client_ctx(user, db) as ac:
        resp = await ac.get(
            f"/analysis/table/{_TABLE_ID}/clear-distribution",
            params={"as_of": "2026-05-01", "user_id": str(_USER_ID)},
        )

    assert resp.status_code == 200, resp.text
    songs = {s["sha256"]: s for s in resp.json()["songs"]}

    assert _SHA256_B in songs, "Song B must appear in songs list"
    assert songs[_SHA256_B]["clear_type"] == 2, (
        f"Expected EASY (2) for Song B in historical view, got {songs[_SHA256_B]['clear_type']}"
    )


async def test_current_snapshot_fumen_a_shows_hard() -> None:
    """Without as_of, fumen A's HARD clear must be visible."""
    user = _make_user()
    db = _make_db(_make_fumen_rows(), _make_all_score_rows())

    async with _make_client_ctx(user, db) as ac:
        resp = await ac.get(
            f"/analysis/table/{_TABLE_ID}/clear-distribution",
            params={"user_id": str(_USER_ID)},
        )

    assert resp.status_code == 200, resp.text
    songs = {s["sha256"]: s for s in resp.json()["songs"]}

    assert _SHA256_A in songs, "Song A must appear in songs list"
    assert songs[_SHA256_A]["clear_type"] == 7, (
        f"Expected HARD (7) for Song A in current view, got {songs[_SHA256_A]['clear_type']}"
    )


async def test_historical_snapshot_includes_lr2_md5_only_fumen() -> None:
    """LR2 md5-only fumens must appear in historical snapshots with correct clear type."""
    user = _make_user()
    db = _make_db(_make_fumen_rows(), _make_historical_score_rows())

    async with _make_client_ctx(user, db) as ac:
        resp = await ac.get(
            f"/analysis/table/{_TABLE_ID}/clear-distribution",
            params={"as_of": "2026-05-01", "user_id": str(_USER_ID)},
        )

    assert resp.status_code == 200, resp.text
    songs = resp.json()["songs"]

    lr2_song = next((s for s in songs if s.get("title") == "LR2 Song"), None)
    assert lr2_song is not None, (
        f"LR2 song must appear in songs list; titles: {[s.get('title') for s in songs]}"
    )
    assert lr2_song["clear_type"] == 2, (
        f"Expected EASY (2) for LR2 song, got {lr2_song['clear_type']}"
    )


async def test_historical_snapshot_level_histogram_excludes_post_snapshot_scores() -> None:
    """Level-1 histogram for as_of=2026-05-01 must count A as NO PLAY, B as EASY."""
    user = _make_user()
    db = _make_db(_make_fumen_rows(), _make_historical_score_rows())

    async with _make_client_ctx(user, db) as ac:
        resp = await ac.get(
            f"/analysis/table/{_TABLE_ID}/clear-distribution",
            params={"as_of": "2026-05-01", "user_id": str(_USER_ID)},
        )

    assert resp.status_code == 200, resp.text
    levels = {lv["level"]: lv["counts"] for lv in resp.json()["levels"]}

    assert "1" in levels, f"Level '1' must appear; levels: {list(levels.keys())}"
    counts = levels["1"]

    assert counts.get("0", 0) == 1, f"Expected 1 NO PLAY in level 1; counts={counts}"
    assert counts.get("2", 0) == 1, f"Expected 1 EASY in level 1; counts={counts}"
    assert "7" not in counts, f"HARD must not appear in level 1 historical view; counts={counts}"
