from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.level_display_preferences import (
    DEFAULT_LEVEL_DISPLAY_PREFERENCES,
    normalize_level_display_preferences,
    normalize_preferences_payload,
    resolve_non_regular_hidden_levels,
)
from app.routers.fumens import _entry_visible, get_fumen_by_hash


def test_normalize_level_display_defaults_to_favorites_only() -> None:
    assert DEFAULT_LEVEL_DISPLAY_PREFERENCES == {
        "favorite": True,
        "server_default": False,
        "user_added": False,
        "ojik_custom": False,
        "favorite_show_non_regular": True,
        "server_default_show_non_regular": True,
        "user_added_show_non_regular": True,
        "ojik_custom_show_non_regular": True,
    }
    assert normalize_level_display_preferences(None) == DEFAULT_LEVEL_DISPLAY_PREFERENCES


def test_normalize_level_display_ignores_unknown_keys_and_non_bool_values() -> None:
    raw = {
        "favorite": False,
        "server_default": "false",
        "user_added": True,
        "ojik_custom": False,
        "extra": False,
        "favorite_show_non_regular": False,
        "server_default_show_non_regular": "yes",  # invalid, ignored
    }
    result = normalize_level_display_preferences(raw)
    assert result["favorite"] is False
    assert result["server_default"] is False  # non-bool ignored
    assert result["user_added"] is True
    assert result["ojik_custom"] is False
    assert result["favorite_show_non_regular"] is False  # valid bool accepted
    assert result["server_default_show_non_regular"] is True  # non-bool → default


def test_normalize_preferences_payload_normalizes_level_display_only() -> None:
    payload = {
        "score_updates_lamp_include_new_plays": False,
        "level_display": {
            "favorite": False,
            "server_default": False,
            "favorite_show_non_regular": False,
        },
    }
    result = normalize_preferences_payload(payload)
    assert result["score_updates_lamp_include_new_plays"] is False
    ld = result["level_display"]
    assert ld["favorite"] is False
    assert ld["server_default"] is False
    assert ld["user_added"] is False
    assert ld["ojik_custom"] is False
    assert ld["favorite_show_non_regular"] is False
    assert ld["server_default_show_non_regular"] is True


def test_normalize_preferences_payload_passes_through_when_no_level_display() -> None:
    payload = {"score_updates_lamp_include_new_plays": False}
    assert normalize_preferences_payload(payload) == payload


# ---------------------------------------------------------------------------
# resolve_non_regular_hidden_levels
# ---------------------------------------------------------------------------

class _AsyncResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_resolve_non_regular_hidden_levels_returns_empty_when_all_show() -> None:
    """Returns {} immediately when all show_non_regular prefs are True (default)."""
    user = SimpleNamespace(
        id=uuid4(),
        preferences={
            "level_display": {
                "favorite": True,
                "server_default": True,
                # all show_non_regular default to True
            }
        },
    )
    db = SimpleNamespace()
    # db.execute should never be called — if it is, it'll raise AttributeError
    result = await resolve_non_regular_hidden_levels(db, user)
    assert result == {}


@pytest.mark.asyncio
async def test_resolve_non_regular_hidden_levels_hides_server_default() -> None:
    """Non-regular levels are hidden for server_default tables when pref is False."""
    table_id = uuid4()
    user = SimpleNamespace(
        id=uuid4(),
        preferences={
            "level_display": {
                "favorite": True,
                "server_default": True,
                "server_default_show_non_regular": False,
                # favorite_show_non_regular defaults to True
            }
        },
    )

    call_count = [0]

    async def fake_execute(query):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: favorite table IDs
            return _AsyncResult([])
        # Second call: tables with non_regular_level_order
        row = SimpleNamespace(
            id=table_id,
            non_regular_level_order=["☆11", "☆12"],
            is_default=True,
            source_url=None,
        )
        return _AsyncResult([row])

    db = SimpleNamespace(execute=fake_execute)
    result = await resolve_non_regular_hidden_levels(db, user)
    assert result == {table_id: {"☆11", "☆12"}}


@pytest.mark.asyncio
async def test_resolve_non_regular_levels_shows_when_favorited_overrides_server_default() -> None:
    """Table that is both server_default and favorited: if favorite shows, non-regular is visible."""
    table_id = uuid4()
    user = SimpleNamespace(
        id=uuid4(),
        preferences={
            "level_display": {
                "server_default_show_non_regular": False,
                # favorite_show_non_regular defaults to True
            }
        },
    )

    call_count = [0]

    async def fake_execute(query):
        call_count[0] += 1
        if call_count[0] == 1:
            # favorite table IDs: this table IS favorited
            return _AsyncResult([table_id])
        row = SimpleNamespace(
            id=table_id,
            non_regular_level_order=["☆11"],
            is_default=True,
            source_url=None,
        )
        return _AsyncResult([row])

    db = SimpleNamespace(execute=fake_execute)
    result = await resolve_non_regular_hidden_levels(db, user)
    # Table belongs to both "favorite" (show_non_regular=True) and "server_default" (show_non_regular=False)
    # Most-permissive: favorite says show → result should be empty
    assert result == {}


@pytest.mark.asyncio
async def test_resolve_non_regular_hidden_levels_returns_empty_for_anonymous() -> None:
    """Anonymous user gets defaults (all show_non_regular=True) → empty result."""
    db = SimpleNamespace()
    result = await resolve_non_regular_hidden_levels(db, None)
    assert result == {}


# ---------------------------------------------------------------------------
# _entry_visible (existing helpers, unchanged)
# ---------------------------------------------------------------------------

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
    user = SimpleNamespace(
        id=uuid4(),
        preferences={"level_display": {"favorite": True, "server_default": False, "user_added": False}},
    )
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

    async def fake_resolve_non_regular_hidden_levels(_db, current_user):
        return {}

    async def fake_table_entries_map(_db, fumen_ids, visible_table_ids=None, non_regular_hidden=None):
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
    monkeypatch.setattr("app.routers.fumens.resolve_non_regular_hidden_levels", fake_resolve_non_regular_hidden_levels)
    monkeypatch.setattr("app.routers.fumens._table_entries_map", fake_table_entries_map)

    result = await get_fumen_by_hash("a" * 32, current_user=user, db=db)

    assert result.table_entries == [{"table_id": str(visible_table_id), "level": "sl1"}]
