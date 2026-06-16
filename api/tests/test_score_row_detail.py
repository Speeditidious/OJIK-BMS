"""Tests for score_row_detail: LR2 random seed map loading and arrangement lookup."""
import json
import inspect
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# JSON seed map structure tests (run without importing the module)
# ---------------------------------------------------------------------------

_SEED_MAP_PATH = Path(__file__).parent.parent / "app" / "data" / "lr2_random_seed_map.json"


@pytest.fixture(scope="module")
def seed_map() -> dict:
    with open(_SEED_MAP_PATH) as f:
        return json.load(f)


def test_seed_map_has_5k_and_7k_keys(seed_map):
    assert "5" in seed_map
    assert "7" in seed_map


def test_5k_arrangement_strings_are_5_digits(seed_map):
    for arrangement in seed_map["5"]:
        assert len(arrangement) == 5, f"5K arrangement '{arrangement}' is not 5 digits"
        assert arrangement.isdigit(), f"5K arrangement '{arrangement}' contains non-digits"


def test_7k_arrangement_strings_are_7_digits(seed_map):
    for arrangement in seed_map["7"]:
        assert len(arrangement) == 7, f"7K arrangement '{arrangement}' is not 7 digits"
        assert arrangement.isdigit(), f"7K arrangement '{arrangement}' contains non-digits"


def test_5k_normal_and_mirror_present(seed_map):
    assert "12345" in seed_map["5"], "5K NORMAL arrangement '12345' is missing"
    assert "54321" in seed_map["5"], "5K MIRROR arrangement '54321' is missing"


def test_7k_normal_and_mirror_present(seed_map):
    assert "1234567" in seed_map["7"], "7K NORMAL arrangement '1234567' is missing"
    assert "7654321" in seed_map["7"], "7K MIRROR arrangement '7654321' is missing"


def test_seed_values_are_lists(seed_map):
    for km in ("5", "7"):
        for arrangement, seeds in seed_map[km].items():
            assert isinstance(seeds, list), (
                f"Seeds for keymode {km} arrangement '{arrangement}' is not a list"
            )
            assert len(seeds) >= 1, (
                f"Seeds list for keymode {km} arrangement '{arrangement}' is empty"
            )
            for s in seeds:
                assert isinstance(s, int), (
                    f"Seed {s!r} in keymode {km} arrangement '{arrangement}' is not an int"
                )


def test_no_duplicate_seed_within_keymode(seed_map):
    """Each (keymode, rseed) pair must map to at most one arrangement."""
    for km in ("5", "7"):
        seen: dict[int, str] = {}
        for arrangement, seeds in seed_map[km].items():
            for s in seeds:
                assert s not in seen or seen[s] == arrangement, (
                    f"Duplicate seed {s} in keymode {km}: maps to both "
                    f"'{seen[s]}' and '{arrangement}'"
                )
                seen[s] = arrangement


# ---------------------------------------------------------------------------
# Module-level loader and lookup function tests
# ---------------------------------------------------------------------------

from app.services.score_row_detail import lookup_lr2_arrangement, _load_lr2_seed_index


def test_lookup_known_7k_seed(seed_map):
    """A known 7K seed returns the correct arrangement string."""
    # Pick the first entry from the 7K map
    arrangements_7k = seed_map["7"]
    first_arrangement = next(iter(arrangements_7k))
    first_seed = arrangements_7k[first_arrangement][0]
    result = lookup_lr2_arrangement(7, first_seed)
    assert result == first_arrangement


def test_lookup_known_5k_seed(seed_map):
    """A known 5K seed returns the correct arrangement string."""
    arrangements_5k = seed_map["5"]
    first_arrangement = next(iter(arrangements_5k))
    first_seed = arrangements_5k[first_arrangement][0]
    result = lookup_lr2_arrangement(5, first_seed)
    assert result == first_arrangement


def test_lookup_7k_normal():
    """7K NORMAL arrangement (1234567) is decodable."""
    seed_map = json.loads(_SEED_MAP_PATH.read_text())
    seed = seed_map["7"]["1234567"][0]
    assert lookup_lr2_arrangement(7, seed) == "1234567"


def test_lookup_7k_mirror():
    """7K MIRROR arrangement (7654321) is decodable."""
    seed_map = json.loads(_SEED_MAP_PATH.read_text())
    seed = seed_map["7"]["7654321"][0]
    assert lookup_lr2_arrangement(7, seed) == "7654321"


def test_lookup_5k_normal():
    """5K NORMAL arrangement (12345) is decodable."""
    seed_map = json.loads(_SEED_MAP_PATH.read_text())
    seed = seed_map["5"]["12345"][0]
    assert lookup_lr2_arrangement(5, seed) == "12345"


def test_lookup_5k_mirror():
    """5K MIRROR arrangement (54321) is decodable."""
    seed_map = json.loads(_SEED_MAP_PATH.read_text())
    seed = seed_map["5"]["54321"][0]
    assert lookup_lr2_arrangement(5, seed) == "54321"


def test_lookup_unmapped_seed_returns_none():
    """An unmapped seed returns None."""
    # Use a seed value unlikely to appear in any real map
    assert lookup_lr2_arrangement(7, 999999999) is None
    assert lookup_lr2_arrangement(5, 999999999) is None


def test_lookup_wrong_keymode_returns_none(seed_map):
    """A valid 7K seed with keymode=5 returns None (no cross-mode leakage)."""
    arrangements_7k = seed_map["7"]
    first_arrangement = next(iter(arrangements_7k))
    first_seed = arrangements_7k[first_arrangement][0]
    # This seed is valid for keymode 7, should not match keymode 5
    result_5k = lookup_lr2_arrangement(5, first_seed)
    result_7k = lookup_lr2_arrangement(7, first_seed)
    assert result_7k == first_arrangement
    # The same seed should not cross-map to a 5K arrangement for THIS seed.
    # If by coincidence the seed integer also exists in the 5K map, that is a
    # data coincidence, not a bug — but for the current dataset we assert None
    # to catch any future regression that leaks the 7K index into keymode=5.
    assert result_5k is None, (
        f"Seed {first_seed} (7K arrangement '{first_arrangement}') must not "
        f"resolve in keymode=5; got '{result_5k}'"
    )


