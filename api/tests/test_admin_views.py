"""Tests for sqladmin model view configuration."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.admin.views import (
    ClientUpdateAnnouncementAdmin,
    DifficultyTableAdmin,
    UserAdmin,
    UserScoreAdmin,
    _clean_level_subset,
    _parse_admin_user_ids,
    _reset_user_play_data,
)
from app.models.score import UserScore

REPO_ROOT = Path(__file__).resolve().parents[2]


def _repo_file(*parts: str) -> Path:
    """Return a repository file path in both host and Docker test layouts."""
    candidates = [
        REPO_ROOT.joinpath(*parts),
        Path(__file__).resolve().parents[1].joinpath(*parts),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


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


def test_client_update_admin_exposes_version_batch_publish_action() -> None:
    """Client Updates admin should expose a version/channel batch publish action."""
    actions = {
        name: value
        for name, value in vars(ClientUpdateAnnouncementAdmin).items()
        if getattr(value, "_action", False)
    }

    assert actions["publish_same_version_updates"]._add_in_list is True
    assert "같은 버전" in actions["publish_same_version_updates"]._label


def test_difficulty_table_admin_exposes_display_level_order_fields() -> None:
    """Difficulty table admin should expose manually managed level order fields."""
    form_fields = {
        getattr(column, "key", column)
        for column in DifficultyTableAdmin.form_columns
    }
    list_fields = {
        getattr(column, "key", column)
        for column in DifficultyTableAdmin.column_list
    }

    assert "display_level_order" in form_fields
    assert "non_regular_level_order" in form_fields
    assert "display_level_order" in list_fields
    assert "non_regular_level_order" in list_fields
    assert "display_level_order" in DifficultyTableAdmin.form_overrides
    assert "non_regular_level_order" in DifficultyTableAdmin.form_overrides
    assert DifficultyTableAdmin.create_template == "sqladmin/difficulty_table_create.html"
    assert DifficultyTableAdmin.edit_template == "sqladmin/difficulty_table_edit.html"


def test_difficulty_table_level_order_template_enhances_select_and_drag_order() -> None:
    """Difficulty table admin template should restrict choices and support drag ordering."""
    template = _repo_file("templates", "sqladmin", "difficulty_table_level_order_fields.html")
    content = template.read_text(encoding="utf-8")

    assert 'document.querySelector(\'[name="level_order"]\')' in content
    assert 'tags: false' in content
    assert 'new Option(level, level' in content
    assert 'choice.setAttribute("draggable", "true")' in content
    assert 'toChip.after(fromChip)' in content


def test_clean_level_subset_keeps_unique_current_levels() -> None:
    """Admin level-order lists should ignore duplicates and stale values."""
    assert _clean_level_subset(["3", "missing", "1", "3"], ["1", "2", "3"]) == ["3", "1"]
    assert _clean_level_subset(["missing"], ["1", "2", "3"]) is None


def test_parse_admin_user_ids_ignores_invalid_values() -> None:
    """sqladmin pks parsing should keep valid UUIDs and skip bad values."""
    valid = uuid.uuid4()

    assert _parse_admin_user_ids(f"{valid},not-a-uuid,") == [valid]


def test_sqladmin_delete_modal_override_guards_missing_related_target() -> None:
    """Delete modal override should preserve bulk-delete URLs from sqladmin JS."""
    template = _repo_file("templates", "sqladmin", "modals", "delete.html")
    content = template.read_text(encoding="utf-8")

    assert "event.relatedTarget || []" in content
    assert 'trigger = window.jQuery("#action-delete")' in content
    assert "isUsableDeleteUrl" in content
    assert 'value !== "undefined"' in content
    assert "selectedCount(pk)" in content
    assert 'removeAttr("data-bs-toggle data-bs-target")' in content
    assert 'safeBulkDeleteUrl' in content
    assert "stopImmediatePropagation" in content
    assert "hasDeletePkParam" in content
    assert "setDeleteButtonUrl" in content
    assert 'prop("disabled", true)' in content


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


def test_fumen_admin_exposes_keymode() -> None:
    """FumenAdmin should expose keymode in list and sortable columns."""
    from app.admin.views import FumenAdmin
    from app.models.fumen import Fumen

    list_keys = {col.key for col in FumenAdmin.column_list}
    sortable_keys = {col.key for col in FumenAdmin.column_sortable_list}
    assert "keymode" in list_keys
    assert "keymode" in sortable_keys


class _FakeDb:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object | None]] = []

    async def execute(self, statement, params=None):
        self.calls.append((statement, params))
