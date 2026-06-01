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


# ---------------------------------------------------------------------------
# Judgment normalization
# ---------------------------------------------------------------------------

_LR2_JUDGMENT_KEYS = ("perfect", "great", "good", "bad", "poor")
_BEA_JUDGMENT_GROUPS = (
    # (group_key, early_key, late_key)
    ("pgreat", "epg", "lpg"),
    ("great", "egr", "lgr"),
    ("good", "egd", "lgd"),
    ("bad", "ebd", "lbd"),
    ("poor", "epr", "lpr"),
    ("miss", "ems", "lms"),
)
_BEA_FAST_KEYS_EX_PGREAT = ("egr", "egd", "ebd", "epr", "ems")
_BEA_SLOW_KEYS_EX_PGREAT = ("lgr", "lgd", "lbd", "lpr", "lms")
_ALL_BEA_KEYS: frozenset[str] = frozenset(k for _, e, l in _BEA_JUDGMENT_GROUPS for k in (e, l))


def normalize_judgments(client_type: str, judgments: dict | None) -> dict | None:
    """Return normalized judgment groups with fast/slow counts, or None if unusable.

    Args:
        client_type: ``"lr2"`` or ``"beatoraja"``.
        judgments: Raw judgments dict from ``user_scores.judgments``, or ``None``.

    Returns:
        A dict with ``judgments`` (list of group dicts), ``fast_total_excluding_pgreat``,
        and ``slow_total_excluding_pgreat``; or ``None`` when the source data is unusable.
    """
    if judgments is None:
        return None

    if client_type == "lr2":
        # Validate that at least one expected key exists
        if not any(k in judgments for k in _LR2_JUDGMENT_KEYS):
            return None

        groups = [
            {"key": "pgreat", "count": judgments.get("perfect", 0), "fast": None, "slow": None},
            {"key": "great",  "count": judgments.get("great", 0),   "fast": None, "slow": None},
            {"key": "good",   "count": judgments.get("good", 0),    "fast": None, "slow": None},
            {"key": "bad",    "count": judgments.get("bad", 0),     "fast": None, "slow": None},
            {"key": "poor",   "count": judgments.get("poor", 0),    "fast": None, "slow": None},
            {"key": "miss",   "count": 0,                           "fast": None, "slow": None},
        ]
        return {
            "judgments": groups,
            "fast_total_excluding_pgreat": None,
            "slow_total_excluding_pgreat": None,
        }

    if client_type == "beatoraja":
        # Validate that at least one expected key exists
        if not any(k in judgments for k in _ALL_BEA_KEYS):
            return None

        groups = []
        for group_key, early_key, late_key in _BEA_JUDGMENT_GROUPS:
            e = judgments.get(early_key, 0)
            l = judgments.get(late_key, 0)
            groups.append({"key": group_key, "count": e + l, "fast": e, "slow": l})

        fast_total = sum(judgments.get(k, 0) for k in _BEA_FAST_KEYS_EX_PGREAT)
        slow_total = sum(judgments.get(k, 0) for k in _BEA_SLOW_KEYS_EX_PGREAT)

        return {
            "judgments": groups,
            "fast_total_excluding_pgreat": fast_total,
            "slow_total_excluding_pgreat": slow_total,
        }

    return None


# ---------------------------------------------------------------------------
# Best-per-client selection
# ---------------------------------------------------------------------------

from typing import Any


def pick_best_per_client(rows: list[Any]) -> list[Any]:
    """Return the single best representative row per client_type.

    Selection priority (higher = better):
    1. Highest exscore (None is treated as -infinity).
    2. Highest clear_type (None is treated as -infinity).
    3. Latest coalesce(recorded_at, synced_at) (None is treated as earliest).

    Args:
        rows: Iterable of objects with attributes ``client_type``, ``exscore``,
              ``clear_type``, ``recorded_at``, ``synced_at``.

    Returns:
        One row per distinct ``client_type``, chosen by the priority above.
    """
    best: dict[str, Any] = {}

    for row in rows:
        ct = row.client_type
        if ct not in best:
            best[ct] = row
            continue

        incumbent = best[ct]

        # --- exscore comparison (higher wins, None is -infinity) ---
        ex_new = row.exscore if row.exscore is not None else -1
        ex_inc = incumbent.exscore if incumbent.exscore is not None else -1
        if ex_new > ex_inc:
            best[ct] = row
            continue
        if ex_new < ex_inc:
            continue

        # --- tie: clear_type (higher wins, None is -infinity) ---
        cl_new = row.clear_type if row.clear_type is not None else -1
        cl_inc = incumbent.clear_type if incumbent.clear_type is not None else -1
        if cl_new > cl_inc:
            best[ct] = row
            continue
        if cl_new < cl_inc:
            continue

        # --- tie: latest timestamp (None is earliest) ---
        ts_new = row.recorded_at or row.synced_at
        ts_inc = incumbent.recorded_at or incumbent.synced_at
        if ts_new is None and ts_inc is None:
            continue
        if ts_new is None:
            continue
        if ts_inc is None or ts_new > ts_inc:
            best[ct] = row

    return list(best.values())


