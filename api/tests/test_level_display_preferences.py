from app.services.level_display_preferences import (
    DEFAULT_LEVEL_DISPLAY_PREFERENCES,
    normalize_level_display_preferences,
    normalize_preferences_payload,
)


def test_normalize_level_display_defaults_to_favorites_only() -> None:
    assert DEFAULT_LEVEL_DISPLAY_PREFERENCES == {
        "favorite": True,
        "server_default": False,
        "user_added": False,
        "ojik_custom": False,
    }
    assert normalize_level_display_preferences(None) == DEFAULT_LEVEL_DISPLAY_PREFERENCES


def test_normalize_level_display_ignores_unknown_keys_and_non_bool_values() -> None:
    raw = {
        "favorite": False,
        "server_default": "false",
        "user_added": True,
        "ojik_custom": False,
        "extra": False,
    }
    assert normalize_level_display_preferences(raw) == {
        "favorite": False,
        "server_default": False,
        "user_added": True,
        "ojik_custom": False,
    }


def test_normalize_preferences_payload_normalizes_level_display_only() -> None:
    payload = {
        "score_updates_lamp_include_new_plays": False,
        "level_display": {"favorite": False, "server_default": False},
    }
    assert normalize_preferences_payload(payload) == {
        "score_updates_lamp_include_new_plays": False,
        "level_display": {
            "favorite": False,
            "server_default": False,
            "user_added": False,
            "ojik_custom": False,
        },
    }


def test_normalize_preferences_payload_passes_through_when_no_level_display() -> None:
    payload = {"score_updates_lamp_include_new_plays": False}
    assert normalize_preferences_payload(payload) == payload


from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.routers.fumens import _entry_visible, get_fumen_by_hash


def test_entry_visible_allows_everything_when_filter_is_none() -> None:
    assert _entry_visible(uuid4(), None) is True


def test_entry_visible_rejects_entries_outside_visible_set() -> None:
    visible_id = uuid4()
    hidden_id = uuid4()
    assert _entry_visible(visible_id, {visible_id}) is True
    assert _entry_visible(hidden_id, {visible_id}) is False


@pytest.mark.asyncio
async def test_get_fumen_by_hash_applies_current_user_level_display_filter(monkeypatch) -> None:
    fumen_id = uuid4()
    visible_table_id = uuid4()
    hidden_table_id = uuid4()
    user = SimpleNamespace(id=uuid4(), preferences={"level_display": {"favorite": True, "server_default": False, "user_added": False}})
    db = SimpleNamespace()
    fumen = SimpleNamespace(
        fumen_id=fumen_id,
        md5="a" * 32,
        sha256=None,
        title="Filtered Song",
        artist="Tester",
        bpm_min=None,
        bpm_max=None,
        bpm_main=None,
        notes_total=None,
        total=None,
        notes_n=None,
        notes_ln=None,
        notes_s=None,
        notes_ls=None,
        length=None,
        youtube_url=None,
        file_url=None,
        file_url_diff=None,
    )

    async def fake_get_fumen_by_hash(_hash_value, _db):
        return fumen

    async def fake_resolve_visible_table_ids(_db, current_user):
        assert current_user is user
        return {visible_table_id}

    async def fake_table_entries_map(_db, fumen_ids, visible_table_ids=None):
        assert fumen_ids == [fumen_id]
        assert visible_table_ids == {visible_table_id}
        entries = [
            {"table_id": str(visible_table_id), "level": "sl1"},
            {"table_id": str(hidden_table_id), "level": "sl2"},
        ]
        return {
            fumen_id: [
                entry
                for entry in entries
                if visible_table_ids is None or entry["table_id"] in {str(tid) for tid in visible_table_ids}
            ]
        }

    monkeypatch.setattr("app.routers.fumens._get_fumen_by_hash", fake_get_fumen_by_hash)
    monkeypatch.setattr("app.routers.fumens.resolve_visible_table_ids", fake_resolve_visible_table_ids)
    monkeypatch.setattr("app.routers.fumens._table_entries_map", fake_table_entries_map)

    result = await get_fumen_by_hash("a" * 32, current_user=user, db=db)

    assert result.table_entries == [{"table_id": str(visible_table_id), "level": "sl1"}]
