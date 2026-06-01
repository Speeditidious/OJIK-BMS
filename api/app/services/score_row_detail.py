"""Score row detail service: judgment normalization and arrangement decoding.

LR2 random seed data is derived from LR2HackBox
(https://github.com/MatVeiQaaa/LR2HackBox), licensed under the MIT License.
See api/app/data/LR2HackBox-MIT-LICENSE.txt for the full license text.
"""
import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"
_SEED_MAP_PATH = _DATA_DIR / "lr2_random_seed_map.json"


def _load_lr2_seed_index() -> dict[tuple[str, int], str]:
    """Load the LR2 seed map and build a (keymode, rseed) -> arrangement reverse index.

    Raises ValueError on duplicate (keymode, rseed) assignments to different arrangements.
    """
    with open(_SEED_MAP_PATH) as f:
        seed_map: dict[str, dict[str, list[int]]] = json.load(f)

    index: dict[tuple[str, int], str] = {}
    for keymode_str, arrangements in seed_map.items():
        for arrangement, seeds in arrangements.items():
            for seed in seeds:
                key = (keymode_str, seed)
                if key in index and index[key] != arrangement:
                    raise ValueError(
                        f"Duplicate seed assignment: keymode={keymode_str} rseed={seed} "
                        f"maps to both '{index[key]}' and '{arrangement}'"
                    )
                index[key] = arrangement
    return index


# Module-level reverse index: (keymode_str, rseed) -> arrangement_string
# Loaded once at process import from lr2_random_seed_map.json.
# If the file is missing or corrupt the module fails to import — this is intentional.
_LR2_SEED_INDEX: dict[tuple[str, int], str] = _load_lr2_seed_index()


def lookup_lr2_arrangement(keymode: int, rseed: int) -> str | None:
    """Return the arrangement string for the given LR2 keymode and rseed, or None if unmapped.

    Args:
        keymode: Number of key lanes (5 or 7).
        rseed: The raw rseed value stored in user_scores.options.

    Returns:
        A digit string representing the lane arrangement (e.g. ``"2561437"`` for 7K,
        ``"34512"`` for 5K), or ``None`` if the seed is not in the map.
    """
    return _LR2_SEED_INDEX.get((str(keymode), rseed))
