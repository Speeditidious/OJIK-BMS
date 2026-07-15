"""Tests for GET /rankings/{table_slug}/calc-params."""
import uuid

import pytest
from fastapi import HTTPException

from app.routers.rankings import get_calc_params
from app.services.ranking_config import (
    BonusConfig,
    LevelOverride,
    RankingConfig,
    ReferenceCondition,
    TableRankingConfig,
)


def _make_table_cfg(slug: str = "test-table") -> TableRankingConfig:
    """Build a minimal-but-complete TableRankingConfig for endpoint tests."""
    return TableRankingConfig(
        slug=slug,
        table_id=uuid.uuid4(),
        display_name="Test Table",
        display_order=1,
        level_order=["LEVEL 1", "LEVEL 2"],
        level_weights={"LEVEL 1": 1.0, "LEVEL 2": 2.0},
        base_lamp_mult={"NOPLAY": 0.0, "MAX": 1.0},
        upper_lamp_bonus={"NOPLAY": 0.0, "MAX": 0.2},
        # rank_mult here is already the "effective" merged dict (global +
        # table override applied at config-load time — see
        # load_ranking_config in ranking_config.py, which merges
        # `{**global_rank_mult, **table_override}` into TableRankingConfig
        # before it is ever stored on the dataclass).
        rank_mult={"F": 0.0, "AAA": 1.08},
        bonus=BonusConfig(
            bp_weight=0.15,
            rate_weight=0.40,
            bp_floor=150.0,
            bp_slope=1.0,
            rate_floor=0.70,
            rate_slope=1.0,
        ),
        reference_20=ReferenceCondition(
            level="LEVEL 1",
            lamp="MAX",
            bp=0,
            rank="AAA",
            rate=1.0,
        ),
        c_table=123.4,
        top_n=100,
        max_level=200,
        level_overrides=[
            LevelOverride(
                fumen_sha256=None,
                fumen_md5="d" * 32,
                lamp_to_level={"HARD": "LEVEL 2"},
                note="test override",
            ),
        ],
    )


def _make_config(table_cfg: TableRankingConfig) -> RankingConfig:
    return RankingConfig(
        tables=[table_cfg],
        exp_level_step=100.0,
        high_tier_rating_anchor=1000.0,
    )


@pytest.mark.asyncio
async def test_get_calc_params_returns_all_required_fields(monkeypatch):
    table_cfg = _make_table_cfg()
    config = _make_config(table_cfg)
    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)

    result = await get_calc_params("test-table")

    assert result["slug"] == "test-table"
    assert result["top_n"] == 100
    assert result["max_level"] == 200
    assert result["exp_level_step"] == 100.0
    assert result["config_fingerprint"].startswith("sha256:")
    assert result["c_table"] == 123.4
    assert result["level_weights"] == {"LEVEL 1": 1.0, "LEVEL 2": 2.0}
    assert result["base_lamp_mult"] == {"NOPLAY": 0.0, "MAX": 1.0}
    assert result["upper_lamp_bonus"] == {"NOPLAY": 0.0, "MAX": 0.2}
    assert result["rank_mult"] == {"F": 0.0, "AAA": 1.08}
    assert result["bonus"] == {
        "bp_weight": 0.15,
        "rate_weight": 0.40,
        "bp_floor": 150.0,
        "bp_slope": 1.0,
        "rate_floor": 0.70,
        "rate_slope": 1.0,
    }
    assert result["level_overrides"] == [
        {
            "fumen_sha256": None,
            "fumen_md5": "d" * 32,
            "lamp_to_level": {"HARD": "LEVEL 2"},
            "note": "test override",
        }
    ]


@pytest.mark.asyncio
async def test_get_calc_params_404_for_unknown_slug(monkeypatch):
    table_cfg = _make_table_cfg()
    config = _make_config(table_cfg)
    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)

    with pytest.raises(HTTPException) as exc_info:
        await get_calc_params("does-not-exist")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_calc_params_fingerprint_is_stable_across_calls(monkeypatch):
    table_cfg = _make_table_cfg()
    config = _make_config(table_cfg)
    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)

    first = await get_calc_params("test-table")
    second = await get_calc_params("test-table")

    assert first["config_fingerprint"] == second["config_fingerprint"]
    assert first["config_fingerprint"].startswith("sha256:")


@pytest.mark.asyncio
async def test_get_calc_params_fingerprint_differs_across_tables(monkeypatch):
    table_a = _make_table_cfg(slug="table-a")
    table_b = _make_table_cfg(slug="table-b")
    table_b.c_table = 999.9
    config = RankingConfig(
        tables=[table_a, table_b],
        exp_level_step=100.0,
        high_tier_rating_anchor=1000.0,
    )
    monkeypatch.setattr("app.routers.rankings._get_config_or_503", lambda: config)

    result_a = await get_calc_params("table-a")
    result_b = await get_calc_params("table-b")

    assert result_a["config_fingerprint"] != result_b["config_fingerprint"]
