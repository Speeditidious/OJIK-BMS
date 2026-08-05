"""Tests for the `/activity/recent` Redis response cache.

The cache helpers in `app.routers.activity` are exercised directly against a
fake Redis client rather than through the HTTP layer, because what matters is
(a) the key shape, (b) the round-trip, and (c) that *every* Redis failure mode
degrades to an uncached response instead of a 500. There is no reachable Redis
in the test environment, so the client is injected via `_get_redis`.
"""
from __future__ import annotations

import json

import pytest

from app.routers import activity

pytestmark = pytest.mark.asyncio


class _FakeRedis:
    """Minimal async stand-in for `redis.asyncio.Redis` (get/set only)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, int]] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append((key, ex))


class _BrokenRedis:
    """Stand-in for an unreachable Redis: every command raises."""

    async def get(self, key: str):
        raise ConnectionError("Error 111 connecting to redis:6379. Connection refused.")

    async def set(self, key: str, value: str, ex: int | None = None):
        raise ConnectionError("Error 111 connecting to redis:6379. Connection refused.")


async def test_cache_key_shape_matches_plan():
    assert activity._recent_cache_key(10, 1) == "activity:recent:10:1"
    assert activity._recent_cache_key(25, 3) == "activity:recent:25:3"


async def test_cache_set_then_get_round_trips_with_ttl(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(activity, "_get_redis", lambda: fake)

    payload = {"items": [], "window_days": 30, "total_count": 0, "page": 1}
    await activity._cache_set("activity:recent:10:", payload)

    assert fake.set_calls == [("activity:recent:10:", activity._RECENT_CACHE_TTL_SECONDS)]
    assert await activity._cache_get("activity:recent:10:") == payload


async def test_cache_get_returns_none_on_miss(monkeypatch):
    monkeypatch.setattr(activity, "_get_redis", lambda: _FakeRedis())
    assert await activity._cache_get("activity:recent:10:") is None


async def test_cache_fails_open_when_redis_unreachable(monkeypatch):
    """An unreachable Redis must degrade to a cache miss, never raise."""
    monkeypatch.setattr(activity, "_get_redis", lambda: _BrokenRedis())

    assert await activity._cache_get("activity:recent:10:") is None
    # Must not raise.
    await activity._cache_set("activity:recent:10:", {"items": []})


async def test_cache_fails_open_when_client_cannot_be_created(monkeypatch):
    monkeypatch.setattr(activity, "_get_redis", lambda: None)

    assert await activity._cache_get("activity:recent:10:") is None
    await activity._cache_set("activity:recent:10:", {"items": []})


async def test_corrupt_cached_payload_is_treated_as_miss(monkeypatch):
    fake = _FakeRedis()
    fake.store["activity:recent:10:"] = "not-json{"
    monkeypatch.setattr(activity, "_get_redis", lambda: fake)

    assert await activity._cache_get("activity:recent:10:") is None


async def test_cached_payload_deserializes_into_response_model(monkeypatch):
    """A cached payload must reconstruct a valid `RecentActivityResponse`.

    Guards the `RecentActivityResponse(**cached)` path in the endpoint against
    a future field addition that `model_dump()` would emit but the model could
    not round-trip.
    """
    fake = _FakeRedis()
    monkeypatch.setattr(activity, "_get_redis", lambda: fake)

    original = activity.RecentActivityResponse(
        items=[
            activity.RecentActivityItem(
                id="e1",
                user_id="u1",
                username="alice",
                avatar_url=None,
                is_admin=False,
                synced_at="2026-08-05T00:00:00",
                sync_date="2026-08-05",
                updated_client_types=["lr2"],
            )
        ],
        window_days=30,
        total_count=1,
        page=1,
    )
    await activity._cache_set("activity:recent:10:", original.model_dump())

    cached = await activity._cache_get("activity:recent:10:")
    assert activity.RecentActivityResponse(**cached) == original


async def test_stored_payload_is_json_serializable_text(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(activity, "_get_redis", lambda: fake)
    await activity._cache_set("k", {"a": 1})
    assert json.loads(fake.store["k"]) == {"a": 1}
