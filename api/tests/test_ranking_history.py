"""Regression tests for ranking history best-score merging."""

from datetime import date
import uuid

import pytest

from app.services.ranking_config import BonusConfig, ReferenceCondition, TableRankingConfig
from app.services.ranking_dashboard import (
    _capture_ranks_for_targets,
    _query_table_score_history,
    compute_exp_progress_fields,
)
from app.services.ranking_calculator import BestScore, _exp_level, _merge_best_score_fields


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
