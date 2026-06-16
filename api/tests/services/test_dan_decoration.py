import uuid

import pytest

from app.services import dan_decoration as service
from app.services.ranking_config import (
    BonusConfig,
    DanConfig,
    RankingConfig,
    ReferenceCondition,
    TableRankingConfig,
)


class _FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    async def execute(self, _statement, params):
        self.params = params
        return _FakeResult(self.rows)


def _table(slug, table_id, dans):
    return TableRankingConfig(
        slug=slug,
        table_id=table_id,
        display_name=slug,
        display_order=0,
        level_order=["1"],
        level_weights={"1": 1.0},
        base_lamp_mult={},
        upper_lamp_bonus={},
        rank_mult={},
        bonus=BonusConfig(0, 0, 0, 1, 0, 1),
        reference_20=ReferenceCondition("1", "EASY", 0, "A", 0.8),
        c_table=1.0,
        top_n=50,
        dans=dans,
    )


def _linked_table(slug, table_id, linked_dan_table):
    table = _table(slug, table_id, [])
    table.linked_dan_table = linked_dan_table
    return table


@pytest.mark.asyncio
async def test_resolve_dan_decorations_for_table_ignores_other_table_dans(monkeypatch):
    user_id = uuid.uuid4()
    balgwang_id = uuid.uuid4()
    stella_id = uuid.uuid4()
    balgwang = _table(
        "balgwang",
        balgwang_id,
        [
            DanConfig("発狂初段", "course", None, "★01", "#111111", "none", 1),
        ],
    )
    stella = _table(
        "stella",
        stella_id,
        [
            DanConfig("st12", "course", None, "st12", "#222222", "strong", 12),
        ],
    )
    monkeypatch.setattr(service, "get_ranking_config", lambda: RankingConfig([balgwang, stella], 1, 1))

    db = _FakeDb(
        [
            {"uid": str(user_id), "tid": str(balgwang_id), "dan_title": "発狂初段"},
            {"uid": str(user_id), "tid": str(stella_id), "dan_title": "st12"},
        ]
    )

    result = await service.resolve_dan_decorations_for_table(db, [user_id], "balgwang")

    assert result[str(user_id)]["display_text"] == "★01"
    assert db.params["table_ids"] == [str(balgwang_id)]


@pytest.mark.asyncio
async def test_resolve_dan_decorations_for_table_uses_linked_dan_definitions(monkeypatch):
    user_id = uuid.uuid4()
    balgwang_id = uuid.uuid4()
    overjoy_id = uuid.uuid4()
    balgwang = _table(
        "balgwang",
        balgwang_id,
        [
            DanConfig("発狂Overjoy", "course", None, "(^^)", "#111111", "strong", 120),
        ],
    )
    overjoy = _linked_table("overjoy", overjoy_id, "balgwang")
    monkeypatch.setattr(service, "get_ranking_config", lambda: RankingConfig([balgwang, overjoy], 1, 1))

    db = _FakeDb(
        [
            {"uid": str(user_id), "tid": str(overjoy_id), "dan_title": "発狂Overjoy"},
        ]
    )

    result = await service.resolve_dan_decorations_for_table(db, [user_id], "overjoy")

    assert result[str(user_id)]["display_text"] == "(^^)"
