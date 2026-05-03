"""Tests for client sync batching metadata."""

import pytest

from ojikbms_client import sync as sync_mod


class _FakeAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeResponse:
    status_code = 200
    text = ""

    def json(self) -> dict:
        return {"synced_scores": 1, "inserted_scores": 1, "errors": []}


@pytest.mark.asyncio
async def test_sync_scores_marks_only_last_batch_as_final(monkeypatch) -> None:
    """Only the last score batch should trigger server-side ranking recalculation."""
    payloads: list[dict] = []

    async def fake_request(_client, _method, _url, *, api_url, json):
        payloads.append(json)
        return _FakeResponse()

    monkeypatch.setattr(sync_mod, "_make_client", lambda **_kwargs: _FakeAsyncClient())
    monkeypatch.setattr(sync_mod, "get_api_url", lambda: "http://api.test")
    monkeypatch.setattr(sync_mod, "make_authenticated_request", fake_request)
    monkeypatch.setattr(sync_mod, "update_last_synced_at", lambda: None)

    scores = [{"client_type": "lr2", "fumen_md5": str(i).zfill(32)} for i in range(1001)]

    await sync_mod.sync_scores(scores)

    assert [payload["is_final_batch"] for payload in payloads] == [False, False, True]
    assert [payload["has_previous_score_changes"] for payload in payloads] == [False, True, True]
