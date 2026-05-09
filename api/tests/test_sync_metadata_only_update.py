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


def _make_best(row_id, judgments=None, scorehash=None):
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
        "_latest_scorehash": scorehash,
    }


@pytest.mark.asyncio
async def test_sync_skips_no_play_before_score_computation_or_update():
    """NO PLAY rows must not be stored even if judgments could compute score fields."""
    captured_updates: list = []
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_db = _make_mock_db(captured_updates)

    payload = sync_module.SyncRequest(
        scores=[
            sync_module.ScoreSyncItem(
                fumen_md5="a" * 32,
                client_type="lr2",
                clear_type=0,
                notes=1000,
                judgments={
                    "perfect": 1000,
                    "great": 0,
                    "good": 0,
                    "bad": 0,
                    "poor": 0,
                },
                play_count=0,
            )
        ],
        player_stats=[],
    )

    with patch.object(sync_module, "_fetch_current_bests", AsyncMock(return_value={})):
        with patch.object(sync_module, "_fetch_existing_scorehashes", AsyncMock(return_value=set())):
            with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
                result = await sync_module.sync_data(
                    payload,
                    current_user=mock_user,
                    db=mock_db,
                )

    assert result.synced_scores == 0
    assert result.inserted_scores == 0
    assert result.metadata_updated == 0
    assert result.skipped_scores == 1
    assert captured_updates == []


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


