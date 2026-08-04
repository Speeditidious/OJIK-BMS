from app.services.weekly_config import load_weekly_config, WeeklyConfigError
from app.routers.weeklies import _weekly_avatar_url, _weekly_dan_table_slugs


def test_load_returns_categories_in_order():
    cfg = load_weekly_config()
    keys = [c.key for c in cfg.categories]
    assert keys == sorted(keys, key=lambda k: {c.key: c.order for c in cfg.categories}[k])
    assert "5aery" in keys
    assert "stellaverse" in keys
    assert "balgwang" in keys


def test_bracket_pick_count_defaults_to_two():
    cfg = load_weekly_config()
    five_aery = cfg.category("5aery")
    starter = five_aery.bracket("starter")
    assert starter.pick_count == 2


def test_aery_level_ranges_match_imported_level_labels():
    cfg = load_weekly_config()
    five_aery = cfg.category("5aery")
    assert five_aery.bracket("starter").selectors[0].level_range == ("LEVEL 1", "LEVEL 11")
    assert five_aery.bracket("novice").selectors[0].level_range == ("LEVEL 12", "LEVEL 15")
    assert five_aery.bracket("intermediate").selectors[0].level_range == ("LEVEL 15+", "LEVEL 17")
    assert five_aery.bracket("advanced").selectors[0].level_range == ("LEVEL 17+", "LEVEL 18")
    assert five_aery.bracket("expert").selectors[0].level_range == ("LEVEL 18+", "LEVEL 19")
    assert five_aery.bracket("master").selectors[0].level_range == ("LEVEL 19+", "LEVEL 20+")


def test_balgwang_category_splits_tables_into_groups():
    cfg = load_weekly_config()
    category = cfg.category("balgwang")
    groups = {b.group for b in category.brackets}
    assert groups == {"発狂", "NEW GENERATION 発狂", "OVERJOY"}

    for bracket in category.brackets:
        tables = {s.table for s in bracket.selectors}
        if bracket.group == "発狂":
            assert tables == {"balgwang"}
        elif bracket.group == "NEW GENERATION 発狂":
            assert tables == {"new_balgwang"}
        elif bracket.group == "OVERJOY":
            assert tables == {"overjoy"}


def test_new_balgwang_upper_ranges_are_split_without_missing_label():
    cfg = load_weekly_config()
    category = cfg.category("balgwang")
    assert category.bracket("ng_diamond").selectors[0].level_range == ("21", "22")
    assert category.bracket("ng_obsidian").selectors[0].level_range == ("23", "24")


def test_balgwang_upper_ranges_are_split_at_twenty_three():
    cfg = load_weekly_config()
    category = cfg.category("balgwang")
    assert category.bracket("bg_diamond").selectors[0].level_range == ("21", "22")
    assert category.bracket("bg_obsidian").selectors[0].level_range == ("23", "25")


def test_overjoy_group_keeps_existing_level_ranges():
    cfg = load_weekly_config()
    category = cfg.category("balgwang")
    assert category.bracket("oj_diamond").selectors[0].level_range == ("0", "3")
    assert category.bracket("oj_obsidian").selectors[0].level_range == ("4", "5")
    assert category.bracket("oj_wtf").selectors[0].level_range == ("6", "8")


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
    assert _weekly_dan_table_slugs("5aery", "starter") == ["5aery"]
    assert _weekly_dan_table_slugs("stellaverse", "sr_traveler") == ["satellite", "stella"]
    assert _weekly_dan_table_slugs("stellaverse", "sl_traveler") == ["satellite", "stella"]
    assert _weekly_dan_table_slugs("stellaverse", "st_traveler") == ["satellite", "stella"]
    assert _weekly_dan_table_slugs("balgwang", "bg_dirt") == ["balgwang", "new_balgwang", "overjoy"]
    assert _weekly_dan_table_slugs("balgwang", "oj_wtf") == ["balgwang", "new_balgwang", "overjoy"]


def test_weekly_avatar_url_matches_ranking_fallback_order():
    assert _weekly_avatar_url("/uploads/avatars/me.png", "123", "hash", None) == "/uploads/avatars/me.png"
    assert _weekly_avatar_url(None, "123", "a_hash", None) == "https://cdn.discordapp.com/avatars/123/a_hash.gif"
    assert _weekly_avatar_url(None, "123", "hash", None) == "https://cdn.discordapp.com/avatars/123/hash.png"
    assert _weekly_avatar_url(None, "123", None, "https://cdn.example/avatar.png") == "https://cdn.example/avatar.png"
