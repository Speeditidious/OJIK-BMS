"""Regression tests for dashboard backend range handling and source-client aggregation."""

import asyncio
import tomllib
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.score import UserScore
from app.models.user import User
from app.routers.analysis import (
    _build_fumen_aggregate,
    _build_activity_subquery,
    _get_daily_plays,
    _get_day_stats,
    _initial_sync_exclusion_filters,
    _initial_sync_exclusion_for_subq,
    _split_table_level_order,
    _resolve_activity_window,
    _resolve_rating_update_window,
    get_play_summary,
    get_score_updates,
)
from app.routers.rankings import get_ranking_display_config, get_ranking_history
from app.routers.scores import get_score_for_song, get_scores_for_fumen
from app.services.client_aggregation import PerClientBest, aggregate_source_client
from app.services.ranking_calculator import BestScore, compute_ranking
from app.services.ranking_config import (
    BmsForceEmblem,
    LevelOverride,
    RankingConfig,
    RankingConfigError,
    _validate_bmsforce_emblems,
)
from app.services.ranking_dashboard import (
    _compare_entries,
    _resolve_best_state_timestamps,
    _resolve_date_window,
    build_user_contribution_rows,
    compute_rating_breakdown,
    compute_rating_updates,
    compute_rating_updates_aggregated,
    resolve_best_state_row,
)
from app.services.rating_derived_data import _build_user_table_rating_derived_rows


def _make_rating_table(top_n: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        slug="test-table",
        table_id=uuid.uuid4(),
        display_name="Test Table",
        display_order=1,
        top_n=top_n,
        max_level=200,
    )


def _compile_conditions(conditions) -> str:
    return "\n".join(
        str(
            condition.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for condition in conditions
    )


def test_initial_sync_exclusion_filters_apply_to_all_first_synced_clients():
    user = SimpleNamespace(
        first_synced_at={
            "lr2": "2026-05-06T09:00:00+00:00",
            "beatoraja": "2026-05-06T10:00:00+00:00",
            "invalid": "not-a-timestamp",
        }
    )

    conditions = _initial_sync_exclusion_filters(user)
    compiled = _compile_conditions(conditions)

    assert len(conditions) == 2
    assert "user_scores.client_type != 'lr2'" in compiled
    assert "user_scores.client_type != 'beatoraja'" in compiled
    assert "user_scores.synced_at > '2026-05-06 12:00:00+00:00'" in compiled
    assert "user_scores.synced_at > '2026-05-06 13:00:00+00:00'" in compiled


def test_initial_sync_exclusion_subquery_filters_apply_to_all_first_synced_clients():
    user = SimpleNamespace(
        first_synced_at={
            "lr2": "2026-05-06T09:00:00+00:00",
            "beatoraja": "2026-05-06T10:00:00+00:00",
        }
    )
    subq = select(
        UserScore.client_type.label("client_type"),
        UserScore.synced_at.label("synced_at"),
    ).subquery()

    conditions = _initial_sync_exclusion_for_subq(user, subq)
    compiled = _compile_conditions(conditions)

    assert len(conditions) == 2
    assert "client_type != 'lr2'" in compiled
    assert "client_type != 'beatoraja'" in compiled
    assert "synced_at > '2026-05-06 12:00:00+00:00'" in compiled
    assert "synced_at > '2026-05-06 13:00:00+00:00'" in compiled


def test_activity_subquery_excludes_no_play_rows_from_counts():
    user = SimpleNamespace(id=uuid.uuid4())

    subq = _build_activity_subquery(user)
    compiled = str(
        select(subq).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "user_scores.clear_type IS NULL OR user_scores.clear_type != 0" in compiled


def test_split_table_level_order_uses_custom_and_non_regular_order():
    """Dashboard table levels should use admin custom orders and ignore stale values."""
    regular, non_regular = _split_table_level_order(
        ["1", "2", "3", "EX", "INSANE"],
        ["3", "MISSING", "1", "2"],
        ["INSANE", "MISSING", "EX"],
    )

    assert regular == ["3", "1", "2"]
    assert non_regular == ["INSANE", "EX"]


def _build_fake_ranking(scores, top_n: int):
    values = sorted(
        [
            float(score.exscore or 0)
            for score in scores
            if score.exscore is not None
        ],
        reverse=True,
    )
    total = sum(values)
    rating = sum(values[:top_n])
    return SimpleNamespace(
        exp=total,
        exp_level=1,
        rating=rating,
        rating_norm=rating / 1000.0,
    )


def _make_level_override_table(song_sha256: str) -> SimpleNamespace:
    return SimpleNamespace(
        slug="test-table",
        table_id=uuid.uuid4(),
        display_name="Test Table",
        display_order=1,
        top_n=1,
        max_level=200,
        level_order=["12", "13"],
        level_weights={"12": 100.0, "13": 200.0},
        base_lamp_mult={"HARD": 1.0},
        upper_lamp_bonus={"HARD": 0.0},
        rank_mult={"AA": 1.0},
        bonus=SimpleNamespace(
            bp_weight=0.0,
            rate_weight=0.0,
            bp_floor=100.0,
            bp_slope=1.0,
            rate_floor=0.5,
            rate_slope=1.0,
        ),
        c_table=1.0,
        level_overrides=[
            LevelOverride(
                fumen_sha256=song_sha256,
                fumen_md5=None,
                lamp_to_level={"HARD": "13"},
                note="test override",
            )
        ],
    )


def test_level_overrides_affect_rating_but_not_saved_display_level():
    song_sha256 = "a" * 64
    table_cfg = _make_level_override_table(song_sha256)
    score = BestScore(
        sha256=song_sha256,
        md5=None,
        level="12",
        clear_type=5,
        exscore=1800,
        rate=95.0,
        rank="AA",
        min_bp=1,
    )
    result = compute_ranking(table_cfg, exp_level_step=100.0, scores=[score])

    assert result.rating == 200.0
    assert result.rating_contributions[0]["song_rating"] == 200.0
    assert result.rating_contributions[0]["level"] == "12"
    assert result.exp_top_contributions[0]["level"] == "12"


@pytest.mark.asyncio
async def test_contribution_rows_display_original_level_with_level_override(monkeypatch):
    song_sha256 = "b" * 64
    user_id = uuid.uuid4()
    table_cfg = _make_level_override_table(song_sha256)
    score = BestScore(
        sha256=song_sha256,
        md5=None,
        level="12",
        clear_type=5,
        exscore=1800,
        rate=95.0,
        rank="AA",
        min_bp=1,
    )
    detail_score_id = uuid.uuid4()
    detail_options = {"option": 2}

    async def fake_query_target_fumen_details(_table_id, _db):
        return [
            {
                "sha256": song_sha256,
                "md5": None,
                "title": "Override Song",
                "artist": "Artist",
                "level": "12",
            }
        ]

    async def fake_bulk_query_best_scores(_table_id, _db, user_id=None):
        return {user_id: [score]}

    async def fake_query_per_client_bests(_table_id, _user_id, _db):
        return {}

    async def fake_query_best_state_times(_table_id, _user_id, _db, _targets, _score_by_key):
        return {
            (song_sha256, None): (
                None,
                None,
                str(detail_score_id),
                "beatoraja",
                detail_options,
            )
        }

    monkeypatch.setattr(
        "app.services.ranking_dashboard.query_target_fumen_details",
        fake_query_target_fumen_details,
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.bulk_query_best_scores",
        fake_bulk_query_best_scores,
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard._query_per_client_bests",
        fake_query_per_client_bests,
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard._query_best_state_times",
        fake_query_best_state_times,
    )

    result = await build_user_contribution_rows(
        user_id=user_id,
        table_cfg=table_cfg,
        db=object(),
        metric="rating",
        scope="top",
        sort_by="value",
        sort_dir="desc",
        page=1,
        limit=20,
        query=None,
        table_symbol="★",
    )

    assert result["entries"][0]["value"] == 200.0
    assert result["entries"][0]["level"] == "12"
    assert result["entries"][0]["detail_score_id"] == str(detail_score_id)
    assert result["entries"][0]["client_type"] == "beatoraja"
    assert result["entries"][0]["options"] == detail_options


def test_ranking_config_toml_is_valid():
    config_path = Path(__file__).resolve().parents[1] / "ranking_tables" / "config.toml"

    parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))

    assert "global" in parsed
    assert "tables" in parsed


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _QueuedResult:
    def __init__(self, rows=None, scalar=None, row=None):
        self._rows = rows or []
        self._scalar = scalar
        self._row = row

    def __iter__(self):
        return iter(self._rows)

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar

    def one_or_none(self):
        return self._row

    def one(self):
        return self._row


