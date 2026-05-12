"""Tests for sqladmin model view configuration."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.admin.views import (
    UserAdmin,
    UserScoreAdmin,
    _parse_admin_user_ids,
    _reset_user_play_data,
)
from app.models.score import UserScore

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_user_score_admin_searches_every_column() -> None:
    """User Scores admin search should cover every stored score field."""
    searchable_keys = {
        column.key for column in UserScoreAdmin.column_searchable_list
    }
    model_keys = {column.key for column in UserScore.__table__.columns}

    assert searchable_keys == model_keys


def test_user_admin_exposes_per_client_reset_actions() -> None:
    """Users admin should expose whole-client and per-client reset actions."""
    actions = {
        name: value
        for name, value in vars(UserAdmin).items()
        if getattr(value, "_action", False)
    }

    assert actions["reset_play_data"]._label == "플레이 데이터 초기화"
    assert actions["reset_lr2_play_data"]._label == "LR2 플레이 데이터 초기화"
    assert actions["reset_beatoraja_play_data"]._label == "Beatoraja 플레이 데이터 초기화"
    assert actions["reset_lr2_play_data"]._add_in_list is True
    assert actions["reset_beatoraja_play_data"]._add_in_detail is True


def test_parse_admin_user_ids_ignores_invalid_values() -> None:
    """sqladmin pks parsing should keep valid UUIDs and skip bad values."""
    valid = uuid.uuid4()

    assert _parse_admin_user_ids(f"{valid},not-a-uuid,") == [valid]


def test_sqladmin_delete_modal_override_guards_missing_related_target() -> None:
    """Delete modal override should preserve bulk-delete URLs from sqladmin JS."""
    template = REPO_ROOT / "api" / "templates" / "sqladmin" / "modals" / "delete.html"
    content = template.read_text(encoding="utf-8")

    assert "event.relatedTarget || []" in content
    assert 'trigger = window.jQuery("#action-delete")' in content
    assert "isUsableDeleteUrl" in content
    assert 'value !== "undefined"' in content
    assert "selectedCount(pk)" in content


@pytest.mark.asyncio
async def test_client_play_data_reset_scopes_deletes_and_first_sync_key() -> None:
    """Per-client reset should preserve other client data and remove one first_sync key."""
    user_id = uuid.uuid4()
    db = _FakeDb()

    await _reset_user_play_data(db, user_id, "lr2")

    assert len(db.calls) == 3
    score_delete = str(db.calls[0][0])
    stats_delete = str(db.calls[1][0])
    first_sync_update = str(db.calls[2][0])
    first_sync_params = db.calls[2][1]

    assert "DELETE FROM user_scores" in score_delete
    assert "user_scores.client_type" in score_delete
    assert "DELETE FROM user_player_stats" in stats_delete
    assert "user_player_stats.client_type" in stats_delete
    assert "first_synced_at - CAST(:client_type AS text)" in first_sync_update
    assert first_sync_params == {"uid": str(user_id), "client_type": "lr2"}


class _FakeDb:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object | None]] = []

    async def execute(self, statement, params=None):
        self.calls.append((statement, params))
