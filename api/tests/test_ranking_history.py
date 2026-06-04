"""Regression tests for ranking history best-score merging."""

import uuid
from datetime import date

import pytest

from app.services.ranking_calculator import (
    BestScore,
    _exp_level,
    _merge_best_score_fields,
    _song_rating,
    recalculate_table_bulk,
)
from app.services.ranking_config import (
    BonusConfig,
    RankingConfig,
    ReferenceCondition,
    TableRankingConfig,
)
from app.services.ranking_dashboard import (
    _capture_ranks_for_targets,
    _query_table_score_history,
    compute_exp_progress_fields,
)


def test_merge_best_score_fields_preserves_existing_clear_when_exscore_only_improves():
    existing = BestScore(
        sha256="sha",
        md5="md5",
        level="LEVEL 1",
        clear_type=7,
        exscore=1900,
        rate=88.8,
        rank="AAA",
        min_bp=12,
        client_types=("lr2",),
    )
    row = {
        "clear_type": 5,
        "exscore": 1950,
        "rate": 90.1,
        "rank": "MAX",
        "min_bp": 20,
        "client_type": "beatoraja",
    }

    merged, changed = _merge_best_score_fields(existing, row, "LEVEL 1", "sha", "md5")

    assert changed is True
    assert merged is not None
    assert merged.clear_type == 7
    assert merged.exscore == 1950
    assert merged.rate == 90.1
    assert merged.rank == "MAX"
    assert merged.min_bp == 12
    assert merged.client_types == ("beatoraja", "lr2")


def test_merge_best_score_fields_collects_clients_for_independent_best_fields():
    existing = BestScore(
        sha256="sha",
        md5="md5",
        level="LEVEL 1",
        clear_type=5,
        exscore=1800,
        rate=82.5,
        rank="AA",
        min_bp=30,
        client_types=("lr2",),
    )
    row = {
        "clear_type": 7,
        "exscore": 1800,
        "rate": 82.5,
        "rank": "AA",
        "min_bp": 24,
        "client_type": "beatoraja",
    }

    merged, changed = _merge_best_score_fields(existing, row, "LEVEL 1", "sha", "md5")

    assert changed is True
    assert merged is not None
    assert merged.clear_type == 7
    assert merged.exscore == 1800
    assert merged.min_bp == 24
    assert merged.client_types == ("beatoraja", "lr2")


class _FakeMappingsResult:
    def mappings(self):
        return self

    def all(self):
        return []


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.params = None

    async def execute(self, _statement, params):
        self.params = params
        return _FakeMappingsResult()


@pytest.mark.asyncio
async def test_query_table_score_history_binds_until_date_as_python_date(monkeypatch):
    async def fake_query_target_fumen_details(_table_id, _db):
        return []

    monkeypatch.setattr(
        "app.services.ranking_dashboard.query_target_fumen_details",
        fake_query_target_fumen_details,
    )

    table_cfg = TableRankingConfig(
        slug="test",
        table_id=uuid.uuid4(),
        display_name="Test Table",
        display_order=1,
        level_order=["LEVEL 1"],
        level_weights={"LEVEL 1": 1.0},
        base_lamp_mult={"NOPLAY": 0.0},
        upper_lamp_bonus={"NOPLAY": 0.0},
        rank_mult={"F": 1.0},
        bonus=BonusConfig(
            bp_weight=0.0,
            rate_weight=0.0,
            bp_floor=1.0,
            bp_slope=1.0,
            rate_floor=0.0,
            rate_slope=1.0,
        ),
        reference_20=ReferenceCondition(
            level="LEVEL 1",
            lamp="NOPLAY",
            bp=0,
            rank="F",
            rate=0.0,
        ),
        c_table=1.0,
        top_n=20,
    )
    session = _FakeAsyncSession()
    target_date = date(2026, 4, 16)

    targets, rows = await _query_table_score_history(
        uuid.uuid4(),
        table_cfg,
        session,
        target_date,
    )

    assert targets == []
    assert rows == []
    assert session.params is not None
    assert session.params["until_date"] == target_date
    assert isinstance(session.params["until_date"], date)


def test_capture_ranks_for_targets_tracks_sparse_ranks_and_total_entries():
    targets_by_key = {
        ("sha-1", None): {"title": "Alpha"},
        ("sha-2", None): {"title": "Beta"},
        ("sha-3", None): {"title": "Gamma"},
        ("sha-4", None): {"title": "Omega"},
    }
    values = {
        ("sha-1", None): 12.0,
        ("sha-2", None): 8.0,
        ("sha-3", None): 8.0,
    }

    rank_map, total_entries = _capture_ranks_for_targets(
        values,
        targets_by_key,
        {("sha-2", None), ("sha-4", None)},
    )

    assert total_entries == 4
    assert rank_map[("sha-2", None)] == 2
    assert rank_map[("sha-4", None)] == 4


def test_exp_level_is_capped_by_max_level():
    assert _exp_level(total_exp=100_000, exp_level_step=100, max_level=2) == 2