class _QueuedSession:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _query):
        if not self._results:
            raise AssertionError("Unexpected execute() call")
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_score_updates_uses_target_user_for_initial_sync_flag(monkeypatch):
    target_user = SimpleNamespace(
        id=uuid.uuid4(),
        first_synced_at={"beatoraja": "2026-04-22T09:00:00+00:00"},
        is_active=True,
    )
    score = UserScore(
        id=uuid.uuid4(),
        user_id=target_user.id,
        fumen_hash_others="course-hash",
        client_type="beatoraja",
        play_count=3,
        synced_at=datetime(2026, 4, 22, 9, 30, tzinfo=UTC),
    )
    db = _QueuedSession(
        [
            _QueuedResult(rows=[SimpleNamespace(score_id=score.id)]),
            _QueuedResult(rows=[score]),
            _QueuedResult(rows=[]),
            _QueuedResult(rows=[score]),
        ]
    )

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return target_user

    async def fake_build_course_indexes(_db):
        return ({}, {}, {})

    monkeypatch.setattr("app.routers.analysis._resolve_target_user", fake_resolve_target_user)
    monkeypatch.setattr("app.routers.analysis._build_course_indexes", fake_build_course_indexes)
    monkeypatch.setattr(
        "app.routers.analysis._match_course_from_indexes",
        lambda *_args, **_kwargs: SimpleNamespace(name="Test Course", dan_title="Test Dan"),
    )

    result = await get_score_updates(
        date="2026-04-22",
        user_id=target_user.id,
        current_user=None,
        db=db,
    )

    assert result["play_count_updates"][0]["is_initial_sync"] is True
    assert result["play_count_updates"][0]["detail_score_id"] == str(score.id)


@pytest.mark.asyncio
async def test_scores_for_fumen_marks_null_recorded_at_within_three_hour_first_sync(monkeypatch):
    target_user = SimpleNamespace(
        id=uuid.uuid4(),
        first_synced_at={"lr2": "2026-05-06T14:34:43.481754+00:00"},
        is_active=True,
    )
    score = UserScore(
        id=uuid.uuid4(),
        user_id=target_user.id,
        fumen_md5="a" * 32,
        client_type="lr2",
        clear_type=4,
        exscore=1200,
        rate=80.0,
        rank="AA",
        recorded_at=None,
        synced_at=datetime(2026, 5, 6, 16, 30, 34, 898067, tzinfo=UTC),
    )
    db = _QueuedSession(
        [
            _QueuedResult(rows=[score]),
            _QueuedResult(scalar=target_user.first_synced_at),
            _QueuedResult(row=None),  # fumen_meta (notes_total, keymode)
        ]
    )

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return target_user

    monkeypatch.setattr("app.routers.scores._resolve_target_user", fake_resolve_target_user)

    result = await get_scores_for_fumen(
        hash_value="a" * 32,
        current_user=target_user,
        db=db,
    )

    assert result[0].recorded_at is None
    assert result[0].is_first_sync is True


@pytest.mark.asyncio
async def test_scores_for_fumen_allows_synced_at_after_three_hour_first_sync_window(monkeypatch):
    target_user = SimpleNamespace(
        id=uuid.uuid4(),
        first_synced_at={"lr2": "2026-05-06T14:34:43.481754+00:00"},
        is_active=True,
    )
    score = UserScore(
        id=uuid.uuid4(),
        user_id=target_user.id,
        fumen_md5="b" * 32,
        client_type="lr2",
        clear_type=4,
        exscore=1200,
        rate=80.0,
        rank="AA",
        recorded_at=None,
        synced_at=datetime(2026, 5, 6, 17, 34, 44, 481754, tzinfo=UTC),
    )
    db = _QueuedSession(
        [
            _QueuedResult(rows=[score]),
            _QueuedResult(scalar=target_user.first_synced_at),
            _QueuedResult(row=None),  # fumen_meta (notes_total, keymode)
        ]
    )

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return target_user

    monkeypatch.setattr("app.routers.scores._resolve_target_user", fake_resolve_target_user)

    result = await get_scores_for_fumen(
        hash_value="b" * 32,
        current_user=target_user,
        db=db,
    )

    assert result[0].recorded_at is None
    assert result[0].is_first_sync is False


@pytest.mark.asyncio
async def test_scores_for_fumen_preserves_real_recorded_at_inside_first_sync_window(monkeypatch):
    target_user = SimpleNamespace(
        id=uuid.uuid4(),
        first_synced_at={"beatoraja": "2026-05-06T14:34:43.481754+00:00"},
        is_active=True,
    )
    recorded_at = datetime(2026, 5, 1, 10, 0, 0, tzinfo=UTC)
    score = UserScore(
        id=uuid.uuid4(),
        user_id=target_user.id,
        fumen_md5="c" * 32,
        client_type="beatoraja",
        clear_type=4,
        exscore=1200,
        rate=80.0,
        rank="AA",
        recorded_at=recorded_at,
        synced_at=datetime(2026, 5, 6, 16, 30, 34, 898067, tzinfo=UTC),
    )
    db = _QueuedSession(
        [
            _QueuedResult(rows=[score]),
            _QueuedResult(scalar=target_user.first_synced_at),
            _QueuedResult(row=None),  # fumen_meta (notes_total, keymode)
        ]
    )

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return target_user

    monkeypatch.setattr("app.routers.scores._resolve_target_user", fake_resolve_target_user)

    result = await get_scores_for_fumen(
        hash_value="c" * 32,
        current_user=target_user,
        db=db,
    )

    assert result[0].recorded_at == recorded_at.isoformat()


class _ScoreSession:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _query):
        return _ScalarResult(self._rows)


class _HistorySession:
    def __init__(self):
        self.commit_calls = 0
        self.rollback_calls = 0

    async def commit(self):
        self.commit_calls += 1

    async def rollback(self):
        self.rollback_calls += 1


def test_aggregate_source_client_prefers_single_dominant_client_with_missing_fields():
    source_client, detail = aggregate_source_client(
        [
            PerClientBest(client_type="lr2", exscore=1000),
            PerClientBest(client_type="beatoraja", clear_type=5, exscore=900, min_bp=5),
        ]
    )

    assert source_client == "LR"
    assert detail is None


def test_aggregate_source_client_reports_mix_when_best_fields_are_split():
    source_client, detail = aggregate_source_client(
        [
            PerClientBest(client_type="lr2", clear_type=3, exscore=1000),
            PerClientBest(client_type="beatoraja", clear_type=5, exscore=900, min_bp=4),
        ]
    )

    assert source_client == "MIX"
    assert detail == {
        "clear_type": "BR",
        "exscore": "LR",
        "min_bp": "BR",
    }


def _contribution_entry(**overrides):
    entry = {
        "rank": 1,
        "sha256": "a" * 64,
        "md5": None,
        "title": "Alpha",
        "level": "12",
        "value": 100.0,
        "clear_type": 5,
        "client_types": ["beatoraja"],
        "min_bp": 10,
        "rate": 90.0,
        "rank_grade": "AA",
        "recorded_at": datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
        "sort_recorded_at": datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
    }
    entry.update(overrides)
    return entry


