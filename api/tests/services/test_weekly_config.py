from app.services.weekly_config import load_weekly_config, WeeklyConfigError
from app.routers.weeklies import _weekly_avatar_url, _weekly_dan_table_slugs


def test_load_returns_categories_in_order():
    cfg = load_weekly_config()
    keys = [c.key for c in cfg.categories]
    assert keys == sorted(keys, key=lambda k: {c.key: c.order for c in cfg.categories}[k])
    assert "aery" in keys
    assert "stellaverse" in keys
    assert "balgwang" in keys


def test_bracket_pick_count_defaults():
    cfg = load_weekly_config()
    aery = cfg.category("aery")
    starter = aery.bracket("starter")
    assert starter.pick_count == 7


def test_aery_level_ranges_match_imported_level_labels():
    cfg = load_weekly_config()
    aery = cfg.category("aery")
    assert aery.bracket("starter").selectors[0].level_range == ("LEVEL 1", "LEVEL 11")
    assert aery.bracket("novice").selectors[0].level_range == ("LEVEL 12", "LEVEL 15")
    assert aery.bracket("intermediate").selectors[0].level_range == ("LEVEL 15+", "LEVEL 17")
    assert aery.bracket("advanced").selectors[0].level_range == ("LEVEL 17+", "LEVEL 18")
    assert aery.bracket("expert").selectors[0].level_range == ("LEVEL 18+", "LEVEL 19")
    assert aery.bracket("master").selectors[0].level_range == ("LEVEL 19+", "LEVEL 20+")


def test_multi_table_bracket_has_multiple_selectors():
    cfg = load_weekly_config()
    diamond = cfg.category("balgwang").bracket("diamond")
    assert len(diamond.selectors) == 3
    assert {s.table for s in diamond.selectors} == {"balgwang", "new_balgwang", "overjoy"}


def test_new_balgwang_obsidian_uses_existing_level_label():
    cfg = load_weekly_config()
    obsidian = cfg.category("balgwang").bracket("obsidian")
    new_balgwang_selector = next(s for s in obsidian.selectors if s.table == "new_balgwang")
    assert new_balgwang_selector.levels == ("24",)


def test_rollover_settings():
    cfg = load_weekly_config()
    assert cfg.settings.timezone == "Asia/Seoul"
    assert cfg.settings.rollover_day_of_week == "mon"
    assert cfg.settings.rollover_hour == 4


def test_unknown_category_raises():
    cfg = load_weekly_config()
    try:
        cfg.category("nope")
        assert False, "expected WeeklyConfigError"
    except WeeklyConfigError:
        pass


def test_weekly_dan_tables_follow_category_dan_systems():
    assert _weekly_dan_table_slugs("aery", "starter") == ["aery"]
    assert _weekly_dan_table_slugs("stellaverse", "sr_traveler") == ["satellite", "stella"]
    assert _weekly_dan_table_slugs("stellaverse", "sl_traveler") == ["satellite", "stella"]
    assert _weekly_dan_table_slugs("stellaverse", "st_traveler") == ["satellite", "stella"]
    assert _weekly_dan_table_slugs("balgwang", "dirt") == ["balgwang", "new_balgwang", "overjoy"]
    assert _weekly_dan_table_slugs("balgwang", "wtf") == ["balgwang", "new_balgwang", "overjoy"]


def test_weekly_avatar_url_matches_ranking_fallback_order():
    assert _weekly_avatar_url("/uploads/avatars/me.png", "123", "hash", None) == "/uploads/avatars/me.png"
    assert _weekly_avatar_url(None, "123", "a_hash", None) == "https://cdn.discordapp.com/avatars/123/a_hash.gif"
    assert _weekly_avatar_url(None, "123", "hash", None) == "https://cdn.discordapp.com/avatars/123/hash.png"
    assert _weekly_avatar_url(None, "123", None, "https://cdn.example/avatar.png") == "https://cdn.example/avatar.png"