def test_multiple_seeds_per_arrangement_supported(tmp_path):
    """A JSON with multiple seeds for one arrangement is loaded correctly."""
    mock_map = {
        "7": {
            "1234567": [100, 200, 300],
        },
        "5": {},
    }
    mock_path = tmp_path / "mock_seed_map.json"
    mock_path.write_text(json.dumps(mock_map))

    with patch("app.services.score_row_detail._SEED_MAP_PATH", mock_path):
        index = _load_lr2_seed_index()

    assert index[("7", 100)] == "1234567"
    assert index[("7", 200)] == "1234567"
    assert index[("7", 300)] == "1234567"


def test_duplicate_seed_raises_value_error(tmp_path):
    """_load_lr2_seed_index raises ValueError when the same seed maps to two different arrangements."""
    mock_map = {
        "7": {
            "1234567": [42],
            "7654321": [42],  # same seed 42, different arrangement
        },
        "5": {},
    }
    mock_path = tmp_path / "bad_seed_map.json"
    mock_path.write_text(json.dumps(mock_map))

    with patch("app.services.score_row_detail._SEED_MAP_PATH", mock_path):
        with pytest.raises(ValueError, match="Duplicate seed assignment"):
            _load_lr2_seed_index()


def test_5k_seed_count(seed_map):
    """At least 120 5K arrangements are loaded."""
    assert len(seed_map["5"]) >= 120


def test_7k_seed_count(seed_map):
    """At least 5000 7K arrangements are loaded."""
    assert len(seed_map["7"]) >= 5000


# ---------------------------------------------------------------------------
# Imports for new functions
# ---------------------------------------------------------------------------

from app.services.score_row_detail import (
    build_course_stages,
    course_option_label,
    decode_arrangement,
    normalize_judgments,
)


# ---------------------------------------------------------------------------
# normalize_judgments — LR2
# ---------------------------------------------------------------------------

def test_lr2_judgment_order():
    """LR2 judgments are returned in pgreat/great/good/bad/poor/miss order."""
    j = {"perfect": 100, "great": 20, "good": 5, "bad": 2, "poor": 1}
    result = normalize_judgments("lr2", j)
    assert result is not None
    keys = [g["key"] for g in result["judgments"]]
    assert keys == ["pgreat", "great", "good", "bad", "poor", "miss"]


def test_lr2_judgment_counts():
    """LR2 judgment counts map correctly from source keys."""
    j = {"perfect": 500, "great": 30, "good": 10, "bad": 3, "poor": 2}
    result = normalize_judgments("lr2", j)
    groups = {g["key"]: g["count"] for g in result["judgments"]}
    assert groups["pgreat"] == 500
    assert groups["great"] == 30
    assert groups["good"] == 10
    assert groups["bad"] == 3
    assert groups["poor"] == 2
    assert groups["miss"] == 0


def test_lr2_judgment_fast_slow_null():
    """LR2 fast and slow values are all None (no early/late data)."""
    j = {"perfect": 100, "great": 20, "good": 5, "bad": 2, "poor": 1}
    result = normalize_judgments("lr2", j)
    for g in result["judgments"]:
        assert g["fast"] is None, f"{g['key']}.fast should be None"
        assert g["slow"] is None, f"{g['key']}.slow should be None"


def test_lr2_fast_slow_totals_null():
    """LR2 fast/slow totals are None."""
    j = {"perfect": 100, "great": 20, "good": 5, "bad": 2, "poor": 1}
    result = normalize_judgments("lr2", j)
    assert result["fast_total_excluding_pgreat"] is None
    assert result["slow_total_excluding_pgreat"] is None


def test_lr2_judgment_none_input():
    """normalize_judgments returns None when judgments is None (LR2)."""
    assert normalize_judgments("lr2", None) is None


# ---------------------------------------------------------------------------
# Course row detail
# ---------------------------------------------------------------------------

def test_course_option_label_decodes_lr2_op_best():
    assert course_option_label("lr2", {"op_best": 20}) == "RANDOM"


def test_course_option_label_decodes_beatoraja_option():
    assert course_option_label("beatoraja", {"option": 1}) == "MIRROR"


def test_course_option_label_returns_none_without_metadata():
    assert course_option_label("beatoraja", None) is None


def test_build_course_stages_prefers_sha256_list_and_preserves_missing_stage():
    course = type("Course", (), {
        "sha256_list": ["sha-1", None, "sha-3"],
        "md5_list": ["md5-1", "md5-2", "md5-3"],
    })()
    rows = [
        {"sha256": "sha-1", "md5": "md5-1", "level": "★1", "title": "First"},
        {"sha256": None, "md5": "md5-2", "level": "★2", "title": "MD5 fallback must not leak"},
        {"sha256": "sha-3", "md5": "md5-3", "level": "★3", "title": "Third"},
    ]

    assert build_course_stages(course, rows) == [
        {"stage": 1, "level": "★1", "title": "First", "fumen_sha256": "sha-1", "fumen_md5": "md5-1", "table_symbol": None},
        {"stage": 2, "level": None, "title": None, "fumen_sha256": None, "fumen_md5": None, "table_symbol": None},
        {"stage": 3, "level": "★3", "title": "Third", "fumen_sha256": "sha-3", "fumen_md5": "md5-3", "table_symbol": None},
    ]