def test_contribution_entry_sort_supports_rank_and_recorded_at_with_nulls_last():
    newer = _contribution_entry(
        title="Newer",
        rank=2,
        recorded_at=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        sort_recorded_at=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
    )
    older = _contribution_entry(
        title="Older",
        rank=1,
        recorded_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
        sort_recorded_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
    )
    missing = _contribution_entry(title="Missing", rank=3, recorded_at=None, sort_recorded_at=None)
    first_sync = _contribution_entry(
        title="First Sync",
        rank=4,
        recorded_at=None,
        sort_recorded_at=datetime(2026, 4, 20, 13, 0, tzinfo=UTC),
    )

    assert _compare_entries(newer, older, "recorded_at", "desc", {"12": 0}) < 0
    assert _compare_entries(older, newer, "recorded_at", "asc", {"12": 0}) < 0
    assert _compare_entries(missing, newer, "recorded_at", "desc", {"12": 0}) > 0
    assert _compare_entries(first_sync, older, "recorded_at", "asc", {"12": 0}) > 0
    assert _compare_entries(older, newer, "rank", "asc", {"12": 0}) < 0


def test_best_state_timestamp_requires_exscore_when_available():
    best = BestScore(
        sha256="a" * 64,
        md5=None,
        level="12",
        clear_type=5,
        exscore=1040,
        rate=86.67,
        rank="AA",
        min_bp=12,
    )
    first_best_at = datetime(2026, 4, 20, 11, 0, tzinfo=UTC)
    repeat_best_at = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)

    display_ts, sort_ts = _resolve_best_state_timestamps(
        [
            {
                "clear_type": 5,
                "min_bp": 14,
                "exscore": 1040,
                "rate": 86.67,
                "rank": "AA",
                "display_recorded_at": datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
                "effective_ts": datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
            },
            {
                "clear_type": 5,
                "min_bp": 12,
                "exscore": 1030,
                "rate": 86.67,
                "rank": "AA",
                "display_recorded_at": datetime(2026, 4, 20, 10, 30, tzinfo=UTC),
                "effective_ts": datetime(2026, 4, 20, 10, 30, tzinfo=UTC),
            },
            {
                "clear_type": 5,
                "min_bp": 12,
                "exscore": 1040,
                "rate": 86.67,
                "rank": "AA",
                "display_recorded_at": first_best_at,
                "effective_ts": first_best_at,
            },
            {
                "clear_type": 5,
                "min_bp": 12,
                "exscore": 1040,
                "rate": 86.67,
                "rank": "AA",
                "display_recorded_at": repeat_best_at,
                "effective_ts": repeat_best_at,
            },
        ],
        best,
    )

    assert display_ts == first_best_at
    assert sort_ts == first_best_at


def test_best_state_row_returns_first_real_row_that_completed_best_state():
    best = BestScore(
        sha256="a" * 64,
        md5=None,
        level="12",
        clear_type=5,
        exscore=1040,
        rate=86.67,
        rank="AA",
        min_bp=12,
    )
    first_id = uuid.uuid4()
    repeat_id = uuid.uuid4()
    first_best_at = datetime(2026, 4, 20, 11, 0, tzinfo=UTC)
    repeat_best_at = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)

    row = resolve_best_state_row(
        [
            {
                "score_id": first_id,
                "clear_type": 5,
                "min_bp": 12,
                "exscore": 1040,
                "rate": 86.67,
                "rank": "AA",
                "effective_ts": first_best_at,
            },
            {
                "score_id": repeat_id,
                "clear_type": 5,
                "min_bp": 12,
                "exscore": 1040,
                "rate": 86.67,
                "rank": "AA",
                "effective_ts": repeat_best_at,
            },
        ],
        best,
    )

    assert row is not None
    assert row["score_id"] == first_id


def test_best_state_timestamp_ignores_missing_optional_best_fields():
    best = BestScore(
        sha256="b" * 64,
        md5=None,
        level="12",
        clear_type=5,
        exscore=None,
        rate=86.67,
        rank="AA",
        min_bp=12,
    )
    first_best_at = datetime(2026, 4, 20, 11, 0, tzinfo=UTC)

    display_ts, sort_ts = _resolve_best_state_timestamps(
        [
            {
                "clear_type": 5,
                "min_bp": 12,
                "rate": 86.67,
                "rank": "AA",
                "display_recorded_at": first_best_at,
                "effective_ts": first_best_at,
            }
        ],
        best,
    )

    assert display_ts == first_best_at
    assert sort_ts == first_best_at


def test_resolve_activity_window_supports_custom_range():
    start_date, until_date, meta = _resolve_activity_window(
        days=None,
        from_=date(2026, 4, 1),
        to=date(2026, 4, 20),
    )

    assert start_date == date(2026, 4, 1)
    assert until_date == date(2026, 4, 21)
    assert meta == {"from": "2026-04-01", "to": "2026-04-20"}


