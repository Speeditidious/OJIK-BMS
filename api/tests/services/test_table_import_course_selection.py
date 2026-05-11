"""Tests for constraint-aware course active selection."""
from __future__ import annotations

import uuid

import pytest

from app.models.course import Course
from app.services.table_import import (
    _group_key,
    _hash_list_key,
    select_active,
    upsert_courses,
)


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _ScalarRows(self._rows)


class _FakeDb:
    def __init__(self) -> None:
        self.rows: list[Course] = []
        self.flush_count = 0

    async def execute(self, _statement):
        return _Result(self.rows)

    def add(self, course: Course) -> None:
        course.id = uuid.uuid4()
        self.rows.append(course)

    async def flush(self) -> None:
        self.flush_count += 1


class FakeCourse:
    def __init__(self, name, md5_list, constraint, sha256_list=None):
        self.name = name
        self.md5_list = md5_list
        self.sha256_list = sha256_list
        self.constraint = constraint
        self.id = None
        self.is_active = True


def test_example_from_doc_picks_gauge_lr2() -> None:
    md5s = ["a", "b", "c", "d"]
    a = FakeCourse("A", md5s, ["grade_mirror", "no_good"])
    b = FakeCourse("B", md5s, ["grade_mirror", "no_speed"])
    c = FakeCourse("C", md5s, ["grade_mirror", "gauge_lr2"])
    assert select_active([a, b, c]) is c


def test_judge_beats_speed() -> None:
    md5s = ["a"]
    x = FakeCourse("X", md5s, ["grade_mirror", "no_good"])
    y = FakeCourse("Y", md5s, ["grade_mirror", "no_speed"])
    assert select_active([x, y]) is x


def test_layout_preference_mirror_over_grade() -> None:
    md5s = ["a"]
    mirror = FakeCourse("M", md5s, ["grade_mirror"])
    grade = FakeCourse("G", md5s, ["grade"])
    random = FakeCourse("R", md5s, ["grade_random"])
    assert select_active([grade, random, mirror]) is mirror


def test_ln_preference_ln_over_cn_over_hcn() -> None:
    md5s = ["a"]
    ln = FakeCourse("LN", md5s, ["ln"])
    cn = FakeCourse("CN", md5s, ["cn"])
    hcn = FakeCourse("HCN", md5s, ["hcn"])
    assert select_active([hcn, cn, ln]) is ln
    assert select_active([hcn, cn]) is cn


def test_speed_prefers_without_no_speed() -> None:
    md5s = ["a"]
    restricted = FakeCourse("A", md5s, ["grade_mirror", "no_speed"])
    normal = FakeCourse("B", md5s, ["grade_mirror"])
    assert select_active([restricted, normal]) is normal


def test_single_group_returns_alone() -> None:
    md5s = ["a"]
    only = FakeCourse("only", md5s, [])
    assert select_active([only]) is only


def test_group_key_keeps_hash_order() -> None:
    assert _hash_list_key(["b", "a"]) != _hash_list_key(["a", "b"])


def test_group_key_falls_back_to_sha256_when_md5_missing() -> None:
    a = FakeCourse("A", [], [], sha256_list=["s1", "s2"])
    b = FakeCourse("B", [], ["no_speed"], sha256_list=["s1", "s2"])
    assert _group_key(a) == _group_key(b)


@pytest.mark.asyncio
async def test_upsert_courses_keeps_constraint_variants_but_only_one_active(monkeypatch) -> None:
    async def noop_fill(db, courses) -> None:
        return None

    monkeypatch.setattr("app.services.table_import._fill_sha256_lists_for_courses", noop_fill)
    db = _FakeDb()
    table_id = uuid.uuid4()
    md5s = ["a" * 32, "b" * 32]

    summary = await upsert_courses(
        db,
        table_id,
        [
            {"name": "A", "md5_list": md5s, "constraint": ["grade_mirror", "no_good"]},
            {"name": "B", "md5_list": md5s, "constraint": ["grade_mirror", "no_speed"]},
            {"name": "C", "md5_list": md5s, "constraint": ["grade_mirror", "gauge_lr2"]},
        ],
    )

    rows = db.rows
    assert summary["inserted"] == 3
    assert len(rows) == 3
    active_names = [row.name for row in rows if row.is_active]
    assert active_names == ["C"]


@pytest.mark.asyncio
async def test_upsert_courses_is_idempotent_for_same_payload(monkeypatch) -> None:
    async def noop_fill(db, courses) -> None:
        return None

    monkeypatch.setattr("app.services.table_import._fill_sha256_lists_for_courses", noop_fill)
    db = _FakeDb()
    table_id = uuid.uuid4()
    payload = [
        {"name": "A", "md5_list": ["a" * 32], "constraint": ["grade"]},
        {"name": "A", "md5_list": ["a" * 32], "constraint": ["grade_mirror"]},
    ]

    first = await upsert_courses(db, table_id, payload)
    second = await upsert_courses(db, table_id, payload)

    rows = db.rows
    assert first["inserted"] == 2
    assert second["inserted"] == 0
    assert second["updated"] == 2
    assert len(rows) == 2
    assert sum(1 for row in rows if row.is_active) == 1


@pytest.mark.asyncio
async def test_upsert_courses_backfills_legacy_constraintless_row(monkeypatch) -> None:
    async def noop_fill(db, courses) -> None:
        return None

    monkeypatch.setattr("app.services.table_import._fill_sha256_lists_for_courses", noop_fill)
    db = _FakeDb()
    table_id = uuid.uuid4()
    legacy = Course(
        name="A",
        source_table_id=table_id,
        md5_list=["a" * 32],
        constraint=[],
        is_active=True,
        dan_title="",
    )
    legacy.id = uuid.uuid4()
    db.rows.append(legacy)

    summary = await upsert_courses(
        db,
        table_id,
        [{"name": "A", "md5_list": ["a" * 32], "constraint": ["grade_mirror"]}],
    )

    assert summary["inserted"] == 0
    assert summary["updated"] == 1
    assert len(db.rows) == 1
    assert db.rows[0].id == legacy.id
    assert db.rows[0].constraint == ["grade_mirror"]
    assert db.rows[0].is_active is True


@pytest.mark.asyncio
async def test_upsert_courses_deactivates_vanished_variant(monkeypatch) -> None:
    async def noop_fill(db, courses) -> None:
        return None

    monkeypatch.setattr("app.services.table_import._fill_sha256_lists_for_courses", noop_fill)
    db = _FakeDb()
    table_id = uuid.uuid4()
    md5s = ["a" * 32]
    await upsert_courses(
        db,
        table_id,
        [
            {"name": "A", "md5_list": md5s, "constraint": ["grade"]},
            {"name": "B", "md5_list": md5s, "constraint": ["grade_mirror"]},
        ],
    )

    summary = await upsert_courses(
        db,
        table_id,
        [{"name": "A", "md5_list": md5s, "constraint": ["grade"]}],
    )

    rows = db.rows
    assert len(rows) == 2
    assert summary["deactivated"] >= 1
    assert [row.name for row in rows if row.is_active] == ["A"]