# ---------------------------------------------------------------------------
# Arrangement decoding
# ---------------------------------------------------------------------------

# LR2 arrangement enum (op_best // 10)
_LR2_OPTION_LABELS = {
    0: "NORMAL",
    1: "MIRROR",
    2: "RANDOM",
    3: "S-RANDOM",
    4: "H-RANDOM",
    5: "ALL-SCRATCH",
}
_LR2_STATIC_MAP_OPTIONS = {3, 4, 5}  # S-RANDOM, H-RANDOM, ALL-SCRATCH

# Beatoraja SP option enum
_BEA_SP_OPTION_LABELS = {
    0: "NORMAL",
    1: "MIRROR",
    2: "RANDOM",
    3: "R-RANDOM",
    4: "S-RANDOM",
    5: "H-RANDOM",
    6: "ALL-SCRATCH",
    7: "RANDOM-EX",
    8: "S-RANDOM-EX",
    9: "BATTLE",
    10: "BATTLE AS",
}
_BEA_STATIC_MAP_OPTIONS = {3, 4, 5, 6, 7, 8}  # R-RANDOM, S-RANDOM, H-RANDOM, ALL-SCRATCH, RANDOM-EX, S-RANDOM-EX
_BEA_ASSIST_OPTIONS = {9, 10}  # BATTLE, BATTLE AS

_BEA_DOUBLE_OPTION_LABELS = {
    0: None,
    1: "FLIP",
}

_BEA_SP_KEYMODES = {5, 7}
_BEA_DP_KEYMODES = {10, 14}


def _java_random_shuffle(seed: int, n: int) -> list[int]:
    """Simulate java.util.Random(seed) Fisher-Yates shuffle of n keys.

    Returns a list of lane numbers 1..n in shuffled order.
    """
    MASK = (1 << 48) - 1
    MULT = 0x5DEECE66D
    ADD = 0xB

    # Java Random initializes with (seed ^ MULT) & MASK
    state = (seed ^ MULT) & MASK

    lanes = list(range(1, n + 1))

    def next_int(bound: int) -> int:
        nonlocal state
        # Mirrors java.util.Random.nextInt(bound): rejection-sample on overflow.
        # In Python, integers are arbitrary-precision so bits-val+(bound-1) >= 0 always;
        # the loop always exits on the first iteration for bounds ≤ 14 (BMS key count).
        while True:
            state = (state * MULT + ADD) & MASK
            bits = state >> 17
            val = bits % bound
            if bits - val + (bound - 1) >= 0:
                return val

    # Fisher-Yates shuffle (reverse)
    for i in range(n - 1, 0, -1):
        j = next_int(i + 1)
        lanes[i], lanes[j] = lanes[j], lanes[i]

    return lanes


def _make_unavailable(option_label: str, reason: str) -> dict:
    return {
        "option_label": option_label,
        "lane_groups": None,
        "double_option_label": None,
        "unavailable_reason": reason,
    }


def _identity_lanes(n: int) -> list[int]:
    return list(range(1, n + 1))


def _mirror_lanes(n: int) -> list[int]:
    return list(range(n, 0, -1))


def _decode_bea_sp_option(option_enum: int, seed: int | None, keymode: int) -> dict | None:
    """Decode a single Beatoraja SP option into a lane group dict, or return a reason string."""
    label = _BEA_SP_OPTION_LABELS.get(option_enum, f"UNKNOWN({option_enum})")

    if option_enum in _BEA_ASSIST_OPTIONS:
        return ("assist_option_unsupported", label)
    if option_enum in _BEA_STATIC_MAP_OPTIONS:
        return ("static_map_unsupported", label)
    if option_enum == 0:  # NORMAL
        return {"side": "single", "option_label": "NORMAL", "lanes": _identity_lanes(keymode)}
    if option_enum == 1:  # MIRROR
        return {"side": "single", "option_label": "MIRROR", "lanes": _mirror_lanes(keymode)}
    if option_enum == 2:  # RANDOM
        if seed is None:
            return ("score_metadata_missing", label)
        return {"side": "single", "option_label": "RANDOM", "lanes": _java_random_shuffle(seed, keymode)}

    return ("static_map_unsupported", label)