def test_resolve_activity_window_rejects_partial_range():
    with pytest.raises(HTTPException) as exc_info:
        _resolve_activity_window(days=None, from_=date(2026, 4, 1), to=None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "both 'from' and 'to' must be provided"


def test_resolve_rating_update_window_rejects_multiple_modes():
    with pytest.raises(HTTPException) as exc_info:
        _resolve_rating_update_window(
            year=None,
            days=30,
            target_date=None,
            from_=date(2026, 4, 1),
            to=date(2026, 4, 20),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Specify exactly one of year, days, date, or from+to"


def test_resolve_date_window_accepts_explicit_range():
    start_date, end_date = _resolve_date_window(
        from_date=date(2026, 4, 1),
        to_date=date(2026, 4, 20),
    )

    assert start_date == date(2026, 4, 1)
    assert end_date == date(2026, 4, 20)


def test_validate_bmsforce_emblems_sorts_and_normalizes_labels():
    emblems = _validate_bmsforce_emblems(
        [
            {
                "tier": "legend",
                "min_value": 20,
                "max_value": None,
                "color": "#FFD700",
                "glow_intensity": "strong",
                "label": " Legend ",
            },
            {
                "tier": "rookie",
                "min_value": 0,
                "max_value": 2,
                "color": "#999",
                "glow_intensity": "none",
                "label": " ",
            },
            {
                "tier": "bronze",
                "min_value": 2,
                "max_value": 20,
                "color": "#A67C52",
                "glow_intensity": "subtle",
            },
        ]
    )

    assert [emblem.tier for emblem in emblems] == ["rookie", "bronze", "legend"]
    assert emblems[0].label is None
    assert emblems[-1].label == "Legend"


def test_validate_bmsforce_emblems_rejects_gaps():
    with pytest.raises(RankingConfigError) as exc_info:
        _validate_bmsforce_emblems(
            [
                {
                    "tier": "rookie",
                    "min_value": 0,
                    "max_value": 2,
                    "color": "#999999",
                    "glow_intensity": "none",
                },
                {
                    "tier": "bronze",
                    "min_value": 3,
                    "max_value": None,
                    "color": "#A67C52",
                    "glow_intensity": "subtle",
                },
            ]
        )

    assert "continuous" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_ranking_display_config_serializes_emblems(monkeypatch):
    config = RankingConfig(
        tables=[],
        exp_level_step=100.0,
        high_tier_rating_anchor=1000.0,
        bmsforce_emblems=[
            BmsForceEmblem(
                tier="rookie",
                min_value=0.0,
                max_value=2.0,
                color="#999999",
                glow_intensity="none",
            ),
            BmsForceEmblem(
                tier="legend",
                min_value=20.0,
                max_value=None,
                color="#FFD700",
                glow_intensity="strong",
                label="Legend",
            ),
        ],
    )
    monkeypatch.setattr("app.routers.rankings.get_ranking_config", lambda: config)

    result = await get_ranking_display_config()

    assert result == {
        "bmsforce_emblems": [
            {
                "tier": "rookie",
                "min_value": 0.0,
                "max_value": 2.0,
                "color": "#999999",
                "glow_intensity": "none",
                "label": None,
            },
            {
                "tier": "legend",
                "min_value": 20.0,
                "max_value": None,
                "color": "#FFD700",
                "glow_intensity": "strong",
                "label": "Legend",
            },
        ]
    }


@pytest.mark.asyncio
async def test_get_score_for_song_uses_common_source_client_aggregation():
    user_id = uuid.uuid4()
    target_sha = "a" * 64
    current_user = User(id=user_id, username="tester", is_active=True)
    rows = [
        UserScore(
            id=uuid.uuid4(),
            user_id=user_id,
            client_type="lr2",
            fumen_sha256=target_sha,
            clear_type=5,
            exscore=1000,
            max_combo=500,
            min_bp=None,
            recorded_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
        ),
        UserScore(
            id=uuid.uuid4(),
            user_id=user_id,
            client_type="beatoraja",
            fumen_sha256=target_sha,
            clear_type=5,
            exscore=900,
            max_combo=450,
            min_bp=5,
            recorded_at=datetime(2026, 4, 20, 11, 0, tzinfo=UTC),
        ),
    ]

    result = await get_score_for_song(
        fumen_sha256=target_sha,
        client_type=None,
        current_user=current_user,
        db=_ScoreSession(rows),
    )

    assert result.source_client == "LR"
    assert result.source_client_detail is None
    assert result.best_clear_type_client == "LR"
    assert result.best_exscore_client == "LR"
    assert result.best_min_bp_client == "BR"


@pytest.mark.asyncio
async def test_get_score_for_song_displays_non_100_max_as_perfect():
    user_id = uuid.uuid4()
    target_sha = "b" * 64
    current_user = User(id=user_id, username="tester", is_active=True)
    raw_row = UserScore(
        id=uuid.uuid4(),
        user_id=user_id,
        client_type="beatoraja",
        fumen_sha256=target_sha,
        clear_type=9,
        exscore=1998,
        rate=99.9,
        rank="AAA",
        min_bp=0,
        recorded_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
    )

    result = await get_score_for_song(
        fumen_sha256=target_sha,
        client_type=None,
        current_user=current_user,
        db=_ScoreSession([raw_row]),
    )

    assert raw_row.clear_type == 9
    assert result.best_clear_type == 8


def test_build_fumen_aggregate_uses_display_clear_type_for_current_state():
    row = SimpleNamespace(
        fumen_sha256="c" * 64,
        fumen_md5=None,
        client_type="beatoraja",
        clear_type=9,
        exscore=0,
        rate=0.0,
        rank="F",
        min_bp=None,
        max_combo=0,
        options=None,
        play_count=1,
    )

    result = _build_fumen_aggregate([row], {})

    assert result[("c" * 64, None)]["current_state"]["clear_type"] == 7


@pytest.mark.asyncio
async def test_get_ranking_history_accepts_730_day_range(monkeypatch):
    current_user = User(id=uuid.uuid4(), username="tester", is_active=True)
    table_cfg = SimpleNamespace(slug="test-table")
    config = SimpleNamespace(get_table_by_slug=lambda slug: table_cfg if slug == "test-table" else None)

    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)

    async def fake_compute_ranking_history_for_user(_user_id, _table_cfg, _config, from_, to, _db):
        return [SimpleNamespace(date=from_, exp=10.0, exp_level=1, rating=20.0, rating_norm=0.5)]

    monkeypatch.setattr(
        "app.services.ranking_calculator.compute_ranking_history_for_user",
        fake_compute_ranking_history_for_user,
    )

    from_date = date(2024, 4, 20)
    to_date = from_date + timedelta(days=730)
    result = await get_ranking_history(
        table_slug="test-table",
        from_=from_date,
        to=to_date,
        user_id=None,
        current_user=current_user,
        db=object(),
    )

    assert result["from"] == "2024-04-20"
    assert result["to"] == "2026-04-20"
    assert len(result["points"]) == 1


@pytest.mark.asyncio
async def test_get_ranking_history_trims_leading_zero_points_but_keeps_pre_sync_records(monkeypatch):
    current_user = User(
        id=uuid.uuid4(),
        username="tester",
        is_active=True,
        first_synced_at={"lr2": "2026-04-27T09:00:00+00:00"},
    )
    table_cfg = SimpleNamespace(slug="test-table")
    config = SimpleNamespace(get_table_by_slug=lambda slug: table_cfg if slug == "test-table" else None)
    seen_from: date | None = None

    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)

    async def fake_compute_ranking_history_for_user(_user_id, _table_cfg, _config, from_, _to, _db):
        nonlocal seen_from
        seen_from = from_
        return [
            SimpleNamespace(date=from_, exp=0.0, exp_level=0, rating=0.0, rating_norm=0.0),
            SimpleNamespace(date=date(2026, 4, 10), exp=12000.0, exp_level=10, rating=12000.0, rating_norm=12.0),
            SimpleNamespace(date=date(2026, 4, 27), exp=15000.0, exp_level=12, rating=15000.0, rating_norm=15.0),
        ]

    monkeypatch.setattr(
        "app.services.ranking_calculator.compute_ranking_history_for_user",
        fake_compute_ranking_history_for_user,
    )

    result = await get_ranking_history(
        table_slug="test-table",
        from_=date(2026, 4, 1),
        to=date(2026, 4, 30),
        user_id=None,
        current_user=current_user,
        db=object(),
    )

    assert seen_from == date(2026, 4, 1)
    assert result["from"] == "2026-04-01"
    assert [point["date"] for point in result["points"]] == ["2026-04-10", "2026-04-27"]
    assert result["points"][0]["rating"] == 12000.0


@pytest.mark.asyncio
async def test_get_ranking_history_returns_empty_when_range_has_only_zero_points(monkeypatch):
    current_user = User(
        id=uuid.uuid4(),
        username="tester",
        is_active=True,
        first_synced_at={"lr2": "2026-04-27T09:00:00+00:00"},
    )
    table_cfg = SimpleNamespace(slug="test-table")
    config = SimpleNamespace(get_table_by_slug=lambda slug: table_cfg if slug == "test-table" else None)

    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)

    async def fake_compute_ranking_history_for_user(_user_id, _table_cfg, _config, from_, _to, _db):
        return [SimpleNamespace(date=from_, exp=0.0, exp_level=0, rating=0.0, rating_norm=0.0)]

    monkeypatch.setattr(
        "app.services.ranking_calculator.compute_ranking_history_for_user",
        fake_compute_ranking_history_for_user,
    )

    result = await get_ranking_history(
        table_slug="test-table",
        from_=date(2026, 4, 1),
        to=date(2026, 4, 20),
        user_id=None,
        current_user=current_user,
        db=object(),
    )

    assert result["from"] == "2026-04-01"
    assert result["to"] == "2026-04-20"
    assert result["points"] == []


