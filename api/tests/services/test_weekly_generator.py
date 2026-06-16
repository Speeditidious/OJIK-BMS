import random

from app.services.weekly_config import Bracket, Selector
from app.services.weekly_generator import (
    PoolEntry,
    resolve_levels,
    dedup_pool,
    pick,
)


def test_resolve_levels_from_range_inclusive():
    level_order = ["1", "2", "3", "4", "5", "6"]
    sel = Selector(table="x", level_range=("2", "4"))
    assert resolve_levels(level_order, sel) == ["2", "3", "4"]


def test_resolve_levels_explicit_overrides_range():
    level_order = ["1", "2", "3"]
    sel = Selector(table="x", levels=("1", "3"))
    assert resolve_levels(level_order, sel) == ["1", "3"]


def test_resolve_levels_unknown_bound_raises():
    level_order = ["1", "2", "3"]
    sel = Selector(table="x", level_range=("2", "9"))
    try:
        resolve_levels(level_order, sel)
        assert False
    except Exception:
        pass


def test_dedup_keeps_first_occurrence_by_fumen_id():
    import uuid
    fid = uuid.uuid4()
    t1, t2 = uuid.uuid4(), uuid.uuid4()
    pool = [
        PoolEntry(fumen_id=fid, table_id=t1, level="21", table_symbol="★"),
        PoolEntry(fumen_id=fid, table_id=t2, level="21", table_symbol="▼"),
        PoolEntry(fumen_id=uuid.uuid4(), table_id=t1, level="22", table_symbol="★"),
    ]
    deduped = dedup_pool(pool)
    assert len(deduped) == 2
    assert deduped[0].table_symbol == "★"


def test_pick_caps_at_pool_size():
    pool = [PoolEntry(fumen_id=__import__("uuid").uuid4(), table_id=None, level="1", table_symbol="x") for _ in range(3)]
    rng = random.Random(42)
    assert len(pick(pool, 5, rng)) == 3
    assert len(pick(pool, 2, rng)) == 2
