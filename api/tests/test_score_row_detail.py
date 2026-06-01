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