@pytest.mark.asyncio
async def test_get_ranking_history_rejects_731_day_range(monkeypatch):
    monkeypatch.setattr(
        "app.routers.rankings._get_config_or_503",
        lambda: SimpleNamespace(get_table_by_slug=lambda _slug: None),
    )
    current_user = User(id=uuid.uuid4(), username="tester", is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await get_ranking_history(
            table_slug="test-table",
            from_=date(2024, 4, 20),
            to=date(2026, 4, 21),
            user_id=None,
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Date range too large (max 730 days)"


@pytest.mark.asyncio
async def test_get_ranking_history_rebuilds_stale_derived_data_before_fetch(monkeypatch):
    current_user = User(id=uuid.uuid4(), username="tester", is_active=True)
    table_cfg = _make_rating_table()
    config = SimpleNamespace(
        exp_level_step=100.0,
        get_table_by_slug=lambda slug: table_cfg if slug == table_cfg.slug else None,
    )
    db = _HistorySession()
    state = {"fresh": False}
    recalc_calls = 0
    fetch_calls = 0

    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)
    monkeypatch.setattr("app.routers.rankings._HISTORY_REBUILD_LOCKS", {})

    async def fake_has_fresh(_user_id, _table_id, _db):
        return state["fresh"]

    async def fake_recalculate_user(_user_id, _config, _db):
        nonlocal recalc_calls
        recalc_calls += 1
        state["fresh"] = True

    async def fake_fetch(_user_id, _table_id, from_, _to, _step, _max_level, _db):
        nonlocal fetch_calls
        fetch_calls += 1
        return [SimpleNamespace(date=from_, exp=10.0, exp_level=1, rating=20.0, rating_norm=0.5)]

    async def fake_compute(*_args, **_kwargs):
        raise AssertionError("fallback replay should not run when rebuild succeeds")

    monkeypatch.setattr("app.routers.rankings.has_fresh_user_table_rating_derived_data", fake_has_fresh)
    monkeypatch.setattr("app.services.ranking_calculator.recalculate_user", fake_recalculate_user)
    monkeypatch.setattr("app.routers.rankings.fetch_user_table_rating_history_points", fake_fetch)
    monkeypatch.setattr("app.services.ranking_calculator.compute_ranking_history_for_user", fake_compute)

    result = await get_ranking_history(
        table_slug=table_cfg.slug,
        from_=date(2026, 4, 1),
        to=date(2026, 4, 7),
        user_id=None,
        current_user=current_user,
        db=db,
    )

    assert result["points"] == [
        {
            "date": "2026-04-01",
            "exp": 10.0,
            "exp_level": 1,
            "rating": 20.0,
            "rating_norm": 0.5,
        }
    ]
    assert recalc_calls == 1
    assert fetch_calls == 1
    assert db.commit_calls == 1
    assert db.rollback_calls == 0


@pytest.mark.asyncio
async def test_get_ranking_history_falls_back_after_rebuild_failure(monkeypatch):
    current_user = User(id=uuid.uuid4(), username="tester", is_active=True)
    table_cfg = _make_rating_table()
    config = SimpleNamespace(
        exp_level_step=100.0,
        get_table_by_slug=lambda slug: table_cfg if slug == table_cfg.slug else None,
    )
    db = _HistorySession()
    compute_calls = 0

    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)
    monkeypatch.setattr("app.routers.rankings._HISTORY_REBUILD_LOCKS", {})

    async def fake_has_fresh(_user_id, _table_id, _db):
        return False

    async def fake_recalculate_user(_user_id, _config, _db):
        raise RuntimeError("rebuild failed")

    async def fake_compute(_user_id, _table_cfg, _config, from_, _to, _db):
        nonlocal compute_calls
        compute_calls += 1
        return [SimpleNamespace(date=from_, exp=33.0, exp_level=2, rating=44.0, rating_norm=0.777)]

    async def fake_fetch(*_args, **_kwargs):
        raise AssertionError("checkpoint fetch should not run when rebuild fails")

    monkeypatch.setattr("app.routers.rankings.has_fresh_user_table_rating_derived_data", fake_has_fresh)
    monkeypatch.setattr("app.services.ranking_calculator.recalculate_user", fake_recalculate_user)
    monkeypatch.setattr("app.services.ranking_calculator.compute_ranking_history_for_user", fake_compute)
    monkeypatch.setattr("app.routers.rankings.fetch_user_table_rating_history_points", fake_fetch)

    result = await get_ranking_history(
        table_slug=table_cfg.slug,
        from_=date(2026, 4, 1),
        to=date(2026, 4, 7),
        user_id=None,
        current_user=current_user,
        db=db,
    )

    assert result["points"] == [
        {
            "date": "2026-04-01",
            "exp": 33.0,
            "exp_level": 2,
            "rating": 44.0,
            "rating_norm": 0.777,
        }
    ]
    assert compute_calls == 1
    assert db.commit_calls == 0
    assert db.rollback_calls == 1


@pytest.mark.asyncio
async def test_get_ranking_history_singleflights_concurrent_stale_rebuilds(monkeypatch):
    current_user = User(id=uuid.uuid4(), username="tester", is_active=True)
    table_cfg = _make_rating_table()
    config = SimpleNamespace(
        exp_level_step=100.0,
        get_table_by_slug=lambda slug: table_cfg if slug == table_cfg.slug else None,
    )
    db = _HistorySession()
    state = {"fresh": False}
    recalc_calls = 0
    fetch_calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)
    monkeypatch.setattr("app.routers.rankings._HISTORY_REBUILD_LOCKS", {})

    async def fake_has_fresh(_user_id, _table_id, _db):
        return state["fresh"]

    async def fake_recalculate_user(_user_id, _config, _db):
        nonlocal recalc_calls
        recalc_calls += 1
        started.set()
        await release.wait()
        state["fresh"] = True

    async def fake_fetch(_user_id, _table_id, from_, _to, _step, _max_level, _db):
        nonlocal fetch_calls
        fetch_calls += 1
        return [SimpleNamespace(date=from_, exp=55.0, exp_level=3, rating=66.0, rating_norm=0.888)]

    async def fake_compute(*_args, **_kwargs):
        raise AssertionError("fallback replay should not run for successful singleflight rebuild")

    monkeypatch.setattr("app.routers.rankings.has_fresh_user_table_rating_derived_data", fake_has_fresh)
    monkeypatch.setattr("app.services.ranking_calculator.recalculate_user", fake_recalculate_user)
    monkeypatch.setattr("app.routers.rankings.fetch_user_table_rating_history_points", fake_fetch)
    monkeypatch.setattr("app.services.ranking_calculator.compute_ranking_history_for_user", fake_compute)

    task1 = asyncio.create_task(
        get_ranking_history(
            table_slug=table_cfg.slug,
            from_=date(2026, 4, 1),
            to=date(2026, 4, 7),
            user_id=None,
            current_user=current_user,
            db=db,
        )
    )
    await started.wait()
    task2 = asyncio.create_task(
        get_ranking_history(
            table_slug=table_cfg.slug,
            from_=date(2026, 4, 1),
            to=date(2026, 4, 7),
            user_id=None,
            current_user=current_user,
            db=db,
        )
    )
    await asyncio.sleep(0)
    release.set()
    result1, result2 = await asyncio.gather(task1, task2)

    assert result1["points"] == result2["points"]
    assert recalc_calls == 1
    assert fetch_calls == 2
    assert db.commit_calls == 1
    assert db.rollback_calls == 0