def test_build_course_stages_falls_back_to_md5_list_when_sha256_list_absent():
    course = type("Course", (), {
        "sha256_list": None,
        "md5_list": ["md5-1", "md5-2"],
    })()
    rows = [
        {"sha256": "sha-1", "md5": "md5-1", "level": "▽1", "title": "First"},
        {"sha256": "sha-2", "md5": "md5-2", "level": "▽2", "title": "Second"},
    ]

    assert build_course_stages(course, rows) == [
        {"stage": 1, "level": "▽1", "title": "First", "fumen_sha256": "sha-1", "fumen_md5": "md5-1", "table_symbol": None},
        {"stage": 2, "level": "▽2", "title": "Second", "fumen_sha256": "sha-2", "fumen_md5": "md5-2", "table_symbol": None},
    ]


# ---------------------------------------------------------------------------
# normalize_judgments — Beatoraja
# ---------------------------------------------------------------------------

_BEA_J = {
    "epg": 600, "lpg": 634,
    "egr": 20,  "lgr": 36,
    "egd": 3,   "lgd": 4,
    "ebd": 1,   "lbd": 0,
    "epr": 0,   "lpr": 2,
    "ems": 0,   "lms": 0,
}


def test_bea_judgment_grouped_counts():
    """Beatoraja grouped counts are sums of early+late."""
    result = normalize_judgments("beatoraja", _BEA_J)
    assert result is not None
    groups = {g["key"]: g for g in result["judgments"]}
    assert groups["pgreat"]["count"] == 600 + 634
    assert groups["great"]["count"] == 20 + 36
    assert groups["good"]["count"] == 3 + 4
    assert groups["bad"]["count"] == 1 + 0
    assert groups["poor"]["count"] == 0 + 2
    assert groups["miss"]["count"] == 0 + 0


def test_bea_judgment_fast_slow_values():
    """Beatoraja per-group fast/slow: pgreat.fast=epg, pgreat.slow=lpg."""
    result = normalize_judgments("beatoraja", _BEA_J)
    groups = {g["key"]: g for g in result["judgments"]}
    assert groups["pgreat"]["fast"] == 600   # epg
    assert groups["pgreat"]["slow"] == 634   # lpg
    assert groups["great"]["fast"] == 20     # egr
    assert groups["great"]["slow"] == 36     # lgr
    assert groups["bad"]["fast"] == 1        # ebd
    assert groups["bad"]["slow"] == 0        # lbd


def test_bea_fast_slow_totals_excluding_pgreat():
    """Beatoraja fast/slow totals exclude pgreat."""
    result = normalize_judgments("beatoraja", _BEA_J)
    # fast: egr+egd+ebd+epr+ems = 20+3+1+0+0 = 24
    assert result["fast_total_excluding_pgreat"] == 24
    # slow: lgr+lgd+lbd+lpr+lms = 36+4+0+2+0 = 42
    assert result["slow_total_excluding_pgreat"] == 42


def test_bea_judgment_none_input():
    """normalize_judgments returns None when judgments is None (Beatoraja)."""
    assert normalize_judgments("beatoraja", None) is None


# ---------------------------------------------------------------------------
# decode_arrangement — LR2
# ---------------------------------------------------------------------------

_LR2_7K_NORMAL_OP = 0 * 10   # arrangement_enum=0 → NORMAL
_LR2_7K_MIRROR_OP = 1 * 10   # arrangement_enum=1 → MIRROR
_LR2_7K_RANDOM_OP = 2 * 10   # arrangement_enum=2 → RANDOM
_LR2_7K_SRANDOM_OP = 3 * 10  # arrangement_enum=3 → S-RANDOM

# A known 7K RANDOM seed/arrangement from the seed map
_LR2_7K_RANDOM_SEED = 778
_LR2_7K_RANDOM_ARR = "2561437"  # arrangement for seed=778 in 7K

# A known 5K RANDOM seed
_LR2_5K_RANDOM_SEED = 11168
_LR2_5K_RANDOM_ARR = "34512"


def test_lr2_normal_7k():
    """LR2 7K NORMAL returns identity lanes."""
    result = decode_arrangement("lr2", {"op_best": _LR2_7K_NORMAL_OP, "rseed": 391}, 7)
    assert result["unavailable_reason"] is None
    assert result["option_label"] == "NORMAL"
    assert result["lane_groups"][0]["lanes"] == [1, 2, 3, 4, 5, 6, 7]
    assert result["lane_groups"][0]["side"] == "single"


def test_lr2_mirror_7k():
    """LR2 7K MIRROR returns reversed lanes."""
    result = decode_arrangement("lr2", {"op_best": _LR2_7K_MIRROR_OP, "rseed": 0}, 7)
    assert result["unavailable_reason"] is None
    assert result["option_label"] == "MIRROR"
    assert result["lane_groups"][0]["lanes"] == [7, 6, 5, 4, 3, 2, 1]


def test_lr2_random_7k_mapped():
    """LR2 7K RANDOM with a mapped seed returns the decoded arrangement."""
    result = decode_arrangement("lr2", {"op_best": _LR2_7K_RANDOM_OP, "rseed": _LR2_7K_RANDOM_SEED}, 7)
    assert result["unavailable_reason"] is None
    assert result["option_label"] == "RANDOM"
    expected_lanes = [int(c) for c in _LR2_7K_RANDOM_ARR]
    assert result["lane_groups"][0]["lanes"] == expected_lanes


def test_lr2_random_5k_mapped():
    """LR2 5K RANDOM with a mapped seed returns the decoded arrangement."""
    result = decode_arrangement("lr2", {"op_best": _LR2_7K_RANDOM_OP, "rseed": _LR2_5K_RANDOM_SEED}, 5)
    assert result["unavailable_reason"] is None
    assert result["option_label"] == "RANDOM"
    expected_lanes = [int(c) for c in _LR2_5K_RANDOM_ARR]
    assert result["lane_groups"][0]["lanes"] == expected_lanes