def decode_arrangement(
    client_type: str,
    options: dict | None,
    keymode: int | None,
) -> dict:
    """Return arrangement dict with option_label, lane_groups, double_option_label, unavailable_reason.

    Args:
        client_type: ``"lr2"`` or ``"beatoraja"``.
        options: Raw options dict from ``user_scores.options``, or ``None``.
        keymode: Number of lanes from ``fumens.keymode``, or ``None``.

    Returns:
        A dict with keys ``option_label``, ``lane_groups``, ``double_option_label``,
        ``unavailable_reason``.
    """
    if options is None:
        return _make_unavailable("UNKNOWN", "score_metadata_missing")
    if keymode is None:
        return _make_unavailable("UNKNOWN", "keymode_missing")

    if client_type == "lr2":
        op_best = options.get("op_best")
        if op_best is None:
            return _make_unavailable("UNKNOWN", "score_metadata_missing")

        arrangement_enum = op_best // 10
        label = _LR2_OPTION_LABELS.get(arrangement_enum, f"UNKNOWN({arrangement_enum})")

        # LR2 only supports SP (5K/7K); DP modes cannot reconstruct both sides
        if keymode not in _BEA_SP_KEYMODES:
            if keymode in _BEA_DP_KEYMODES:
                return _make_unavailable(label, "dp_unsupported")
            return _make_unavailable(label, "keymode_unsupported")

        if arrangement_enum in _LR2_STATIC_MAP_OPTIONS:
            return _make_unavailable(label, "static_map_unsupported")

        if arrangement_enum == 0:  # NORMAL
            lanes = _identity_lanes(keymode)
        elif arrangement_enum == 1:  # MIRROR
            lanes = _mirror_lanes(keymode)
        elif arrangement_enum == 2:  # RANDOM
            rseed = options.get("rseed")
            if rseed is None:
                return _make_unavailable(label, "score_metadata_missing")
            arrangement_str = lookup_lr2_arrangement(keymode, rseed)
            if arrangement_str is None:
                return _make_unavailable(label, "lr2_seed_unmapped")
            lanes = [int(c) for c in arrangement_str]
        else:
            return _make_unavailable(label, "static_map_unsupported")

        return {
            "option_label": label,
            "lane_groups": [{"side": "single", "option_label": label, "lanes": lanes}],
            "double_option_label": None,
            "unavailable_reason": None,
        }

    if client_type == "beatoraja":
        option_raw = options.get("option")
        if option_raw is None:
            return _make_unavailable("UNKNOWN", "score_metadata_missing")

        if keymode in _BEA_SP_KEYMODES:
            option_enum = option_raw & 0xFF
            label = _BEA_SP_OPTION_LABELS.get(option_enum, f"UNKNOWN({option_enum})")
            seed = options.get("seed")
            result = _decode_bea_sp_option(option_enum, seed, keymode)
            if isinstance(result, tuple):
                reason, _ = result
                return _make_unavailable(label, reason)
            return {
                "option_label": label,
                "lane_groups": [result],
                "double_option_label": None,
                "unavailable_reason": None,
            }

        if keymode in _BEA_DP_KEYMODES:
            n = keymode // 2  # lanes per side: 5 or 7

            option_1p = option_raw & 0xFF
            option_2p = (option_raw >> 8) & 0xFF
            double_option = (option_raw >> 16) & 0xFF

            seed_packed = options.get("seed")
            seed_1p: int | None = None
            seed_2p: int | None = None
            if seed_packed is not None:
                seed_1p = seed_packed & 0xFFFFFFFF
                seed_2p = (seed_packed >> 32) & 0xFFFFFFFF

            label_1p = _BEA_SP_OPTION_LABELS.get(option_1p, f"UNKNOWN({option_1p})")
            label_2p = _BEA_SP_OPTION_LABELS.get(option_2p, f"UNKNOWN({option_2p})")
            double_label = _BEA_DOUBLE_OPTION_LABELS.get(double_option)

            # Determine top-level option label
            if option_1p == option_2p:
                top_label = label_1p
            else:
                top_label = "DP"

            # BATTLE / BATTLE AS → assist_option_unsupported
            if option_1p in _BEA_ASSIST_OPTIONS or option_2p in _BEA_ASSIST_OPTIONS:
                return _make_unavailable(top_label, "assist_option_unsupported")

            # Apply FLIP: swap 1P/2P options and seeds
            if double_option == 1:  # FLIP
                option_1p, option_2p = option_2p, option_1p
                seed_1p, seed_2p = seed_2p, seed_1p
                label_1p, label_2p = label_2p, label_1p

            def decode_dp_side(opt_enum: int, lbl: str, sd: int | None, side: str) -> dict | tuple:
                if opt_enum in _BEA_ASSIST_OPTIONS:
                    return ("assist_option_unsupported", lbl)
                if opt_enum in _BEA_STATIC_MAP_OPTIONS:
                    return ("static_map_unsupported", lbl)
                if opt_enum == 0:
                    return {"side": side, "option_label": lbl, "lanes": _identity_lanes(n)}
                if opt_enum == 1:
                    return {"side": side, "option_label": lbl, "lanes": _mirror_lanes(n)}
                if opt_enum == 2:
                    if sd is None:
                        return ("score_metadata_missing", lbl)
                    return {"side": side, "option_label": lbl, "lanes": _java_random_shuffle(sd, n)}
                return ("static_map_unsupported", lbl)

            res_1p = decode_dp_side(option_1p, label_1p, seed_1p, "1p")
            res_2p = decode_dp_side(option_2p, label_2p, seed_2p, "2p")

            # Check for errors
            for res in (res_1p, res_2p):
                if isinstance(res, tuple):
                    reason, lbl = res
                    return _make_unavailable(top_label, reason)

            return {
                "option_label": top_label,
                "lane_groups": [res_1p, res_2p],
                "double_option_label": double_label,
                "unavailable_reason": None,
            }

        # Unsupported key mode (e.g. POPN)
        return _make_unavailable("UNKNOWN", "keymode_unsupported")

    return _make_unavailable("UNKNOWN", "score_metadata_missing")