@pytest.mark.asyncio
async def test_rating_breakdown_uses_display_delta_for_entered_song(monkeypatch):
    table_cfg = _make_rating_table(top_n=2)
    target_date = date(2026, 4, 22)
    song_a = "a" * 64
    song_b = "b" * 64
    song_c = "c" * 64

    targets = [
        {"sha256": song_a, "md5": None, "title": "Alpha", "artist": "Artist", "level": "12"},
        {"sha256": song_b, "md5": None, "title": "Beta", "artist": "Artist", "level": "12"},
        {"sha256": song_c, "md5": None, "title": "Gamma", "artist": "Artist", "level": "12"},
    ]
    alpha_id = uuid.uuid4()
    beta_previous_id = uuid.uuid4()
    gamma_previous_id = uuid.uuid4()
    beta_current_id = uuid.uuid4()
    history_rows = [
        {
            "score_id": alpha_id,
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1200,
            "rate": 90.0,
            "rank": "AA",
            "min_bp": 10,
            "client_type": "lr2",
            "options": {"op_best": 0},
            "effective_ts": datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        },
        {
            "score_id": beta_previous_id,
            "fumen_sha256": song_b,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1138,
            "rate": 89.444,
            "rank": "AA",
            "min_bp": 12,
            "client_type": "lr2",
            "options": {"op_best": 10},
            "effective_ts": datetime(2026, 4, 21, 10, 5, tzinfo=UTC),
        },
        {
            "score_id": gamma_previous_id,
            "fumen_sha256": song_c,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1150,
            "rate": 89.5,
            "rank": "AA",
            "min_bp": 11,
            "client_type": "lr2",
            "options": {"op_best": 20},
            "effective_ts": datetime(2026, 4, 21, 10, 10, tzinfo=UTC),
        },
        {
            "score_id": beta_current_id,
            "fumen_sha256": song_b,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1187,
            "rate": 91.126,
            "rank": "AAA",
            "min_bp": 8,
            "client_type": "beatoraja",
            "options": {"option": 3},
            "effective_ts": datetime(2026, 4, 22, 9, 0, tzinfo=UTC),
        },
    ]

    async def fake_query(_user_id, _table_cfg, _db, _until_date):
        return targets, history_rows

    monkeypatch.setattr("app.services.ranking_dashboard._query_table_score_history", fake_query)
    monkeypatch.setattr(
        "app.services.ranking_dashboard._contribution_value",
        lambda score, target_level, _table_cfg, _sha256, _md5: (
            float(score.exscore or 0) if score is not None else 0.0,
            target_level,
        ),
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.compute_ranking",
        lambda cfg, _step, scores: _build_fake_ranking(scores, cfg.top_n),
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.standardize_rating",
        lambda raw_rating, _level: raw_rating / 1000.0,
    )

    result = await compute_rating_breakdown(
        user_id=uuid.uuid4(),
        table_cfg=table_cfg,
        db=object(),
        table_symbol="ST",
        exp_level_step=100.0,
        target_date=target_date,
    )

    beta_entry = next(entry for entry in result["rating_contributions"] if entry["sha256"] == song_b)
    gamma_entry = next(entry for entry in result["rating_contributions"] if entry["sha256"] == song_c)

    assert beta_entry["delta_rating"] == 49
    assert beta_entry["rate"] == 91.126
    assert beta_entry["previous_rate"] == 89.444
    assert beta_entry["was_in_top_n"] is False
    assert beta_entry["is_in_top_n"] is True
    assert beta_entry["detail_score_id"] == str(beta_current_id)
    assert beta_entry["client_type"] == "beatoraja"
    assert beta_entry["options"] == {"option": 3}
    assert gamma_entry["delta_rating"] == 0
    assert gamma_entry["was_in_top_n"] is True
    assert gamma_entry["is_in_top_n"] is False
    assert gamma_entry["detail_score_id"] == str(gamma_previous_id)
    assert gamma_entry["client_type"] == "lr2"
    assert gamma_entry["options"] == {"op_best": 20}


@pytest.mark.asyncio
async def test_rating_updates_ignore_best_score_changes_without_display_delta(monkeypatch):
    table_cfg = _make_rating_table(top_n=1)
    target_date = date(2026, 4, 22)
    song_a = "a" * 64

    targets = [
        {"sha256": song_a, "md5": None, "title": "Alpha", "artist": "Artist", "level": "12"},
    ]
    history_rows = [
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 3,
            "exscore": 1000,
            "rate": 85.0,
            "rank": "A",
            "min_bp": 25,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1000,
            "rate": 85.0,
            "rank": "A",
            "min_bp": 20,
            "client_type": "beatoraja",
            "effective_ts": datetime(2026, 4, 22, 9, 0, tzinfo=UTC),
        },
    ]

    async def fake_query(_user_id, _table_cfg, _db, _until_date):
        return targets, history_rows

    monkeypatch.setattr("app.services.ranking_dashboard._query_table_score_history", fake_query)
    monkeypatch.setattr(
        "app.services.ranking_dashboard._contribution_value",
        lambda score, target_level, _table_cfg, _sha256, _md5: (
            float(score.exscore or 0) if score is not None else 0.0,
            target_level,
        ),
    )

    result = await compute_rating_updates(
        user_id=uuid.uuid4(),
        table_cfg=table_cfg,
        db=object(),
        table_symbol="ST",
        target_date=target_date,
    )

    assert result["count"] == 0
    assert result["entries"] == []


@pytest.mark.asyncio
async def test_rating_updates_do_not_count_top_n_drops(monkeypatch):
    table_cfg = _make_rating_table(top_n=2)
    target_date = date(2026, 4, 22)
    song_a = "a" * 64
    song_b = "b" * 64
    song_c = "c" * 64

    targets = [
        {"sha256": song_a, "md5": None, "title": "Alpha", "artist": "Artist", "level": "12"},
        {"sha256": song_b, "md5": None, "title": "Beta", "artist": "Artist", "level": "12"},
        {"sha256": song_c, "md5": None, "title": "Gamma", "artist": "Artist", "level": "12"},
    ]
    history_rows = [
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1200,
            "rate": 90.0,
            "rank": "AA",
            "min_bp": 10,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_b,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1138,
            "rate": 89.444,
            "rank": "AA",
            "min_bp": 12,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 5, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_c,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1150,
            "rate": 89.5,
            "rank": "AA",
            "min_bp": 11,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 10, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_b,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1187,
            "rate": 91.126,
            "rank": "AAA",
            "min_bp": 8,
            "client_type": "beatoraja",
            "effective_ts": datetime(2026, 4, 22, 9, 0, tzinfo=UTC),
        },
    ]

    async def fake_query(_user_id, _table_cfg, _db, _until_date):
        return targets, history_rows

    monkeypatch.setattr("app.services.ranking_dashboard._query_table_score_history", fake_query)
    monkeypatch.setattr(
        "app.services.ranking_dashboard._contribution_value",
        lambda score, target_level, _table_cfg, _sha256, _md5: (
            float(score.exscore or 0) if score is not None else 0.0,
            target_level,
        ),
    )

    result = await compute_rating_updates(
        user_id=uuid.uuid4(),
        table_cfg=table_cfg,
        db=object(),
        table_symbol="ST",
        target_date=target_date,
    )

    assert result["count"] == 1
    assert [entry["sha256"] for entry in result["entries"]] == [song_b]


@pytest.mark.asyncio
async def test_rating_derived_daily_rows_do_not_count_top_n_drops(monkeypatch):
    table_cfg = _make_rating_table(top_n=2)
    user_id = uuid.uuid4()
    target_date = date(2026, 4, 22)
    song_a = "a" * 64
    song_b = "b" * 64
    song_c = "c" * 64

    targets = [
        {"sha256": song_a, "md5": None, "title": "Alpha", "artist": "Artist", "level": "12"},
        {"sha256": song_b, "md5": None, "title": "Beta", "artist": "Artist", "level": "12"},
        {"sha256": song_c, "md5": None, "title": "Gamma", "artist": "Artist", "level": "12"},
    ]
    history_rows = [
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1200,
            "rate": 90.0,
            "rank": "AA",
            "min_bp": 10,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_b,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1138,
            "rate": 89.444,
            "rank": "AA",
            "min_bp": 12,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 5, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_c,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1150,
            "rate": 89.5,
            "rank": "AA",
            "min_bp": 11,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 10, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_b,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1187,
            "rate": 91.126,
            "rank": "AAA",
            "min_bp": 8,
            "client_type": "beatoraja",
            "effective_ts": datetime(2026, 4, 22, 9, 0, tzinfo=UTC),
        },
    ]

    async def fake_query(**_kwargs):
        return targets, history_rows

    monkeypatch.setattr("app.services.rating_derived_data._query_table_score_history", fake_query)
    monkeypatch.setattr(
        "app.services.ranking_dashboard._contribution_value",
        lambda score, target_level, _table_cfg, _sha256, _md5: (
            float(score.exscore or 0) if score is not None else 0.0,
            target_level,
        ),
    )

    _checkpoints, daily_rows, updated_keys_by_date = await _build_user_table_rating_derived_rows(
        user_id=user_id,
        table_cfg=table_cfg,
        db=object(),
        excluded_dates=set(),
    )

    target_row = next(row for row in daily_rows if row["effective_date"] == target_date)
    assert target_row["update_count"] == 1
    assert updated_keys_by_date[target_date] == {(song_b, None)}


