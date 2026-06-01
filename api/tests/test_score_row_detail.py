"""Tests for score_row_detail: LR2 random seed map loading and arrangement lookup."""
import json
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

from app.services.score_row_detail import normalize_judgments, decode_arrangement


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
