"""Tests for deploy-time rating warm-up helpers."""

import uuid
from datetime import UTC, datetime

import pytest

from scripts.deploy_rating_warmup import (
    run_deploy_rating_warmup,
    select_recent_active_user_ids,
)


class _MappingsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _SelectionSession:
    def __init__(self, rows):
        self._rows = rows
        self.params = None

    async def execute(self, _statement, params):
        self.params = params
        return _MappingsResult(self._rows)


@pytest.mark.asyncio
async def test_select_recent_active_user_ids_returns_uuid_list_sorted_by_latest_sync():
    first_user = uuid.uuid4()
    second_user = uuid.uuid4()
    session = _SelectionSession(
        [
            {"user_id": str(first_user)},
            {"user_id": second_user},
        ]
    )

    user_ids = await select_recent_active_user_ids(session, recent_days=14, limit=25)

    assert user_ids == [first_user, second_user]
    assert session.params is not None
    assert session.params["limit"] == 25
    assert isinstance(session.params["cutoff"], datetime)
    assert session.params["cutoff"].tzinfo == UTC


@pytest.mark.asyncio
async def test_run_deploy_rating_warmup_returns_zero_counts_when_no_users(monkeypatch):
    class _EmptySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    async def fake_init_ranking_config(_db):
        return object()

    async def fake_select_recent_active_user_ids(_db, recent_days, limit):
        assert recent_days == 7
        assert limit == 10
        return []

    class _FakeTaskResult:
        id = "task-123"

    class _FakeTask:
        @staticmethod
        def delay():
            return _FakeTaskResult()

    monkeypatch.setattr("scripts.deploy_rating_warmup.AsyncSessionLocal", lambda: _EmptySession())
    monkeypatch.setattr("scripts.deploy_rating_warmup.init_ranking_config", fake_init_ranking_config)
    monkeypatch.setattr(
        "scripts.deploy_rating_warmup.select_recent_active_user_ids",
        fake_select_recent_active_user_ids,
    )
    monkeypatch.setattr("app.tasks.ranking_calculator.recalculate_all_rankings", _FakeTask)

    result = await run_deploy_rating_warmup(recent_days=7, limit=10)

    assert result["processed"] == 0
    assert result["succeeded"] == 0
    assert result["failed"] == 0
    assert result["last_user_id"] is None
    assert result["enqueue_succeeded"] is True
    assert result["enqueue_task_id"] == "task-123"


@pytest.mark.asyncio
async def test_run_deploy_rating_warmup_continues_after_per_user_failure(monkeypatch):
    first_user = uuid.uuid4()
    second_user = uuid.uuid4()

    class _FakeSession:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            self.rollbacks += 1

    fake_session = _FakeSession()

    async def fake_init_ranking_config(_db):
        return object()

    async def fake_select_recent_active_user_ids(_db, recent_days, limit):
        assert recent_days == 30
        assert limit == 2
        return [first_user, second_user]

    async def fake_recalculate_user(user_id, _config, _db):
        if user_id == first_user:
            raise RuntimeError("boom")
        return None

    class _FakeTaskResult:
        id = "task-456"

    class _FakeTask:
        @staticmethod
        def delay():
            return _FakeTaskResult()

    monkeypatch.setattr("scripts.deploy_rating_warmup.AsyncSessionLocal", lambda: fake_session)
    monkeypatch.setattr("scripts.deploy_rating_warmup.init_ranking_config", fake_init_ranking_config)
    monkeypatch.setattr(
        "scripts.deploy_rating_warmup.select_recent_active_user_ids",
        fake_select_recent_active_user_ids,
    )
    monkeypatch.setattr("scripts.deploy_rating_warmup.recalculate_user", fake_recalculate_user)
    monkeypatch.setattr("app.tasks.ranking_calculator.recalculate_all_rankings", _FakeTask)

    result = await run_deploy_rating_warmup(recent_days=30, limit=2)

    assert result["processed"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["last_user_id"] == str(second_user)
    assert result["enqueue_succeeded"] is True
    assert result["enqueue_task_id"] == "task-456"
    assert fake_session.commits == 1
    assert fake_session.rollbacks == 1


@pytest.mark.asyncio
async def test_run_deploy_rating_warmup_reports_enqueue_failure_without_aborting(monkeypatch):
    only_user = uuid.uuid4()

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def fake_init_ranking_config(_db):
        return object()

    async def fake_select_recent_active_user_ids(_db, recent_days, limit):
        assert recent_days == 3
        assert limit == 1
        return [only_user]

    async def fake_recalculate_user(_user_id, _config, _db):
        return None

    class _BrokenTask:
        @staticmethod
        def delay():
            raise RuntimeError("queue down")

    monkeypatch.setattr("scripts.deploy_rating_warmup.AsyncSessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("scripts.deploy_rating_warmup.init_ranking_config", fake_init_ranking_config)
    monkeypatch.setattr(
        "scripts.deploy_rating_warmup.select_recent_active_user_ids",
        fake_select_recent_active_user_ids,
    )
    monkeypatch.setattr("scripts.deploy_rating_warmup.recalculate_user", fake_recalculate_user)
    monkeypatch.setattr("app.tasks.ranking_calculator.recalculate_all_rankings", _BrokenTask)

    result = await run_deploy_rating_warmup(recent_days=3, limit=1)

    assert result["processed"] == 1
    assert result["succeeded"] == 1
    assert result["failed"] == 0
    assert result["enqueue_succeeded"] is False
    assert result["enqueue_task_id"] is None