@pytest.mark.asyncio
async def test_display_rounded_exp_and_rating_changes_gate_breakdown_and_counts(monkeypatch):
    table_cfg = _make_rating_table(top_n=1)
    target_date = date(2026, 4, 22)
    song_a = "a" * 64

    targets = [
        {"sha256": song_a, "md5": None, "title": "Alpha", "artist": "Artist", "level": "12"},
    ]
    history_rows = [
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1000,
            "rate": 90.0,
            "rank": "AA",
            "min_bp": 10,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1001,
            "rate": 90.5,
            "rank": "AA",
            "min_bp": 9,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 22, 11, 0, tzinfo=UTC),
        },
    ]

    async def fake_query(_user_id, _table_cfg, _db, _until_date):
        return targets, history_rows

    monkeypatch.setattr("app.services.ranking_dashboard._query_table_score_history", fake_query)
    monkeypatch.setattr(
        "app.services.ranking_dashboard._contribution_value",
        lambda score, target_level, _table_cfg, _sha256, _md5: (
            (float(score.exscore or 0) / 10.0) if score is not None else 0.0,
            target_level,
        ),
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.compute_ranking",
        lambda cfg, _step, scores: SimpleNamespace(
            exp=sum((score.exscore or 0) / 10.0 for score in scores),
            exp_level=1,
            rating=sum(
                sorted(
                    [(score.exscore or 0) / 10.0 for score in scores],
                    reverse=True,
                )[:cfg.top_n]
            ),
            rating_norm=sum(
                sorted(
                    [(score.exscore or 0) / 10.0 for score in scores],
                    reverse=True,
                )[:cfg.top_n]
            ) / 1000.0,
        ),
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.standardize_rating",
        lambda raw_rating, _level: raw_rating / 1000.0,
    )

    breakdown = await compute_rating_breakdown(
        user_id=uuid.uuid4(),
        table_cfg=table_cfg,
        db=object(),
        table_symbol="ST",
        exp_level_step=100.0,
        target_date=target_date,
    )
    updates = await compute_rating_updates(
        user_id=uuid.uuid4(),
        table_cfg=table_cfg,
        db=object(),
        table_symbol="ST",
        target_date=target_date,
    )

    assert breakdown["exp_contributions"] == []
    assert breakdown["rating_contributions"] == []
    assert updates["count"] == 0


@pytest.mark.asyncio
async def test_rating_updates_skip_excluded_first_sync_date_but_keep_later_baseline(monkeypatch):
    table_cfg = _make_rating_table(top_n=1)
    first_sync_date = date(2026, 4, 21)
    target_date = date(2026, 4, 22)
    song_a = "a" * 64

    targets = [
        {"sha256": song_a, "md5": None, "title": "Alpha", "artist": "Artist", "level": "12"},
    ]
    history_rows = [
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 4,
            "exscore": 1000,
            "rate": 90.126,
            "rank": "AA",
            "min_bp": 10,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        },
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 5,
            "exscore": 1001,
            "rate": 92.345,
            "rank": "AAA",
            "min_bp": 8,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 22, 11, 0, tzinfo=UTC),
        },
    ]

    async def fake_query(_user_id, _table_cfg, _db, _until_date):
        return targets, history_rows

    monkeypatch.setattr("app.services.ranking_dashboard._query_table_score_history", fake_query)
    monkeypatch.setattr(
        "app.services.ranking_dashboard._contribution_value",
        lambda score, target_level, _table_cfg, _sha256, _md5: (
            (float(score.exscore or 0) / 10.0) if score is not None else 0.0,
            target_level,
        ),
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.compute_ranking",
        lambda cfg, _step, scores: _build_fake_ranking(scores, cfg.top_n),
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.standardize_rating",
        lambda raw_rating, _level: raw_rating / 1000.0,
    )

    excluded_dates = {first_sync_date}
    excluded_day = await compute_rating_updates(
        user_id=uuid.uuid4(),
        table_cfg=table_cfg,
        db=object(),
        table_symbol="ST",
        target_date=first_sync_date,
        excluded_dates=excluded_dates,
    )
    next_day = await compute_rating_updates(
        user_id=uuid.uuid4(),
        table_cfg=table_cfg,
        db=object(),
        table_symbol="ST",
        target_date=target_date,
        excluded_dates=excluded_dates,
    )

    assert excluded_day["count"] == 0
    assert excluded_day["entries"] == []
    assert next_day["count"] == 0
    assert next_day["entries"] == []


@pytest.mark.asyncio
async def test_rating_updates_aggregated_skips_excluded_first_sync_date(monkeypatch):
    table_cfg = _make_rating_table(top_n=1)
    excluded_date = date(2026, 4, 21)
    song_a = "a" * 64

    targets = [
        {"sha256": song_a, "md5": None, "title": "Alpha", "artist": "Artist", "level": "12"},
    ]
    history_rows = [
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 4,
            "exscore": 1000,
            "rate": 90.0,
            "rank": "AA",
            "min_bp": 10,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        },
    ]

    async def fake_query(_user_id, _table_cfg, _db, _until_date):
        return targets, history_rows

    monkeypatch.setattr("app.services.ranking_dashboard._query_table_score_history", fake_query)
    monkeypatch.setattr(
        "app.services.ranking_dashboard._contribution_value",
        lambda score, target_level, _table_cfg, _sha256, _md5: (
            float(score.exscore or 0) if score is not None else 0.0,
            target_level,
        ),
    )

    result = await compute_rating_updates_aggregated(
        user_id=uuid.uuid4(),
        ranking_tables=[table_cfg],
        db=object(),
        target_date=excluded_date,
        excluded_dates={excluded_date},
    )

    assert result["date"] == "2026-04-21"
    assert result["count"] == 0
    assert result["tables"] == []


@pytest.mark.asyncio
async def test_rating_breakdown_skips_excluded_first_sync_date(monkeypatch):
    table_cfg = _make_rating_table(top_n=1)
    excluded_date = date(2026, 4, 21)
    song_a = "a" * 64

    targets = [
        {"sha256": song_a, "md5": None, "title": "Alpha", "artist": "Artist", "level": "12"},
    ]
    history_rows = [
        {
            "fumen_sha256": song_a,
            "fumen_md5": None,
            "clear_type": 4,
            "exscore": 1000,
            "rate": 90.126,
            "rank": "AA",
            "min_bp": 10,
            "client_type": "lr2",
            "effective_ts": datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        },
    ]

    async def fake_query(_user_id, _table_cfg, _db, _until_date):
        return targets, history_rows

    monkeypatch.setattr("app.services.ranking_dashboard._query_table_score_history", fake_query)
    monkeypatch.setattr(
        "app.services.ranking_dashboard._contribution_value",
        lambda score, target_level, _table_cfg, _sha256, _md5: (
            float(score.exscore or 0) if score is not None else 0.0,
            target_level,
        ),
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.compute_ranking",
        lambda cfg, _step, scores: _build_fake_ranking(scores, cfg.top_n),
    )
    monkeypatch.setattr(
        "app.services.ranking_dashboard.standardize_rating",
        lambda raw_rating, _level: raw_rating / 1000.0,
    )

    result = await compute_rating_breakdown(
        user_id=uuid.uuid4(),
        table_cfg=table_cfg,
        db=object(),
        table_symbol="ST",
        exp_level_step=100.0,
        target_date=excluded_date,
        excluded_dates={excluded_date},
    )

    assert result["exp_contributions"] == []
    assert result["rating_contributions"] == []


