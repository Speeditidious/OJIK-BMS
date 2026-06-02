"""Tests for lazy course score row details."""
import uuid
import inspect
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.score import UserScore
from app.routers.scores import get_course_row_detail


def test_course_row_detail_accepts_exact_score_id():
    """Course expansion must optionally restrict detail to the clicked score row."""
    assert "score_id" in inspect.signature(get_course_row_detail).parameters


class _Result:
    def __init__(self, *, rows=None):
        self._rows = rows or []

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _query):
        if not self._results:
            raise AssertionError("Unexpected execute() call")
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_course_row_detail_returns_aggregate_record_and_ordered_stages(monkeypatch):
    target_user = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    course_hash = "sha-1sha-2"
    course = SimpleNamespace(
        id=uuid.uuid4(),
        name="Course A",
        source_table_id=uuid.uuid4(),
        sha256_list=["sha-1", "sha-2"],
        md5_list=["md5-1", "md5-2"],
    )
    score = UserScore(
        id=uuid.uuid4(),
        user_id=target_user.id,
        fumen_hash_others=course_hash,
        client_type="beatoraja",
        clear_type=5,
        exscore=2000,
        judgments={"epg": 900, "lpg": 100, "egr": 0, "lgr": 0},
        options={"option": 1},
        recorded_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    stages = [
        SimpleNamespace(sha256="sha-1", md5="md5-1", level="★1", title="First"),
        SimpleNamespace(sha256="sha-2", md5="md5-2", level="★2", title="Second"),
    ]
    db = _Session([
        _Result(rows=[course]),
        _Result(rows=[score]),
        _Result(rows=[SimpleNamespace(symbol="★", slug="stella")]),
        _Result(rows=stages),
    ])

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return target_user

    monkeypatch.setattr("app.routers.scores._resolve_target_user", fake_resolve_target_user)

    result = await get_course_row_detail(
        course_hash=course_hash,
        client_type="beatoraja",
        user_id=target_user.id,
        as_of=None,
        current_user=None,
        db=db,
    )

    assert result.course_name == "Course A"
    assert result.records[0].client_type == "beatoraja"
    assert result.records[0].option_label == "MIRROR"
    assert result.records[0].judgment_detail["judgments"][0]["count"] == 1000
    assert [stage.model_dump() for stage in result.stages] == [
        {"stage": 1, "level": "★1", "title": "First", "fumen_sha256": "sha-1", "fumen_md5": "md5-1", "table_symbol": "★"},
        {"stage": 2, "level": "★2", "title": "Second", "fumen_sha256": "sha-2", "fumen_md5": "md5-2", "table_symbol": "★"},
    ]


@pytest.mark.asyncio
async def test_course_row_detail_preserves_missing_stage(monkeypatch):
    target_user = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    course_hash = "lr2-header" + "m" * 32 + "n" * 32
    course = SimpleNamespace(
        id=uuid.uuid4(),
        name="Course B",
        source_table_id=uuid.uuid4(),
        sha256_list=None,
        md5_list=["m" * 32, "n" * 32],
    )
    score = UserScore(
        id=uuid.uuid4(),
        user_id=target_user.id,
        fumen_hash_others=course_hash,
        client_type="lr2",
        judgments={"perfect": 100, "great": 10},
        options={"op_best": 20},
    )
    db = _Session([
        _Result(rows=[course]),
        _Result(rows=[score]),
        _Result(rows=[SimpleNamespace(symbol="★", slug="stella")]),
        _Result(rows=[]),
    ])

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return target_user

    monkeypatch.setattr("app.routers.scores._resolve_target_user", fake_resolve_target_user)

    result = await get_course_row_detail(
        course_hash=course_hash,
        client_type="lr2",
        user_id=target_user.id,
        as_of=None,
        current_user=None,
        db=db,
    )

    assert result.records[0].option_label == "RANDOM"
    assert [stage.model_dump() for stage in result.stages] == [
        {"stage": 1, "level": None, "title": None, "fumen_sha256": None, "fumen_md5": None, "table_symbol": "★"},
        {"stage": 2, "level": None, "title": None, "fumen_sha256": None, "fumen_md5": None, "table_symbol": "★"},
    ]


@pytest.mark.asyncio
async def test_course_row_detail_filters_selected_score_id(monkeypatch):
    target_user = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    score_id = uuid.uuid4()
    course_hash = "sha-1"
    course = SimpleNamespace(
        id=uuid.uuid4(),
        name="Course Exact",
        source_table_id=None,
        sha256_list=["sha-1"],
        md5_list=["md5-1"],
    )
    score = UserScore(
        id=score_id,
        user_id=target_user.id,
        fumen_hash_others=course_hash,
        client_type="beatoraja",
        judgments={"epg": 10},
        options={"option": 0},
    )
    db = _Session([
        _Result(rows=[course]),
        _Result(rows=[score]),
        _Result(rows=[]),
    ])

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return target_user

    monkeypatch.setattr("app.routers.scores._resolve_target_user", fake_resolve_target_user)

    result = await get_course_row_detail(
        course_hash=course_hash,
        client_type="beatoraja",
        score_id=score_id,
        user_id=target_user.id,
        as_of=None,
        current_user=None,
        db=db,
    )

    assert [record.score_id for record in result.records] == [str(score_id)]
