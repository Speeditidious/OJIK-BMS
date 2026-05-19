"""Tests for user-driven difficulty table imports."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.admin.views import DifficultyTableAdmin
from app.models.difficulty_table import DifficultyTable, UserFavoriteDifficultyTable
from app.routers.tables import ImportTableRequest, import_table
from app.services.table_import import _normalize_song_rows


class _ScalarResult:
    def __init__(self, *, one_or_none: Any = None, scalar: Any = None) -> None:
        self._one_or_none = one_or_none
        self._scalar = scalar

    def scalar_one_or_none(self) -> Any:
        return self._one_or_none

    def scalar(self) -> Any:
        return self._scalar


class _FakeDb:
    def __init__(self, execute_results: list[_ScalarResult]) -> None:
        self.execute_results = execute_results
        self.added: list[Any] = []
        self.executed: list[Any] = []
        self.flush_count = 0
        self.commit_count = 0
        self.refresh_count = 0

    async def execute(self, statement: Any) -> _ScalarResult:
        self.executed.append(statement)
        return self.execute_results.pop(0)

    def add(self, obj: Any) -> None:
        if isinstance(obj, DifficultyTable) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, obj: Any) -> None:
        self.refresh_count += 1


class _FakeRequest:
    def __init__(self, pks: str = "") -> None:
        self.query_params = {"pks": pks}
        self.session = {"admin_user_id": str(uuid.uuid4())}
        self.url_for_calls: list[tuple[str, dict[str, Any]]] = []

    def url_for(self, name: str, **kwargs: Any) -> str:
        self.url_for_calls.append((name, kwargs))
        if name == "admin:details":
            return f"/admin/{kwargs['identity']}/details/{kwargs['pk']}"
        return f"/admin/{kwargs['identity']}/list"


def _table_data() -> dict[str, Any]:
    return {
        "header": {"name": "Imported Table", "symbol": "★"},
        "level_order": ["1"],
        "songs": [
            {
                "md5": "a" * 32,
                "title": "Song A",
                "artist": "Composer",
                "level": "1",
            }
        ],
        "courses": [{"name": "Course A", "md5_list": ["a" * 32]}],
        "symbol": "★",
    }


def test_normalize_song_rows_decodes_html_entities_in_display_text() -> None:
    """Difficulty table imports should store literal display text, not HTML entities."""

    rows = _normalize_song_rows(
        [
            {
                "md5": "c" * 32,
                "title": "lack &quot;0&quot; clock",
                "artist": "Alice &amp; Bob",
                "name_diff": "obj &quot;Another&quot;",
                "level": "1",
            }
        ]
    )

    assert rows[0]["title"] == 'lack "0" clock'
    assert rows[0]["artist"] == 'Alice & Bob / obj: obj "Another"'


@pytest.mark.asyncio
async def test_import_table_populates_new_table_immediately(monkeypatch) -> None:
    """A new import should create the table, favorite, fumens, and courses."""
    table_data = _table_data()
    upserted: dict[str, Any] = {}

    async def fake_fetch_table(url: str) -> dict[str, Any]:
        upserted["url"] = url
        return table_data

    async def fake_upsert_fumens(db: Any, table_id: uuid.UUID, songs: list[dict]) -> set[str]:
        upserted["fumens"] = (table_id, songs)
        return {"md5:" + "a" * 32}

    async def fake_upsert_courses(db: Any, table_id: uuid.UUID, courses: list[dict]) -> None:
        upserted["courses"] = (table_id, courses)

    monkeypatch.setattr("app.parsers.table_fetcher.fetch_table", fake_fetch_table)
    monkeypatch.setattr("app.services.table_import.upsert_fumens", fake_upsert_fumens)
    monkeypatch.setattr("app.services.table_import.upsert_courses", fake_upsert_courses)

    db = _FakeDb([
        _ScalarResult(one_or_none=None),
        _ScalarResult(one_or_none=None),
        _ScalarResult(scalar=0),
        _ScalarResult(scalar=0),
        _ScalarResult(scalar=1),
        _ScalarResult(one_or_none=None),
        _ScalarResult(scalar=0),
        _ScalarResult(scalar=1),
        _ScalarResult(scalar=0),
    ])
    user = SimpleNamespace(id=uuid.uuid4())

    response = await import_table(ImportTableRequest(url="https://example.com/table.html"), user, db)

    table = next(obj for obj in db.added if isinstance(obj, DifficultyTable))
    favorite = next(obj for obj in db.added if isinstance(obj, UserFavoriteDifficultyTable))
    assert response.outcome == "created"
    assert response.table.id == table.id
    assert response.table.name == "Imported Table"
    assert response.table.symbol == "★"
    assert response.table.song_count == 1
    assert table.level_order == ["1"]
    assert favorite.user_id == user.id
    assert favorite.table_id == table.id
    assert upserted["fumens"] == (table.id, table_data["songs"])
    assert upserted["courses"] == (table.id, table_data["courses"])


@pytest.mark.asyncio
async def test_import_table_reuses_populated_existing_table_without_refetch(monkeypatch) -> None:
    """A populated existing URL should only ensure the user's favorite row."""
    existing = DifficultyTable(
        id=uuid.uuid4(),
        name="Existing Table",
        symbol="ex",
        source_url="https://example.com/table.html",
        is_default=False,
        level_order=["1"],
    )

    async def fail_fetch_table(url: str) -> dict[str, Any]:
        raise AssertionError("populated existing table should not be fetched")

    monkeypatch.setattr("app.parsers.table_fetcher.fetch_table", fail_fetch_table)

    db = _FakeDb([
        _ScalarResult(one_or_none=existing),
        _ScalarResult(scalar=3),
        _ScalarResult(one_or_none=None),
        _ScalarResult(scalar=0),
        _ScalarResult(scalar=0),
        _ScalarResult(scalar=0),
    ])
    user = SimpleNamespace(id=uuid.uuid4())

    response = await import_table(ImportTableRequest(url="https://example.com/table.html"), user, db)

    assert response.outcome == "duplicate"
    assert response.table.id == existing.id
    assert response.table.song_count == 3
    assert any(isinstance(obj, UserFavoriteDifficultyTable) for obj in db.added)