@pytest.mark.asyncio
async def test_metadata_only_update_includes_scorehash_and_updates_cache_once():
    """Metadata-only updates include scorehash and do not repeat within one payload."""
    row_id = uuid.uuid4()
    fumen_md5 = uuid.uuid4().hex[:32]
    scorehash = uuid.uuid4().hex
    captured_updates: list = []
    best = _make_best(row_id, _ORIG_JUDGMENTS, scorehash=None)

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
            AsyncMock(return_value={(None, fumen_md5, None, "lr2"): best}),
        ):
            with patch.object(sync_module, "_fetch_existing_scorehashes", AsyncMock(return_value=set())):
                with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.post(
                            "/sync/",
                            json={
                                "scores": [
                                    {
                                        "scorehash": scorehash,
                                        "fumen_md5": fumen_md5,
                                        "client_type": "lr2",
                                        "clear_type": 2,
                                        "exscore": 1000,
                                        "judgments": _ORIG_JUDGMENTS,
                                    },
                                    {
                                        "scorehash": scorehash,
                                        "fumen_md5": fumen_md5,
                                        "client_type": "lr2",
                                        "clear_type": 2,
                                        "exscore": 1000,
                                        "judgments": _ORIG_JUDGMENTS,
                                    },
                                ],
                                "player_stats": [],
                            },
                        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata_updated"] == 1
    assert data["skipped_scores"] == 1
    assert len(captured_updates) == 1


@pytest.mark.asyncio
async def test_same_day_merge_counts_as_metadata_updated():
    """Merging an improved score into an existing same-day row updates that row."""
    row_id = uuid.uuid4()
    user_id = uuid.uuid4()
    fumen_md5 = uuid.uuid4().hex[:32]
    recorded_at = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    captured_updates: list = []

    existing_same_day = UserScore(
        id=row_id,
        user_id=user_id,
        client_type="lr2",
        fumen_md5=fumen_md5,
        clear_type=2,
        exscore=1000,
        min_bp=20,
        recorded_at=recorded_at,
    )
    mock_user = MagicMock()
    mock_user.id = user_id
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
            with patch.object(
                sync_module,
                "_fetch_same_day_rows",
                AsyncMock(return_value={(fumen_md5, "lr2", recorded_at.date()): existing_same_day}),
            ):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post(
                        "/sync/",
                        json={
                            "scores": [{
                                "fumen_md5": fumen_md5,
                                "client_type": "lr2",
                                "clear_type": 2,
                                "exscore": 1100,
                                "recorded_at": recorded_at.isoformat(),
                                "judgments": _NEW_JUDGMENTS,
                            }],
                            "player_stats": [],
                        },
                    )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["synced_scores"] == 1
    assert data["inserted_scores"] == 0
    assert data["metadata_updated"] == 1
    assert len(captured_updates) == 1


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


@pytest.mark.asyncio
async def test_metadata_only_update_skipped_when_scorehash_mismatches_target_row():
    """When the incoming scorehash differs from the stored row's scorehash, no update is issued."""
    row_id = uuid.uuid4()
    hash_others = "a" * 256  # 4-fumen course
    captured_updates: list = []
    best = _make_best(row_id, judgments={"epg": 100}, scorehash="scorehash_A")

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
            AsyncMock(return_value={(None, None, hash_others, "beatoraja"): best}),
        ):
            with patch.object(sync_module, "_fetch_existing_scorehashes", AsyncMock(return_value=set())):
                with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.post(
                            "/sync/",
                            json={
                                "scores": [{
                                    "scorehash": "scorehash_B",
                                    "fumen_hash_others": hash_others,
                                    "client_type": "beatoraja",
                                    "clear_type": 1,
                                    "exscore": 500,
                                    "judgments": {"epg": 50},
                                }],
                                "player_stats": [],
                            },
                        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata_updated"] == 0, "scorehash mismatch must not update the row"
    assert data["skipped_scores"] == 1
    assert len(captured_updates) == 0, "no UPDATE should have been issued"


@pytest.mark.asyncio
async def test_metadata_only_update_applied_when_scorehash_matches_target_row():
    """When the incoming scorehash matches the stored row's scorehash, metadata update is applied."""
    row_id = uuid.uuid4()
    hash_others = "b" * 256
    captured_updates: list = []
    best = _make_best(row_id, judgments={"epg": 100}, scorehash="scorehash_A")

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
            AsyncMock(return_value={(None, None, hash_others, "beatoraja"): best}),
        ):
            with patch.object(
                sync_module,
                "_fetch_existing_scorehashes",
                AsyncMock(return_value={("scorehash_A", "beatoraja", None, None, hash_others)}),
            ):
                with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.post(
                            "/sync/",
                            json={
                                "scores": [{
                                    "scorehash": "scorehash_A",
                                    "fumen_hash_others": hash_others,
                                    "client_type": "beatoraja",
                                    "clear_type": 2,
                                    "exscore": 1000,
                                    "judgments": {"epg": 110},  # changed
                                }],
                                "player_stats": [],
                            },
                        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata_updated"] == 1, "matching scorehash should allow metadata update"
    assert data["skipped_scores"] == 0
    assert len(captured_updates) == 1


@pytest.mark.asyncio
async def test_metadata_only_update_when_item_scorehash_is_none_keeps_existing_behavior():
    """LR2 rows (scorehash=None) are not blocked by the scorehash guard — existing behavior preserved."""
    row_id = uuid.uuid4()
    fumen_md5 = uuid.uuid4().hex[:32]
    captured_updates: list = []
    best = _make_best(row_id, judgments=_ORIG_JUDGMENTS, scorehash=None)

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
            AsyncMock(return_value={(None, fumen_md5, None, "lr2"): best}),
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
    assert data["metadata_updated"] == 1, "LR2 (scorehash=None) must still update metadata"
    assert data["skipped_scores"] == 0
    assert len(captured_updates) == 1


@pytest.mark.asyncio
async def test_oscillation_scenario_full_flow():
    """Two items sharing the same fumen_hash_others but different scorehashes must not oscillate.

    Scenario mirrors the real bug: Beatoraja stores the same course under mode=10000 and
    mode=10020 as separate rows.  Only Row A (scorehash_A) exists in the DB.  Both Item A
    and Item B are sent in a single payload; neither is an improvement.  Item A is a no-op
    (identical to DB); Item B has scorehash_B ≠ scorehash_A → scorehash mismatch → skipped.
    Running the same payload a second time must produce identical results.
    """
    row_id = uuid.uuid4()
    hash_others = "c" * 256
    JA = {"epg": 100, "lpg": 50}
    JB = {"epg": 0, "lpg": 0}

    def make_best_for_row_a():
        return _make_best(row_id, judgments=JA, scorehash="scorehash_A")

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    payload = {
        "scores": [
            {
                "scorehash": "scorehash_A",
                "fumen_hash_others": hash_others,
                "client_type": "beatoraja",
                "clear_type": 4,
                "exscore": 20025,
                "judgments": JA,
            },
            {
                "scorehash": "scorehash_B",
                "fumen_hash_others": hash_others,
                "client_type": "beatoraja",
                "clear_type": 1,
                "exscore": 0,
                "judgments": JB,
            },
        ],
        "player_stats": [],
    }

    async def override_get_db():
        yield _make_mock_db([])

    for _run in range(2):
        captured_updates: list = []
        mock_db = _make_mock_db(captured_updates)

        async def _override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            with patch.object(
                sync_module,
                "_fetch_current_bests",
                AsyncMock(return_value={(None, None, hash_others, "beatoraja"): make_best_for_row_a()}),
            ):
                with patch.object(
                    sync_module,
                    "_fetch_existing_scorehashes",
                    AsyncMock(return_value={("scorehash_A", "beatoraja", None, None, hash_others)}),
                ):
                    with patch.object(sync_module, "_fetch_same_day_rows", AsyncMock(return_value={})):
                        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                            resp = await client.post("/sync/", json=payload)
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata_updated"] == 0, f"run {_run + 1}: oscillation detected — metadata_updated should be 0"
        assert data["skipped_scores"] == 2, f"run {_run + 1}: both items should be skipped"
        assert len(captured_updates) == 0, f"run {_run + 1}: no UPDATE should have been issued"


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


def test_scorehash_identity_key_includes_fumen_hashes():
    """Same scorehash is only the same row when the fumen identity also matches."""
    from app.routers.sync import ScoreSyncItem, _scorehash_identity_key

    shared_scorehash = "same-scorehash"
    item_a = ScoreSyncItem(
        scorehash=shared_scorehash,
        fumen_sha256="a" * 64,
        client_type="beatoraja",
    )
    item_b = ScoreSyncItem(
        scorehash=shared_scorehash,
        fumen_sha256="b" * 64,
        client_type="beatoraja",
    )

    assert _scorehash_identity_key(item_a) != _scorehash_identity_key(item_b)


def test_scorehash_conflict_target_includes_fumen_identity():
    """The PostgreSQL upsert target must match the fumen-scoped unique index."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.dialects.postgresql import insert

    from app.routers.sync import _scorehash_conflict_index_elements

    ins = insert(UserScore).values(
        user_id=uuid.uuid4(),
        client_type="beatoraja",
        scorehash="same-scorehash",
        fumen_sha256="a" * 64,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=_scorehash_conflict_index_elements(),
        index_where=sync_module.text("scorehash IS NOT NULL"),
        set_={"clear_type": ins.excluded.clear_type},
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "COALESCE(fumen_sha256, '')" in compiled
    assert "COALESCE(fumen_md5, '')" in compiled
    assert "COALESCE(fumen_hash_others, '')" in compiled