# ── LR2 player-stats reliability filter tests ──────────────────────────────


class _CaptureSession:
    """Fake async DB session that captures compiled SQL strings and returns empty results."""

    def __init__(self, row_overrides: dict | None = None):
        self.captured_queries: list[str] = []
        self._row_overrides = row_overrides or {}

    async def execute(self, query):
        compiled = str(
            query.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        self.captured_queries.append(compiled)
        idx = len(self.captured_queries) - 1
        if idx in self._row_overrides:
            return self._row_overrides[idx]
        return _QueuedResult(
            rows=[],
            row=SimpleNamespace(has_unreliable=False, has_reliable_lr2=False),
        )


@pytest.mark.asyncio
async def test_daily_plays_excludes_unreliable_lr2_rows():
    """_get_daily_plays inner SQL must filter out unreliable LR2 player-stat rows."""
    user = SimpleNamespace(id=uuid.uuid4(), first_synced_at={})
    db = _CaptureSession()

    from datetime import date as date_cls
    await _get_daily_plays(user, None, date_cls(2026, 1, 1), date_cls(2026, 2, 1), db)

    assert db.captured_queries, "_get_daily_plays should execute at least one query"
    inner_sql = db.captured_queries[0]
    # The unreliable predicate: playtime < 10 * playcount for lr2 rows
    assert "playtime" in inner_sql, "inner query should reference playtime column"
    assert "playcount" in inner_sql, "inner query should reference playcount column"
    assert "10 * user_player_stats.playcount" in inner_sql or "playtime < 10 *" in inner_sql or "10" in inner_sql
    assert "lr2" in inner_sql, "inner query should reference lr2 client_type"
    # Key assertion: NOT unreliable = reliable rows only
    assert "NOT" in inner_sql or "not" in inner_sql.lower(), (
        "inner query should contain NOT to negate the unreliable predicate"
    )


@pytest.mark.asyncio
async def test_day_stats_excludes_unreliable_lr2_rows():
    """_get_day_stats inner SQL must filter out unreliable LR2 player-stat rows."""
    user = SimpleNamespace(id=uuid.uuid4(), first_synced_at={})

    # First execute() → inner query result (empty rows)
    # Second execute() → unreliable_check (SimpleNamespace row)
    db = _CaptureSession(
        row_overrides={
            1: _QueuedResult(
                row=SimpleNamespace(has_unreliable=False, has_reliable_lr2=False)
            )
        }
    )

    result = await _get_day_stats(user, None, "2026-01-15", db)

    assert len(db.captured_queries) >= 2, "_get_day_stats should execute at least 2 queries"
    inner_sql = db.captured_queries[0]
    assert "playtime" in inner_sql
    assert "playcount" in inner_sql
    assert "lr2" in inner_sql
    assert "NOT" in inner_sql or "not" in inner_sql.lower(), (
        "inner query should contain NOT to negate the unreliable predicate"
    )

    # Verify player_stats_unreliable key is present in result
    assert "player_stats_unreliable" in result
    assert "player_stats_unreliable_reason" in result


@pytest.mark.asyncio
async def test_day_stats_returns_unreliable_flag_when_lr2_is_self_inconsistent():
    """_get_day_stats returns player_stats_unreliable=True when only unreliable LR2 rows exist."""
    user = SimpleNamespace(id=uuid.uuid4(), first_synced_at={})

    # First execute() → inner query result (empty rows — filtered out)
    # Second execute() → unreliable check: unreliable exists, no reliable
    db = _CaptureSession(
        row_overrides={
            1: _QueuedResult(
                row=SimpleNamespace(has_unreliable=True, has_reliable_lr2=False)
            )
        }
    )

    result = await _get_day_stats(user, None, "2026-01-15", db)

    assert result["player_stats_unreliable"] is True
    assert result["player_stats_unreliable_reason"] == "lr2_player_stats_self_inconsistent"


@pytest.mark.asyncio
async def test_day_stats_does_not_set_unreliable_flag_when_reliable_lr2_exists():
    """_get_day_stats does not flag unreliable when reliable LR2 rows also exist."""
    user = SimpleNamespace(id=uuid.uuid4(), first_synced_at={})

    db = _CaptureSession(
        row_overrides={
            1: _QueuedResult(
                row=SimpleNamespace(has_unreliable=True, has_reliable_lr2=True)
            )
        }
    )

    result = await _get_day_stats(user, None, "2026-01-15", db)

    assert result["player_stats_unreliable"] is False
    assert result["player_stats_unreliable_reason"] is None


@pytest.mark.asyncio
async def test_play_summary_excludes_unreliable_lr2_rows():
    """get_play_summary SQL must include NOT unreliable predicate in latest_subq."""
    target_user = SimpleNamespace(
        id=uuid.uuid4(),
        first_synced_at={},
        is_active=True,
    )

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return target_user

    import app.routers.analysis as analysis_module

    original = analysis_module._resolve_target_user

    capture_db = _CaptureSession(
        row_overrides={
            # query 0: UserScore count query → (total_scores=0, total_play_count=0)
            0: _QueuedResult(row=SimpleNamespace(total_scores=0, total_play_count=0)),
            # query 1: pstats latest_subq aggregate → (None, None, None) as tuple
            1: _QueuedResult(row=(None, None, None)),
            # query 2: judgments query → empty rows
            2: _QueuedResult(rows=[]),
        }
    )

    analysis_module._resolve_target_user = fake_resolve_target_user
    try:
        result = await get_play_summary(
            client_type=None,
            user_id=None,
            current_user=None,
            db=capture_db,
        )
    finally:
        analysis_module._resolve_target_user = original

    # latest_subq is built in query index 1 (pstats aggregate query)
    # The SQL for it should contain the NOT unreliable predicate
    assert len(capture_db.captured_queries) >= 2
    pstats_sql = capture_db.captured_queries[1]
    assert "lr2" in pstats_sql
    assert "playtime" in pstats_sql
    assert "NOT" in pstats_sql or "not" in pstats_sql.lower()

    # has_player_stats should be in the result
    assert "has_player_stats" in result
    assert result["has_player_stats"] is False  # pstats[0] is None → no reliable rows


@pytest.mark.asyncio
async def test_play_summary_has_player_stats_true_when_reliable_rows_exist():
    """get_play_summary returns has_player_stats=True when reliable player-stat rows exist."""
    target_user = SimpleNamespace(
        id=uuid.uuid4(),
        first_synced_at={},
        is_active=True,
    )

    import app.routers.analysis as analysis_module

    original = analysis_module._resolve_target_user

    async def fake_resolve(_user_id, _current_user, _db):
        return target_user

    capture_db = _CaptureSession(
        row_overrides={
            0: _QueuedResult(row=SimpleNamespace(total_scores=10, total_play_count=50)),
            # pstats[0] is not None → has reliable rows (sum=100 playcount, 3600s playtime)
            1: _QueuedResult(row=(100, 3600, None)),
            2: _QueuedResult(rows=[]),
        }
    )

    analysis_module._resolve_target_user = fake_resolve
    try:
        result = await get_play_summary(
            client_type=None,
            user_id=None,
            current_user=None,
            db=capture_db,
        )
    finally:
        analysis_module._resolve_target_user = original

    assert result["has_player_stats"] is True
    # No fallback: total_play_count comes only from pstats
    assert result["total_play_count"] == 100
