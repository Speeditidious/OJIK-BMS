"""Tests for user-driven difficulty table imports."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.admin.views import DifficultyTableAdmin
from app.models.difficulty_table import DifficultyTable, UserFavoriteDifficultyTable
from app.routers.tables import ImportTableRequest, import_table


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
        _ScalarResult(scalar=1),
        _ScalarResult(one_or_none=None),
        _ScalarResult(scalar=0),
    ])
    user = SimpleNamespace(id=uuid.uuid4())

    response = await import_table(ImportTableRequest(url="https://example.com/table.html"), user, db)

    table = next(obj for obj in db.added if isinstance(obj, DifficultyTable))
    favorite = next(obj for obj in db.added if isinstance(obj, UserFavoriteDifficultyTable))
    assert response.id == table.id
    assert response.name == "Imported Table"
    assert response.symbol == "★"
    assert response.song_count == 1
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
    ])
    user = SimpleNamespace(id=uuid.uuid4())

    response = await import_table(ImportTableRequest(url="https://example.com/table.html"), user, db)

    assert response.id == existing.id
    assert response.song_count == 3
    assert [type(obj) for obj in db.added] == [UserFavoriteDifficultyTable]


@pytest.mark.asyncio
async def test_import_table_populates_empty_existing_table(monkeypatch) -> None:
    """A previously registered but empty table should be filled on re-import."""
    existing = DifficultyTable(
        id=uuid.uuid4(),
        name="Empty Table",
        source_url="https://example.com/table.html",
        is_default=False,
        level_order=None,
    )
    table_data = _table_data()

    async def fake_fetch_table(url: str) -> dict[str, Any]:
        return table_data

    async def fake_upsert_fumens(db: Any, table_id: uuid.UUID, songs: list[dict]) -> set[str]:
        return {"md5:" + "a" * 32}

    async def fake_upsert_courses(db: Any, table_id: uuid.UUID, courses: list[dict]) -> None:
        return None

    monkeypatch.setattr("app.parsers.table_fetcher.fetch_table", fake_fetch_table)
    monkeypatch.setattr("app.services.table_import.upsert_fumens", fake_upsert_fumens)
    monkeypatch.setattr("app.services.table_import.upsert_courses", fake_upsert_courses)

    db = _FakeDb([
        _ScalarResult(one_or_none=existing),
        _ScalarResult(scalar=0),
        _ScalarResult(scalar=1),
        _ScalarResult(one_or_none=None),
        _ScalarResult(scalar=0),
    ])
    user = SimpleNamespace(id=uuid.uuid4())

    response = await import_table(ImportTableRequest(url="https://example.com/table.html"), user, db)

    assert response.id == existing.id
    assert response.name == "Imported Table"
    assert response.song_count == 1
    assert existing.level_order == ["1"]
    assert existing.symbol == "★"


@pytest.mark.asyncio
async def test_difficulty_table_admin_actions_redirect_to_real_identity(monkeypatch) -> None:
    """Difficulty table admin actions should redirect to the hyphenated sqladmin identity."""
    delayed: list[Any] = []

    monkeypatch.setattr("app.tasks.table_updater.update_difficulty_table.delay", delayed.append)
    monkeypatch.setattr("app.tasks.table_updater.update_all_difficulty_tables.delay", lambda: delayed.append("all"))
    monkeypatch.setattr("app.services.ranking_config.get_ranking_config", lambda: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr("app.tasks.ranking_calculator.recalculate_all_rankings.delay", lambda: delayed.append("rankings"))

    for action, pks in [
        (DifficultyTableAdmin.sync_selected_tables, "abc"),
        (DifficultyTableAdmin.sync_all_tables, ""),
        (DifficultyTableAdmin.recalculate_rankings, "abc"),
    ]:
        request = _FakeRequest(pks=pks)
        response = await action(DifficultyTableAdmin, request)
        assert response.status_code == 302
        assert request.url_for_calls[-1] == (
            "admin:list",
            {"identity": DifficultyTableAdmin.identity},
        )
        assert DifficultyTableAdmin.identity == "difficulty-table"
