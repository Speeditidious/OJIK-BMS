"""Shared score-related enum mappings for search/filter operations."""

CLEAR_TYPE_VALUES: dict[str, int] = {
    "MAX":     9,
    "PERFECT": 8,
    "FC":      7,
    "EXHARD":  6,
    "HARD":    5,
    "NORMAL":  4,
    "EASY":    3,
    "ASSIST":  2,
    "FAILED":  1,
    "NO PLAY": 0,
}

RANK_VALUES: tuple[str, ...] = ("AAA", "AA", "A", "B", "C", "D", "E", "F")

# Maps display kanji → internal arrangement name (mirrors fumen-table-utils.ts ARRANGEMENT_KANJI)
ARRANGEMENT_KANJI_REV: dict[str, str] = {
    "正":   "NORMAL",
    "鏡":   "MIRROR",
    "乱":   "RANDOM",
    "R乱":  "R-RANDOM",
    "S乱":  "S-RANDOM",
    "螺":   "SPIRAL",
    "H乱":  "H-RANDOM",
    "全皿": "ALL-SCRATCH",
    "EX乱": "EX-RAN",
    "EXS乱": "EX-S-RAN",
}

LR2_ARRANGEMENT_NAMES: list[str] = [
    "NORMAL", "MIRROR", "RANDOM", "S-RANDOM", "H-RANDOM", "ALL-SCRATCH",
]

BEA_ARRANGEMENT_NAMES: list[str] = [
    "NORMAL", "MIRROR", "RANDOM", "R-RANDOM", "S-RANDOM",
    "SPIRAL", "H-RANDOM", "ALL-SCRATCH", "EX-RAN", "EX-S-RAN",
]