def test_lr2_random_7k_unmapped():
    """LR2 7K RANDOM with an unmapped seed returns lr2_seed_unmapped."""
    result = decode_arrangement("lr2", {"op_best": _LR2_7K_RANDOM_OP, "rseed": 999999999}, 7)
    assert result["unavailable_reason"] == "lr2_seed_unmapped"
    assert result["option_label"] == "RANDOM"


def test_lr2_srandom_static_map_unsupported():
    """LR2 S-RANDOM returns static_map_unsupported."""
    result = decode_arrangement("lr2", {"op_best": _LR2_7K_SRANDOM_OP}, 7)
    assert result["unavailable_reason"] == "static_map_unsupported"
    assert result["option_label"] == "S-RANDOM"


def test_lr2_dp_unsupported():
    """LR2 DP (14K keymode) returns dp_unsupported."""
    result = decode_arrangement("lr2", {"op_best": _LR2_7K_NORMAL_OP}, 14)
    assert result["unavailable_reason"] == "dp_unsupported"


def test_lr2_options_none():
    """LR2 with options=None returns score_metadata_missing."""
    result = decode_arrangement("lr2", None, 7)
    assert result["unavailable_reason"] == "score_metadata_missing"


def test_lr2_keymode_none():
    """LR2 with keymode=None returns keymode_missing."""
    result = decode_arrangement("lr2", {"op_best": _LR2_7K_NORMAL_OP}, None)
    assert result["unavailable_reason"] == "keymode_missing"


# ---------------------------------------------------------------------------
# decode_arrangement — Beatoraja SP
# ---------------------------------------------------------------------------

def test_bea_sp_normal_7k():
    """Beatoraja 7K NORMAL returns identity lanes."""
    result = decode_arrangement("beatoraja", {"option": 0}, 7)
    assert result["unavailable_reason"] is None
    assert result["option_label"] == "NORMAL"
    assert result["lane_groups"][0]["lanes"] == [1, 2, 3, 4, 5, 6, 7]


def test_bea_sp_mirror_7k():
    """Beatoraja 7K MIRROR returns reversed lanes."""
    result = decode_arrangement("beatoraja", {"option": 1}, 7)
    assert result["unavailable_reason"] is None
    assert result["option_label"] == "MIRROR"
    assert result["lane_groups"][0]["lanes"] == [7, 6, 5, 4, 3, 2, 1]


def test_bea_sp_random_fixture_seed_7591322():
    """Beatoraja 7K RANDOM seed=7591322 produces the expected permutation."""
    result = decode_arrangement("beatoraja", {"option": 2, "seed": 7591322}, 7)
    assert result["unavailable_reason"] is None
    assert result["option_label"] == "RANDOM"
    # Pre-computed expected result: java_random_shuffle(7591322, 7)
    assert result["lane_groups"][0]["lanes"] == [5, 3, 4, 7, 6, 1, 2]


def test_bea_sp_random_missing_seed():
    """Beatoraja RANDOM with missing seed returns score_metadata_missing."""
    result = decode_arrangement("beatoraja", {"option": 2}, 7)
    assert result["unavailable_reason"] == "score_metadata_missing"
    assert result["option_label"] == "RANDOM"


def test_bea_sp_srandom_static_map_unsupported():
    """Beatoraja S-RANDOM returns static_map_unsupported."""
    result = decode_arrangement("beatoraja", {"option": 4}, 7)
    assert result["unavailable_reason"] == "static_map_unsupported"
    assert result["option_label"] == "S-RANDOM"


def test_bea_sp_battle_assist_option_unsupported():
    """Beatoraja BATTLE returns assist_option_unsupported."""
    result = decode_arrangement("beatoraja", {"option": 9}, 7)
    assert result["unavailable_reason"] == "assist_option_unsupported"
    assert result["option_label"] == "BATTLE"


def test_bea_sp_battle_as_assist_option_unsupported():
    """Beatoraja BATTLE AS returns assist_option_unsupported."""
    result = decode_arrangement("beatoraja", {"option": 10}, 7)
    assert result["unavailable_reason"] == "assist_option_unsupported"
    assert result["option_label"] == "BATTLE AS"


def test_bea_options_none():
    """Beatoraja with options=None returns score_metadata_missing."""
    result = decode_arrangement("beatoraja", None, 7)
    assert result["unavailable_reason"] == "score_metadata_missing"


def test_bea_keymode_unsupported():
    """Beatoraja with unsupported keymode (e.g., 9 for POPN) returns keymode_unsupported."""
    result = decode_arrangement("beatoraja", {"option": 0}, 9)
    assert result["unavailable_reason"] == "keymode_unsupported"


def test_bea_normal_decodable_without_seed():
    """Beatoraja NORMAL does not require a seed."""
    result = decode_arrangement("beatoraja", {"option": 0}, 7)
    assert result["unavailable_reason"] is None
    assert result["lane_groups"][0]["lanes"] == [1, 2, 3, 4, 5, 6, 7]


def test_bea_mirror_decodable_without_seed():
    """Beatoraja MIRROR does not require a seed."""
    result = decode_arrangement("beatoraja", {"option": 1}, 7)
    assert result["unavailable_reason"] is None
    assert result["lane_groups"][0]["lanes"] == [7, 6, 5, 4, 3, 2, 1]


def test_bea_missing_option_key():
    """Beatoraja options dict without 'option' key returns score_metadata_missing."""
    result = decode_arrangement("beatoraja", {"seed": 12345}, 7)
    assert result["unavailable_reason"] == "score_metadata_missing"


# ---------------------------------------------------------------------------
# decode_arrangement — Beatoraja DP (10K/14K)
# ---------------------------------------------------------------------------

