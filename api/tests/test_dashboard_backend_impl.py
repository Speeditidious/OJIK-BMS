"""Regression tests for dashboard backend range handling and source-client aggregation."""

import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import tomllib

import pytest
from fastapi import HTTPException

from app.models.score import UserScore
from app.models.user import User
from app.routers.analysis import _resolve_activity_window, _resolve_rating_update_window
from app.routers.rankings import get_ranking_display_config, get_ranking_history
from app.routers.scores import get_score_for_song
from app.services.client_aggregation import PerClientBest, aggregate_source_client
from app.services.ranking_config import (
    BmsForceEmblem,
    RankingConfig,
    RankingConfigError,
    _validate_bmsforce_emblems,
)
from app.services.ranking_dashboard import (
    _resolve_date_window,
    compute_rating_breakdown,
    compute_rating_updates,
    compute_rating_updates_aggregated,
)


def _make_rating_table(top_n: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        slug="test-table",
        table_id=uuid.uuid4(),
        display_name="Test Table",
        display_order=1,
        top_n=top_n,
        max_level=200,
    )


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


class _ScoreSession:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _query):
        return _ScalarResult(self._rows)


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
    assert beta_entry["rate"] == 91.13
    assert beta_entry["previous_rate"] == 89.44
    assert beta_entry["was_in_top_n"] is False
    assert beta_entry["is_in_top_n"] is True
    assert gamma_entry["delta_rating"] == 0
    assert gamma_entry["was_in_top_n"] is True
    assert gamma_entry["is_in_top_n"] is False


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