@pytest.mark.asyncio
async def test_import_table_treats_empty_existing_table_as_duplicate_without_refetch(monkeypatch) -> None:
    """Duplicate imports should not fetch external URLs, even if the DB row is incomplete."""
    existing = DifficultyTable(
        id=uuid.uuid4(),
        name="Empty Table",
        source_url="https://example.com/table.html",
        is_default=False,
        level_order=None,
    )

    async def fail_fetch_table(url: str) -> dict[str, Any]:
        raise AssertionError("duplicate import should not fetch external URLs")

    monkeypatch.setattr("app.parsers.table_fetcher.fetch_table", fail_fetch_table)

    db = _FakeDb([
        _ScalarResult(one_or_none=existing),
        _ScalarResult(scalar=0),
        _ScalarResult(one_or_none=None),
        _ScalarResult(scalar=0),
        _ScalarResult(scalar=0),
        _ScalarResult(scalar=0),
    ])
    user = SimpleNamespace(id=uuid.uuid4())

    response = await import_table(ImportTableRequest(url="https://example.com/table.html"), user, db)

    assert response.outcome == "duplicate"
    assert response.table.id == existing.id
    assert response.table.song_count == 0
    assert existing.level_order is None


@pytest.mark.asyncio
async def test_difficulty_table_admin_actions_redirect_to_real_identity(monkeypatch) -> None:
    """Difficulty table admin actions should redirect to the hyphenated sqladmin identity."""
    delayed: list[Any] = []
    created_logs: list[dict[str, Any]] = []

    class _TaskResult:
        id = "task-id"

    async def fake_create_log(**kwargs: Any) -> uuid.UUID:
        created_logs.append(kwargs)
        return uuid.uuid4()

    async def fake_mark_task_id(log_id: uuid.UUID, celery_task_id: str) -> None:
        created_logs.append({"marked": str(log_id), "task": celery_task_id})

    def fake_delay(*args: Any, **kwargs: Any) -> _TaskResult:
        delayed.append((args, kwargs))
        return _TaskResult()

    monkeypatch.setattr("app.services.admin_action_log.create_log", fake_create_log)
    monkeypatch.setattr("app.services.admin_action_log.mark_task_id", fake_mark_task_id)
    monkeypatch.setattr("app.tasks.table_updater.update_difficulty_table.delay", fake_delay)
    monkeypatch.setattr("app.tasks.table_updater.update_all_difficulty_tables.delay", fake_delay)
    monkeypatch.setattr("app.services.ranking_config.get_ranking_config", lambda: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr("app.tasks.ranking_calculator.recalculate_all_rankings.delay", fake_delay)

    for action, pks in [
        (DifficultyTableAdmin.sync_selected_tables, "abc"),
        (DifficultyTableAdmin.sync_all_tables, ""),
        (DifficultyTableAdmin.recalculate_rankings, "abc"),
    ]:
        request = _FakeRequest(pks=pks)
        response = await action(DifficultyTableAdmin, request)
        assert response.status_code == 302
        assert request.url_for_calls[-1][0] == "admin:details"
        assert request.url_for_calls[-1][1]["identity"] == "admin-action-log"
        assert DifficultyTableAdmin.identity == "difficulty-table"
    assert delayed
    assert created_logs