def test_song_rating_ignores_unknown_level_even_when_bonus_would_score():
    table_cfg = TableRankingConfig(
        slug="test",
        table_id=uuid.uuid4(),
        display_name="Test Table",
        display_order=1,
        level_order=["LEVEL 1"],
        level_weights={"LEVEL 1": 10.0},
        base_lamp_mult={
            "NOPLAY": 0.0,
            "FAILED": 0.1,
            "ASSIST": 0.1,
            "EASY": 1.0,
            "NORMAL": 1.0,
            "HARD": 1.0,
            "EXHARD": 1.0,
            "FC": 1.0,
            "PERFECT": 1.0,
            "MAX": 1.0,
        },
        upper_lamp_bonus={
            "NOPLAY": 0.0,
            "FAILED": 0.0,
            "ASSIST": 0.0,
            "EASY": 0.0,
            "NORMAL": 0.0,
            "HARD": 0.0,
            "EXHARD": 0.0,
            "FC": 0.0,
            "PERFECT": 0.0,
            "MAX": 0.0,
        },
        rank_mult={"F": 0.0, "E": 0.1, "D": 0.3, "C": 0.5, "B": 0.8, "A": 1.0, "AA": 1.0, "AAA": 1.0},
        bonus=BonusConfig(
            bp_weight=1.0,
            rate_weight=1.0,
            bp_floor=100.0,
            bp_slope=1.0,
            rate_floor=0.7,
            rate_slope=1.0,
        ),
        reference_20=ReferenceCondition(
            level="LEVEL 1",
            lamp="EASY",
            bp=100,
            rank="A",
            rate=0.7,
        ),
        c_table=100.0,
        top_n=20,
    )

    assert _song_rating("LEVEL DUMMY", "EASY", "AAA", 0, 1.0, table_cfg) == 0.0


def test_compute_exp_progress_fields_marks_max_level_as_complete():
    progress = compute_exp_progress_fields(
        exp=100_000,
        exp_level=200,
        exp_level_step=100,
        max_level=200,
    )

    assert progress["exp_to_next_level"] == 0.0
    assert progress["exp_level_current_span"] == 1.0
    assert progress["exp_level_progress_ratio"] == 1.0
    assert progress["is_max_level"] is True


@pytest.mark.asyncio
async def test_recalculate_table_bulk_upserts_zero_rows_for_users_without_table_scores(monkeypatch):
    table_id = uuid.uuid4()
    user_without_score = uuid.uuid4()
    another_user_without_score = uuid.uuid4()

    table_cfg = TableRankingConfig(
        slug="test",
        table_id=table_id,
        display_name="Test Table",
        display_order=1,
        level_order=["LEVEL 1"],
        level_weights={"LEVEL 1": 1.0},
        base_lamp_mult={"NOPLAY": 0.0},
        upper_lamp_bonus={"NOPLAY": 0.0},
        rank_mult={"F": 1.0},
        bonus=BonusConfig(
            bp_weight=0.0,
            rate_weight=0.0,
            bp_floor=1.0,
            bp_slope=1.0,
            rate_floor=0.0,
            rate_slope=1.0,
        ),
        reference_20=ReferenceCondition(
            level="LEVEL 1",
            lamp="NOPLAY",
            bp=0,
            rank="F",
            rate=0.0,
        ),
        c_table=1.0,
        top_n=20,
    )
    config = RankingConfig(
        tables=[table_cfg],
        exp_level_step=100.0,
        high_tier_rating_anchor=20_000.0,
    )

    class _RowsResult:
        def all(self):
            return []

    class _FakeSession:
        async def execute(self, _statement, _params=None):
            return _RowsResult()

    async def fake_bulk_query_best_scores(_table_id, _db, user_id=None):
        assert user_id is None
        return {}

    async def fake_select_ranking_user_ids(_db):
        return {user_without_score, another_user_without_score}

    async def fake_batch_check_dan_clearance(user_ids, _table_cfg, _config, _db):
        assert user_ids == {user_without_score, another_user_without_score}
        return {user_id: None for user_id in user_ids}

    upserted = []

    async def fake_upsert_user_ranking(result, upsert_table_id, _db):
        upserted.append((result, upsert_table_id))

    rebuilt = []

    async def fake_rebuild_user_rating_derived_data(user_id, _config, _db):
        rebuilt.append(user_id)

    monkeypatch.setattr(
        "app.services.ranking_calculator.bulk_query_best_scores",
        fake_bulk_query_best_scores,
    )
    monkeypatch.setattr(
        "app.services.ranking_calculator.select_ranking_user_ids",
        fake_select_ranking_user_ids,
    )
    monkeypatch.setattr(
        "app.services.ranking_calculator.batch_check_dan_clearance",
        fake_batch_check_dan_clearance,
    )
    monkeypatch.setattr(
        "app.services.ranking_calculator.upsert_user_ranking",
        fake_upsert_user_ranking,
    )
    monkeypatch.setattr(
        "app.services.rating_derived_data.rebuild_user_rating_derived_data",
        fake_rebuild_user_rating_derived_data,
    )

    processed = await recalculate_table_bulk(table_cfg, config, _FakeSession())

    assert processed == 2
    assert {result.user_id for result, _ in upserted} == {
        user_without_score,
        another_user_without_score,
    }
    assert {upsert_table_id for _, upsert_table_id in upserted} == {table_id}
    assert all(result.exp == 0.0 for result, _ in upserted)
    assert all(result.exp_level == 0 for result, _ in upserted)
    assert all(result.rating == 0.0 for result, _ in upserted)
    assert all(result.rating_norm == 0.0 for result, _ in upserted)
    assert set(rebuilt) == {user_without_score, another_user_without_score}