def test_bea_dp_10k_option_seed_unpacking():
    """Beatoraja 10K DP option and seed are unpacked correctly per side."""
    # option_1p=1 (MIRROR), option_2p=2 (RANDOM), double=0 (none)
    # seed_1p=0, seed_2p=12345
    # packed_option = 1 | (2 << 8) | (0 << 16) = 513
    # packed_seed = 0 | (12345 << 32)
    packed_option = 1 | (2 << 8)
    packed_seed = 12345 << 32
    result = decode_arrangement("beatoraja", {"option": packed_option, "seed": packed_seed}, 10)
    assert result["unavailable_reason"] is None
    assert result["double_option_label"] is None
    assert len(result["lane_groups"]) == 2
    # 1P: MIRROR of 5 lanes
    assert result["lane_groups"][0]["side"] == "1p"
    assert result["lane_groups"][0]["option_label"] == "MIRROR"
    assert result["lane_groups"][0]["lanes"] == [5, 4, 3, 2, 1]
    # 2P: RANDOM with seed=12345
    assert result["lane_groups"][1]["side"] == "2p"
    assert result["lane_groups"][1]["option_label"] == "RANDOM"
    # java_random_shuffle(12345, 5)
    assert result["lane_groups"][1]["lanes"] == [5, 3, 4, 1, 2]


def test_bea_dp_flip_ordering():
    """Beatoraja DP with FLIP swaps 1P and 2P before per-side decoding."""
    # option_1p_orig=1 (MIRROR), option_2p_orig=2 (RANDOM), double=1 (FLIP)
    # After FLIP: 1P gets RANDOM (seed_2p=12345), 2P gets MIRROR
    packed_option = 1 | (2 << 8) | (1 << 16)   # = 66049
    packed_seed = 0 | (12345 << 32)             # seed_1p=0, seed_2p=12345
    result = decode_arrangement("beatoraja", {"option": packed_option, "seed": packed_seed}, 10)
    assert result["unavailable_reason"] is None
    assert result["double_option_label"] == "FLIP"
    # After FLIP: 1p = RANDOM (originally 2p's option+seed), 2p = MIRROR (originally 1p's)
    assert result["lane_groups"][0]["side"] == "1p"
    assert result["lane_groups"][0]["option_label"] == "RANDOM"
    assert result["lane_groups"][0]["lanes"] == [5, 3, 4, 1, 2]  # java_random_shuffle(12345, 5)
    assert result["lane_groups"][1]["side"] == "2p"
    assert result["lane_groups"][1]["option_label"] == "MIRROR"
    assert result["lane_groups"][1]["lanes"] == [5, 4, 3, 2, 1]


def test_bea_dp_normal_1p():
    """Beatoraja DP 10K with both sides NORMAL decodes identity for each side."""
    packed_option = 0 | (0 << 8)
    result = decode_arrangement("beatoraja", {"option": packed_option}, 10)
    assert result["unavailable_reason"] is None
    assert result["lane_groups"][0]["lanes"] == [1, 2, 3, 4, 5]
    assert result["lane_groups"][1]["lanes"] == [1, 2, 3, 4, 5]


def test_bea_dp_battle_returns_assist_option_unsupported():
    """Beatoraja DP BATTLE (option_1p=9) returns assist_option_unsupported, not dp_unsupported."""
    packed_option = 9 | (0 << 8)
    result = decode_arrangement("beatoraja", {"option": packed_option}, 10)
    assert result["unavailable_reason"] == "assist_option_unsupported"


def test_bea_dp_battle_as_returns_assist_option_unsupported():
    """Beatoraja DP BATTLE AS (option_2p=10) returns assist_option_unsupported."""
    packed_option = 0 | (10 << 8)
    result = decode_arrangement("beatoraja", {"option": packed_option}, 10)
    assert result["unavailable_reason"] == "assist_option_unsupported"


# ---------------------------------------------------------------------------
# pick_best_per_client unit tests
# ---------------------------------------------------------------------------

from app.services.score_row_detail import pick_best_per_client
from datetime import datetime, timezone
from types import SimpleNamespace


def _make_score(
    client_type: str = "lr2",
    exscore: int | None = None,
    clear_type: int | None = None,
    recorded_at: datetime | None = None,
    synced_at: datetime | None = None,
    **kwargs,
) -> SimpleNamespace:
    """Create a minimal score-like object for pick_best_per_client testing."""
    return SimpleNamespace(
        client_type=client_type,
        exscore=exscore,
        clear_type=clear_type,
        recorded_at=recorded_at,
        synced_at=synced_at,
        **kwargs,
    )


def test_pick_best_empty():
    """Empty input returns empty list."""
    assert pick_best_per_client([]) == []


def test_pick_best_single_row():
    """Single row returns itself."""
    row = _make_score("lr2", exscore=1000)
    result = pick_best_per_client([row])
    assert result == [row]


def test_pick_best_higher_exscore_wins():
    """Row with higher exscore is preferred."""
    low = _make_score("lr2", exscore=500)
    high = _make_score("lr2", exscore=800)
    result = pick_best_per_client([low, high])
    assert len(result) == 1
    assert result[0] is high


def test_pick_best_higher_exscore_wins_reversed_order():
    """Order of input does not affect exscore selection."""
    low = _make_score("lr2", exscore=500)
    high = _make_score("lr2", exscore=800)
    result = pick_best_per_client([high, low])
    assert len(result) == 1
    assert result[0] is high


def test_pick_best_clear_type_tiebreak():
    """When exscore is equal, higher clear_type wins."""
    lower_ct = _make_score("lr2", exscore=1000, clear_type=3)
    higher_ct = _make_score("lr2", exscore=1000, clear_type=5)
    result = pick_best_per_client([lower_ct, higher_ct])
    assert result[0] is higher_ct


def test_pick_best_timestamp_tiebreak():
    """When exscore and clear_type are equal, latest timestamp wins."""
    older = _make_score(
        "lr2", exscore=1000, clear_type=5,
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = _make_score(
        "lr2", exscore=1000, clear_type=5,
        recorded_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    result = pick_best_per_client([older, newer])
    assert result[0] is newer


def test_pick_best_uses_synced_at_when_recorded_at_is_none():
    """synced_at is used as fallback when recorded_at is None."""
    no_recorded = _make_score(
        "lr2", exscore=1000,
        recorded_at=None,
        synced_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    with_older_recorded = _make_score(
        "lr2", exscore=1000,
        recorded_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        synced_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    result = pick_best_per_client([with_older_recorded, no_recorded])
    assert result[0] is no_recorded


def test_pick_best_two_clients_return_two_records():
    """Two different client types each get one representative."""
    lr2_row = _make_score("lr2", exscore=1000)
    bea_row = _make_score("beatoraja", exscore=900)
    result = pick_best_per_client([lr2_row, bea_row])
    assert len(result) == 2
    client_types = {r.client_type for r in result}
    assert client_types == {"lr2", "beatoraja"}


def test_pick_best_none_exscore_loses_to_any_value():
    """A row with exscore=None loses to any numeric exscore."""
    no_score = _make_score("lr2", exscore=None)
    has_score = _make_score("lr2", exscore=1)
    result = pick_best_per_client([no_score, has_score])
    assert result[0] is has_score


# ---------------------------------------------------------------------------
# GET /scores/fumen/{fumen_id}/row-detail API endpoint tests
# ---------------------------------------------------------------------------

import uuid as uuid_mod
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.main import app


def test_exact_score_row_detail_route_is_registered():
    """Exact row expansion must have a dedicated PK-based API route."""
    assert any(
        getattr(route, "path", None) == "/scores/row/{score_id}/row-detail"
        for route in app.routes
    )


@pytest.mark.asyncio
async def test_exact_score_row_detail_returns_only_selected_row(monkeypatch):
    """Exact row expansion serializes one selected score row without aggregate reselection."""
    from app.routers.scores import get_score_row_detail

    user_id = uuid_mod.uuid4()
    fumen_id = uuid_mod.uuid4()
    score = _make_user_score(
        user_id=user_id,
        fumen_id=fumen_id,
        client_type="beatoraja",
        exscore=1777,
        judgments={"epg": 800, "lpg": 50},
        options={"option": 1},
    )
    fumen = SimpleNamespace(fumen_id=fumen_id, keymode=7, notes_total=1000)
    score_result = MagicMock()
    score_result.scalar_one_or_none.return_value = score
    fumen_result = MagicMock()
    fumen_result.one_or_none.return_value = fumen
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[score_result, fumen_result])

    async def fake_resolve_target_user(_user_id, _current_user, _db):
        return SimpleNamespace(id=user_id, is_active=True)

    monkeypatch.setattr("app.routers.scores._resolve_target_user", fake_resolve_target_user)

    result = await get_score_row_detail(
        score_id=score.id,
        user_id=user_id,
        current_user=None,
        db=db,
    )

    assert result.detail_basis == "score_row"
    assert result.fumen_id == str(fumen_id)
    assert [record.score_id for record in result.records] == [str(score.id)]
    assert result.records[0].arrangement["option_label"] == "MIRROR"


def _make_fumen_row(
    fumen_id: uuid_mod.UUID | None = None,
    sha256: str | None = "a" * 64,
    md5: str | None = "b" * 32,
    keymode: int | None = 7,
    notes_total: int | None = 1000,
) -> SimpleNamespace:
    return SimpleNamespace(
        fumen_id=fumen_id or uuid_mod.uuid4(),
        sha256=sha256,
        md5=md5,
        keymode=keymode,
        notes_total=notes_total,
    )


def _make_user_row(
    user_id: uuid_mod.UUID | None = None,
    is_active: bool = True,
) -> SimpleNamespace:
    user = SimpleNamespace(
        id=user_id or uuid_mod.uuid4(),
        is_active=is_active,
    )
    return user


def _make_user_score(
    score_id: uuid_mod.UUID | None = None,
    user_id: uuid_mod.UUID | None = None,
    client_type: str = "beatoraja",
    exscore: int | None = 1000,
    clear_type: int | None = 5,
    min_bp: int | None = 10,
    max_combo: int | None = None,
    rate: float | None = 90.0,
    rank: str | None = "AA",
    play_count: int | None = 5,
    judgments: dict | None = None,
    options: dict | None = None,
    fumen_hash_others: str | None = None,
    recorded_at: datetime | None = None,
    synced_at: datetime | None = None,
    fumen_id: uuid_mod.UUID | None = None,
    fumen_sha256: str | None = None,
    fumen_md5: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=score_id or uuid_mod.uuid4(),
        user_id=user_id or uuid_mod.uuid4(),
        client_type=client_type,
        exscore=exscore,
        clear_type=clear_type,
        min_bp=min_bp,
        max_combo=max_combo,
        rate=rate,
        rank=rank,
        play_count=play_count,
        judgments=judgments,
        options=options,
        fumen_hash_others=fumen_hash_others,
        recorded_at=recorded_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        synced_at=synced_at or datetime(2026, 1, 2, tzinfo=timezone.utc),
        fumen_id=fumen_id,
        fumen_sha256=fumen_sha256,
        fumen_md5=fumen_md5,
        scorehash=None,
    )


def _make_mock_db_for_row_detail(
    fumen_row: SimpleNamespace | None,
    user_row: SimpleNamespace | None,
    score_rows: list[SimpleNamespace],
) -> MagicMock:
    """Build a mock AsyncSession for /scores/fumen/{fumen_id}/row-detail.

    Call sequence:
      1. SELECT Fumen WHERE fumen_id=... → fumen_row (or None)
      2. SELECT User WHERE id=... → user_row (or None)  [only if user_id query param given]
      3. SELECT UserScore WHERE ... → score_rows
    """
    call_count = [0]
    fumen_result = MagicMock()
    if fumen_row is not None:
        fumen_result.one_or_none.return_value = fumen_row
    else:
        fumen_result.one_or_none.return_value = None

    user_result = MagicMock()
    if user_row is not None:
        user_result.scalar_one_or_none.return_value = user_row
    else:
        user_result.scalar_one_or_none.return_value = None

    scores_result = MagicMock()
    scores_result.scalars.return_value.all.return_value = score_rows

    async def _execute(stmt, *args, **kwargs):
        call_count[0] += 1
        try:
            from sqlalchemy.dialects import sqlite as sqlite_dialect
            sql_text = str(stmt.compile(dialect=sqlite_dialect.dialect()))
            sql_lower = sql_text.lower()
            # Detect which query by table/column presence
            if "fumens" in sql_lower and "fumen_id" in sql_lower and call_count[0] == 1:
                return fumen_result
            if "users" in sql_lower and "user_id" in sql_lower or "users" in sql_lower:
                return user_result
            # Default: return scores
            return scores_result
        except Exception:
            return scores_result

    db = MagicMock()
    db.execute = _execute
    return db


@pytest.mark.asyncio
async def test_row_detail_one_record_per_client():
    """Two different client types → two records in response."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)
    user = _make_user_row(user_id=user_id)
    scores = [
        _make_user_score(client_type="beatoraja", exscore=1000, fumen_id=fumen_id),
        _make_user_score(client_type="lr2", exscore=900, fumen_id=fumen_id),
    ]

    # Use a more reliable mock approach: sequential call counter
    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            # Fumen lookup
            result.one_or_none.return_value = fumen
        elif call_idx[0] == 2:
            # User lookup
            result.scalar_one_or_none.return_value = user
        else:
            # Score query
            result.scalars.return_value.all.return_value = scores
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["fumen_id"] == str(fumen_id)
    assert data["keymode"] == 7
    assert data["detail_basis"] == "best_exscore_per_client"
    assert len(data["records"]) == 2
    client_types = {r["client_type"] for r in data["records"]}
    assert client_types == {"beatoraja", "lr2"}


@pytest.mark.asyncio
async def test_row_detail_best_exscore_selected():
    """When multiple rows exist for the same client, the highest exscore is selected."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)
    user = _make_user_row(user_id=user_id)
    best = _make_user_score(client_type="lr2", exscore=1500)
    worse = _make_user_score(client_type="lr2", exscore=800)

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        elif call_idx[0] == 2:
            result.scalar_one_or_none.return_value = user
        else:
            result.scalars.return_value.all.return_value = [worse, best]
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["records"]) == 1
    assert data["records"][0]["exscore"] == 1500


@pytest.mark.asyncio
async def test_row_detail_latest_timestamp_tiebreak():
    """When exscore is equal, the row with the latest timestamp is selected."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)
    user = _make_user_row(user_id=user_id)

    older_score = _make_user_score(
        score_id=uuid_mod.uuid4(),
        client_type="lr2", exscore=1000,
        recorded_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    newer_score = _make_user_score(
        score_id=uuid_mod.uuid4(),
        client_type="lr2", exscore=1000,
        recorded_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        elif call_idx[0] == 2:
            result.scalar_one_or_none.return_value = user
        else:
            result.scalars.return_value.all.return_value = [older_score, newer_score]
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["records"]) == 1
    assert data["records"][0]["score_id"] == str(newer_score.id)


@pytest.mark.asyncio
async def test_row_detail_ignores_play_count_only_latest_tiebreak():
    """A later play-count-only row must not replace the previous record detail row."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id, keymode=7)
    user = _make_user_row(user_id=user_id)

    previous_record = _make_user_score(
        score_id=uuid_mod.uuid4(),
        user_id=user_id,
        fumen_id=fumen_id,
        fumen_sha256="f" * 64,
        client_type="beatoraja",
        exscore=1500,
        clear_type=5,
        min_bp=10,
        max_combo=900,
        play_count=3,
        options={"option": 2},
        recorded_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
    )
    stat_only = _make_user_score(
        score_id=uuid_mod.uuid4(),
        user_id=user_id,
        fumen_id=fumen_id,
        fumen_sha256="f" * 64,
        client_type="beatoraja",
        exscore=1500,
        clear_type=5,
        min_bp=10,
        max_combo=900,
        play_count=4,
        options={"option": 0},
        recorded_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        elif call_idx[0] == 2:
            result.scalar_one_or_none.return_value = user
        else:
            result.scalars.return_value.all.return_value = [stat_only, previous_record]
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["records"]) == 1
    assert data["records"][0]["score_id"] == str(previous_record.id)
    assert data["records"][0]["arrangement"]["option_label"] == "RANDOM"


@pytest.mark.asyncio
async def test_row_detail_course_records_excluded():
    """Rows with fumen_hash_others set (course records) are excluded by the query."""
    # The endpoint passes fumen_hash_others IS NULL as a WHERE condition.
    # We verify: when the DB returns only a course record, the response has 0 records.
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)
    user = _make_user_row(user_id=user_id)

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        elif call_idx[0] == 2:
            result.scalar_one_or_none.return_value = user
        else:
            # Return empty — as the SQL WHERE fumen_hash_others IS NULL filters them out
            result.scalars.return_value.all.return_value = []
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["records"] == []


@pytest.mark.asyncio
async def test_row_detail_fumen_not_found_returns_404():
    """If fumen_id does not exist in DB, endpoint returns 404."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = None  # fumen not found
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_row_detail_inactive_user_returns_404():
    """If the target user is inactive, endpoint returns 404."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)
    inactive_user = _make_user_row(user_id=user_id, is_active=False)

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        else:
            result.scalar_one_or_none.return_value = inactive_user
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_row_detail_missing_user_returns_404():
    """If the target user_id does not exist in DB, endpoint returns 404."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        else:
            result.scalar_one_or_none.return_value = None  # user not found
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_row_detail_no_auth_no_user_id_returns_401():
    """Without authentication and without user_id param, endpoint returns 401."""
    fumen_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/scores/fumen/{fumen_id}/row-detail")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_row_detail_compact_columns_no_full_history():
    """Response records have expected fields and do not include full history payload."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)
    user = _make_user_row(user_id=user_id)
    score = _make_user_score(
        client_type="beatoraja",
        exscore=2345,
        clear_type=5,
        min_bp=12,
        rate=91.23,
        rank="AA",
        play_count=42,
    )

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        elif call_idx[0] == 2:
            result.scalar_one_or_none.return_value = user
        else:
            result.scalars.return_value.all.return_value = [score]
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    record = data["records"][0]

    # Compact expected fields
    assert "score_id" in record
    assert "client_type" in record
    assert "clear_type" in record
    assert "min_bp" in record
    assert "rate" in record
    assert "rank" in record
    assert "exscore" in record
    assert "play_count" in record
    assert "judgment_detail" in record
    assert "arrangement" in record

    # No full history or raw hash fields
    assert "fumen_sha256" not in record
    assert "fumen_md5" not in record
    assert "scorehash" not in record
    assert "user_id" not in record

    assert record["exscore"] == 2345
    assert record["play_count"] == 42


@pytest.mark.asyncio
async def test_row_detail_as_of_parameter_passed_to_query():
    """as_of parameter is accepted; with a past date filtering empty results is valid."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)
    user = _make_user_row(user_id=user_id)

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        elif call_idx[0] == 2:
            result.scalar_one_or_none.return_value = user
        else:
            # Simulate as_of filtering result — no scores before this old date
            result.scalars.return_value.all.return_value = []
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id), "as_of": "2020-01-01"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["records"] == []


@pytest.mark.asyncio
async def test_row_detail_invalid_as_of_returns_400():
    """An invalid as_of date string returns 400."""
    fumen_id = uuid_mod.uuid4()
    user_id = uuid_mod.uuid4()
    fumen = _make_fumen_row(fumen_id=fumen_id)
    user = _make_user_row(user_id=user_id)

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            result.one_or_none.return_value = fumen
        elif call_idx[0] == 2:
            result.scalar_one_or_none.return_value = user
        else:
            result.scalars.return_value.all.return_value = []
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/scores/fumen/{fumen_id}/row-detail",
                params={"user_id": str(user_id), "as_of": "not-a-date"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /scores/me/fumen/{hash_value} — judgment_detail and arrangement fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_history_fumen_rows_include_judgment_detail():
    """GET /scores/me/fumen/{hash} returns judgment_detail for each LR2 score row."""
    user_id = uuid_mod.uuid4()
    user = _make_user_row(user_id=user_id)
    md5 = "b" * 32

    score = _make_user_score(
        user_id=user_id,
        client_type="lr2",
        judgments={"perfect": 100, "great": 10, "good": 2, "bad": 0, "poor": 1},
        options=None,
        fumen_md5=md5,
    )

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            # scores query
            result.scalars.return_value.all.return_value = [score]
        elif call_idx[0] == 2:
            # first_synced_at query
            result.scalar_one_or_none.return_value = None
        else:
            # fumen_meta (notes_total, keymode)
            result.one_or_none.return_value = SimpleNamespace(
                **{"0": 1000, "1": 5}
            )
            # Use a plain tuple so row[0] / row[1] indexing works
            result.one_or_none.return_value = (1000, 5)
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/scores/me/fumen/{md5}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    row = data[0]

    # judgment_detail must be present and non-null for a valid LR2 judgments dict
    assert "judgment_detail" in row
    assert row["judgment_detail"] is not None
    # LR2 maps "perfect" → group key "pgreat"
    first_group = row["judgment_detail"]["judgments"][0]
    assert first_group["key"] == "pgreat"
    assert first_group["count"] == 100
    # LR2 has no fast/slow breakdown
    assert first_group["fast"] is None
    assert first_group["slow"] is None


@pytest.mark.asyncio
async def test_history_fumen_rows_include_arrangement():
    """GET /scores/me/fumen/{hash} returns arrangement for each Beatoraja score row."""
    user_id = uuid_mod.uuid4()
    user = _make_user_row(user_id=user_id)
    md5 = "b" * 32

    score = _make_user_score(
        user_id=user_id,
        client_type="beatoraja",
        judgments=None,
        options={"option": 0, "seed": 0, "mode": 0, "random": 0},  # option=0 = NORMAL
        fumen_md5=md5,
    )

    call_idx = [0]

    async def _execute(stmt, *args, **kwargs):
        call_idx[0] += 1
        result = MagicMock()
        if call_idx[0] == 1:
            # scores query
            result.scalars.return_value.all.return_value = [score]
        elif call_idx[0] == 2:
            # first_synced_at query
            result.scalar_one_or_none.return_value = None
        else:
            # fumen_meta (notes_total, keymode=7)
            result.one_or_none.return_value = (1000, 7)
        return result

    mock_db = MagicMock()
    mock_db.execute = _execute

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/scores/me/fumen/{md5}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    row = data[0]

    # arrangement must be present and non-null
    assert "arrangement" in row
    assert row["arrangement"] is not None
    arrangement = row["arrangement"]
    # option=1 = NORMAL for Beatoraja SP 7K
    assert arrangement["option_label"] == "NORMAL"
    assert arrangement["unavailable_reason"] is None
    # 7K NORMAL: lanes [1, 2, 3, 4, 5, 6, 7]
    assert arrangement["lane_groups"][0]["lanes"] == [1, 2, 3, 4, 5, 6, 7]
