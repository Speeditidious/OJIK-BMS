"""Dump golden fixtures for the JS port of the per-chart rating formula.

Calls the *actual* Python implementation in ``app.services.ranking_calculator``
(and the ``TableRankingConfig``/``BonusConfig``/``LevelOverride`` dataclasses in
``app.services.ranking_config``) against a hand-built input matrix, and writes
the results to ``web/src/lib/__fixtures__/rating-golden.json``.

``web/src/lib/rating-calc-core.test.mjs`` reads this file and asserts the JS
port (``web/src/lib/rating-calc-core.mjs``) reproduces every value bit-for-bit
(within float tolerance).

IMPORTANT — keep this in sync: whenever the formula in
``app/services/ranking_calculator.py`` changes (``_f_bp``, ``_f_rate``,
``_base``, ``_bonus``, ``_resolve_level``, ``_song_rating``, ``_exp_level``,
``standardize_rating``, or the ``CLEAR_TYPE_TO_LAMP_NAME``/``RANK_ORDER``
constants), re-run this script and commit the regenerated fixture file:

    conda run -n ojik_bms python3 api/scripts/dump_rating_fixtures.py

This script does not touch the DB — all configs are built by hand in-process
so it stays self-contained and fast.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ranking_calculator import (  # noqa: E402
    _bonus,
    _exp_level,
    _resolve_level,
    _song_rating,
    standardize_rating,
)
from app.services.ranking_config import (  # noqa: E402
    BonusConfig,
    LevelOverride,
    ReferenceCondition,
    TableRankingConfig,
    _compute_c_table,
)

FIXTURE_PATH = (
    Path(__file__).parent.parent.parent
    / "web" / "src" / "lib" / "__fixtures__" / "rating-golden.json"
)

# Global rank_mult, shared by both configs below (mirrors [global.rank_mult]
# in api/ranking_tables/config.toml).
RANK_MULT = {
    "F": 0.00, "E": 0.10, "D": 0.30, "C": 0.50,
    "B": 0.80, "A": 1.00, "AA": 1.04, "AAA": 1.08,
}

ANCHOR = 1000.0


def _make_config(
    *,
    slug: str,
    level_weights: dict[str, float],
    base_lamp_mult: dict[str, float],
    upper_lamp_bonus: dict[str, float],
    bonus: BonusConfig,
    reference: ReferenceCondition,
    level_overrides: list[LevelOverride] | None = None,
    max_level: int = 200,
    top_n: int = 100,
) -> TableRankingConfig:
    """Build a TableRankingConfig by hand (no DB / TOML loader needed)."""
    c_table = _compute_c_table(
        reference, bonus, level_weights, base_lamp_mult, upper_lamp_bonus,
        RANK_MULT, ANCHOR,
    )
    return TableRankingConfig(
        slug=slug,
        table_id=uuid.uuid5(uuid.NAMESPACE_URL, slug),
        display_name=slug,
        display_order=0,
        level_order=list(level_weights.keys()),
        level_weights=level_weights,
        base_lamp_mult=base_lamp_mult,
        upper_lamp_bonus=upper_lamp_bonus,
        rank_mult=RANK_MULT,
        bonus=bonus,
        reference_20=reference,
        c_table=c_table,
        top_n=top_n,
        max_level=max_level,
        level_overrides=level_overrides or [],
    )


# ── Config 1: "aery_like" — mirrors the 5aery table (config.toml), no
#    level_overrides. bp_floor=100, rate_floor=0.70. ─────────────────────────
AERY_LEVEL_WEIGHTS = {
    "LEVEL 1": 0.5, "LEVEL 2": 1.0, "LEVEL 3": 1.5, "LEVEL 4": 2.0,
    "LEVEL 5": 2.5, "LEVEL 6": 3.0, "LEVEL 7": 3.5, "LEVEL 8": 4.0,
    "LEVEL 9": 4.5, "LEVEL 10": 5.0, "LEVEL 11": 5.5, "LEVEL 12": 6.0,
    "LEVEL 13": 7.0, "LEVEL 14": 8.0, "LEVEL 15": 9.0, "LEVEL 15+": 10.0,
    "LEVEL 16": 11.0, "LEVEL 16+": 12.0, "LEVEL 17": 13.0, "LEVEL 17+": 14.0,
    "LEVEL 18": 15.0, "LEVEL 18+": 16.0, "LEVEL 19": 17.0, "LEVEL 19+": 18.0,
    "LEVEL 20": 20.0, "LEVEL 20+": 22.0,
}
AERY_BASE_LAMP_MULT = {
    "NOPLAY": 0.0, "FAILED": 0.1, "ASSIST": 0.1, "EASY": 0.5, "NORMAL": 0.6,
    "HARD": 1.0, "EXHARD": 1.0, "FC": 1.0, "PERFECT": 1.0, "MAX": 1.0,
}
AERY_UPPER_LAMP_BONUS = {
    "NOPLAY": 0.0, "FAILED": 0.0, "ASSIST": 0.0, "EASY": 0.0, "NORMAL": 0.0,
    "HARD": 0.0, "EXHARD": 0.0, "FC": 3.1, "PERFECT": 3.1, "MAX": 3.1,
}
AERY_BONUS = BonusConfig(
    bp_weight=0.20, rate_weight=0.40,
    bp_floor=100.0, bp_slope=1.0,
    rate_floor=0.70, rate_slope=1.0,
)
AERY_REFERENCE = ReferenceCondition(level="LEVEL 19+", lamp="HARD", bp=50, rank="AA", rate=0.80)

AERY_CFG = _make_config(
    slug="aery_like",
    level_weights=AERY_LEVEL_WEIGHTS,
    base_lamp_mult=AERY_BASE_LAMP_MULT,
    upper_lamp_bonus=AERY_UPPER_LAMP_BONUS,
    bonus=AERY_BONUS,
    reference=AERY_REFERENCE,
)

# ── Config 2: "overjoy_like" — mirrors the overjoy table (config.toml),
#    with level_overrides (both an sha256-matched and an LR2 md5-only entry).
#    bp_floor=150 (global default), rate_floor=0.70. ─────────────────────────
OVERJOY_LEVEL_WEIGHTS = {
    "0": 2.0, "1": 2.0, "2": 4.0, "3": 6.0, "4": 8.0,
    "5": 11.0, "6": 14.0, "7": 17.0, "8": 20.0,
}
OVERJOY_BASE_LAMP_MULT = {
    "NOPLAY": 0.0, "FAILED": 0.1, "ASSIST": 0.1, "EASY": 1.0, "NORMAL": 1.0,
    "HARD": 1.0, "EXHARD": 1.0, "FC": 1.0, "PERFECT": 1.0, "MAX": 1.0,
}
OVERJOY_UPPER_LAMP_BONUS = {
    "NOPLAY": 0.0, "FAILED": 0.0, "ASSIST": 0.0, "EASY": 0.0, "NORMAL": 0.6,
    "HARD": 2.6, "EXHARD": 2.6, "FC": 5.6, "PERFECT": 5.6, "MAX": 5.6,
}
OVERJOY_BONUS = BonusConfig(
    bp_weight=0.15, rate_weight=0.40,
    bp_floor=150.0, bp_slope=1.0,
    rate_floor=0.70, rate_slope=1.0,
)
OVERJOY_REFERENCE = ReferenceCondition(level="5", lamp="EASY", bp=150, rank="A", rate=0.70)

# Real level_override from config.toml (sha256-matched — Beatoraja fumen).
OVERJOY_OVERRIDE_SHA = LevelOverride(
    fumen_sha256="63eeb491ad5ad123df92b74ace3b65b9c6f2ec68e002f908b886cc5016c38310",
    fumen_md5="c569481923194f107186148d48584351",
    lamp_to_level={"HARD": "4", "EXHARD": "4", "FC": "5", "PERFECT": "5"},
    note="Human Sacrifice Halt (HARD clear counts as level 4, FC+ as level 5)",
)
# Synthetic LR2-only override (fumen_sha256=None) — exercises the md5-only
# fallback matching rule (CLAUDE.md 'Fumen hash lookups').
OVERJOY_OVERRIDE_MD5_ONLY = LevelOverride(
    fumen_sha256=None,
    fumen_md5="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    lamp_to_level={"NORMAL": "3", "HARD": "4"},
    note="LR2-only test fixture override (md5-only match)",
)

OVERJOY_CFG = _make_config(
    slug="overjoy_like",
    level_weights=OVERJOY_LEVEL_WEIGHTS,
    base_lamp_mult=OVERJOY_BASE_LAMP_MULT,
    upper_lamp_bonus=OVERJOY_UPPER_LAMP_BONUS,
    bonus=OVERJOY_BONUS,
    reference=OVERJOY_REFERENCE,
    level_overrides=[OVERJOY_OVERRIDE_SHA, OVERJOY_OVERRIDE_MD5_ONLY],
)

CONFIGS = {"aery_like": AERY_CFG, "overjoy_like": OVERJOY_CFG}


def _cfg_to_dict(cfg: TableRankingConfig) -> dict:
    """Convert a TableRankingConfig to the camelCase JS `RatingCalcConfig` shape."""
    return {
        "cTable": cfg.c_table,
        "levelWeights": cfg.level_weights,
        "baseLampMult": cfg.base_lamp_mult,
        "upperLampBonus": cfg.upper_lamp_bonus,
        "rankMult": cfg.rank_mult,
        "bonus": {
            "bpWeight": cfg.bonus.bp_weight,
            "rateWeight": cfg.bonus.rate_weight,
            "bpFloor": cfg.bonus.bp_floor,
            "bpSlope": cfg.bonus.bp_slope,
            "rateFloor": cfg.bonus.rate_floor,
            "rateSlope": cfg.bonus.rate_slope,
        },
        "levelOverrides": [
            {
                "fumenSha256": ov.fumen_sha256,
                "fumenMd5": ov.fumen_md5,
                "lampToLevel": ov.lamp_to_level,
                "note": ov.note,
            }
            for ov in cfg.level_overrides
        ],
    }


# ── resolveLevel cases ────────────────────────────────────────────────────────

def _build_resolve_level_cases() -> list[dict]:
    cases = [
        dict(
            description="sha256-matched override hits (Beatoraja fumen, md5 absent)",
            config_key="overjoy_like",
            fumen_sha256="63eeb491ad5ad123df92b74ace3b65b9c6f2ec68e002f908b886cc5016c38310",
            fumen_md5=None,
            lamp="HARD",
            original_level="3",
        ),
        dict(
            description="md5-only match hits (LR2 fumen, sha256 absent) — same override as sha256 case",
            config_key="overjoy_like",
            fumen_sha256=None,
            fumen_md5="c569481923194f107186148d48584351",
            lamp="HARD",
            original_level="3",
        ),
        dict(
            description="LR2-only override entry (fumen_sha256=None in the override itself) matches by md5",
            config_key="overjoy_like",
            fumen_sha256=None,
            fumen_md5="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            lamp="NORMAL",
            original_level="2",
        ),
        dict(
            description="no matching override (unknown hashes) → falls back to original_level",
            config_key="overjoy_like",
            fumen_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            fumen_md5="00000000000000000000000000000000",
            lamp="HARD",
            original_level="3",
        ),
        dict(
            description="override matched but lamp not in lamp_to_level → falls back to original_level",
            config_key="overjoy_like",
            fumen_sha256="63eeb491ad5ad123df92b74ace3b65b9c6f2ec68e002f908b886cc5016c38310",
            fumen_md5="c569481923194f107186148d48584351",
            lamp="EASY",
            original_level="3",
        ),
    ]
    out = []
    for case in cases:
        cfg = CONFIGS[case["config_key"]]
        expected = _resolve_level(
            case["fumen_sha256"], case["fumen_md5"], case["lamp"], case["original_level"], cfg,
        )
        out.append({
            "description": case["description"],
            "configKey": case["config_key"],
            "fumenSha256": case["fumen_sha256"],
            "fumenMd5": case["fumen_md5"],
            "lamp": case["lamp"],
            "originalLevel": case["original_level"],
            "expectedLevel": expected,
        })
    return out


# ── songRating cases ──────────────────────────────────────────────────────────

def _song_rating_case(description: str, config_key: str, level: str, lamp: str, rank: str,
                       bp: float | None, rate: float | None) -> dict:
    cfg = CONFIGS[config_key]
    rate_01 = (rate / 100.0) if rate is not None else None
    expected = _song_rating(level, lamp, rank, bp, rate_01, cfg)
    return {
        "description": description,
        "configKey": config_key,
        "level": level,
        "lamp": lamp,
        "rank": rank,
        "bp": bp,
        "rate": rate,
        "expectedSongRating": expected,
    }


def _build_song_rating_cases() -> list[dict]:
    cases: list[dict] = []

    # 1) All 10 lamp values (CLEAR_TYPE_TO_LAMP_NAME), including NOPLAY.
    for lamp in ["NOPLAY", "FAILED", "ASSIST", "EASY", "NORMAL", "HARD", "EXHARD", "FC", "PERFECT", "MAX"]:
        cases.append(_song_rating_case(
            f"lamp coverage: {lamp}", "aery_like", "LEVEL 10", lamp, "A", 50, 80.0,
        ))

    # 2) All 10 rank values (RANK_ORDER), including MAX/MAX- → AAA rank_mult remap.
    for rank in ["F", "E", "D", "C", "B", "A", "AA", "AAA", "MAX-", "MAX"]:
        cases.append(_song_rating_case(
            f"rank coverage: {rank}", "aery_like", "LEVEL 15", "HARD", rank, 30, 85.0,
        ))

    # 3) bp spread against aery_like's floor (100): 0, mid, at floor, above floor, None.
    for label, bp in [("bp=0", 0), ("bp=mid", 50), ("bp=at-floor", 100), ("bp=above-floor", 150), ("bp=None", None)]:
        cases.append(_song_rating_case(
            f"bp spread (aery_like, floor=100): {label}", "aery_like", "LEVEL 12", "HARD", "AA", bp, 75.0,
        ))

    # 3b) bp spread against overjoy_like's floor (150).
    for label, bp in [("bp=0", 0), ("bp=mid", 75), ("bp=at-floor", 150), ("bp=above-floor", 220), ("bp=None", None)]:
        cases.append(_song_rating_case(
            f"bp spread (overjoy_like, floor=150): {label}", "overjoy_like", "5", "HARD", "A", bp, 75.0,
        ))

    # 4) rate spread (raw 0-100) against rate_floor=0.70 (both configs share this): 0, mid, at floor, above, 100, None.
    for label, rate in [("rate=0", 0.0), ("rate=mid", 40.0), ("rate=at-floor", 70.0),
                         ("rate=above-floor", 90.0), ("rate=100", 100.0), ("rate=None", None)]:
        cases.append(_song_rating_case(
            f"rate spread: {label}", "aery_like", "LEVEL 12", "NORMAL", "B", 60, rate,
        ))

    # 5) FC-or-above forces effective_bp=0 regardless of the passed bp (bp=999,
    #    well above any floor — a non-FC lamp would get f_bp=0 here).
    for lamp in ["FC", "PERFECT", "MAX"]:
        cases.append(_song_rating_case(
            f"FC-or-above ignores bp: {lamp} with bp=999", "aery_like", "LEVEL 14", lamp, "AA", 999, 85.0,
        ))
    # Sanity control: same bp=999 with a non-FC lamp should hit f_bp=0 (no override).
    cases.append(_song_rating_case(
        "control: HARD with bp=999 (bp bonus should be zero, no FC override)",
        "aery_like", "LEVEL 14", "HARD", "AA", 999, 85.0,
    ))

    # 6) level missing from cfg.levelWeights → 0.
    cases.append(_song_rating_case(
        "unknown level (aery_like) → 0", "aery_like", "LEVEL 99", "HARD", "A", 50, 80.0,
    ))
    cases.append(_song_rating_case(
        "unknown level (overjoy_like) → 0", "overjoy_like", "99", "HARD", "A", 50, 80.0,
    ))

    return cases


# ── expLevel / standardizeRating cases ────────────────────────────────────────

def _standardize_case(description: str, total_exp: float, exp_level_step: float,
                       max_level: int, raw_top_n: float) -> dict:
    player_level = _exp_level(total_exp, exp_level_step, max_level)
    bms_force = standardize_rating(raw_top_n, player_level)
    return {
        "description": description,
        "totalExp": total_exp,
        "expLevelStep": exp_level_step,
        "maxLevel": max_level,
        "rawTopN": raw_top_n,
        "expectedPlayerLevel": player_level,
        "expectedBmsForce": bms_force,
    }


def _build_standardize_cases() -> list[dict]:
    return [
        _standardize_case("total_exp=0 → player_level=0, raw_top_n=0 → bms_force=0",
                           0.0, 100.0, 200, 0.0),
        _standardize_case("negative total_exp/raw_top_n both clamp to 0",
                           -5.0, 100.0, 200, -10.0),
        # threshold(n)=step*n*(n+1); step=100, n=5 -> 3000 (exact boundary).
        _standardize_case("total_exp exactly at threshold(5)=3000 (step=100)",
                           3000.0, 100.0, 200, 2500.0),
        # threshold(6)=4200; value just under, to exercise the float-error safety while-loop.
        _standardize_case("total_exp just under threshold(6)=4200 (float-error safety)",
                           4199.999999999998, 100.0, 200, 4100.0),
        _standardize_case("total_exp exactly at threshold(6)=4200 (step=100)",
                           4200.0, 100.0, 200, 4100.0),
        # max_level cap: threshold(10)=100*10*11=11000, well below total_exp.
        _standardize_case("total_exp far above max_threshold → capped at max_level=10",
                           50000.0, 100.0, 10, 999999.0),
        # standardize_rating branch boundary: adjusted == 100_000 exactly (player_level=0).
        _standardize_case("raw_top_n adjusted exactly 100000 (<=100000 branch, player_level=0)",
                           0.0, 100.0, 200, 100000.0),
        # Just above the 100_000 boundary -> sqrt branch, tests continuity.
        _standardize_case("raw_top_n adjusted just above 100000 (sqrt branch, player_level=0)",
                           0.0, 100.0, 200, 100000.0001),
        # Different exp_level_step (non-default), boundary at threshold(3)=50*3*4=600.
        _standardize_case("non-default exp_level_step=50, total_exp exactly at threshold(3)=600",
                           600.0, 50.0, 200, 550.0),
    ]


def main() -> None:
    fixture = {
        "meta": {
            "pythonSource": "api/app/services/ranking_calculator.py",
            "note": "Golden fixture — regenerate via `conda run -n ojik_bms python3 api/scripts/dump_rating_fixtures.py` whenever the formula changes.",
        },
        "configs": {key: _cfg_to_dict(cfg) for key, cfg in CONFIGS.items()},
        "resolveLevelCases": _build_resolve_level_cases(),
        "songRatingCases": _build_song_rating_cases(),
        "standardizeCases": _build_standardize_cases(),
    }

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)
        f.write("\n")

    total_records = (
        len(fixture["resolveLevelCases"])
        + len(fixture["songRatingCases"])
        + len(fixture["standardizeCases"])
    )
    print(f"Wrote {FIXTURE_PATH}")
    print(f"  configs:            {len(fixture['configs'])}")
    print(f"  resolveLevelCases:  {len(fixture['resolveLevelCases'])}")
    print(f"  songRatingCases:    {len(fixture['songRatingCases'])}")
    print(f"  standardizeCases:   {len(fixture['standardizeCases'])}")
    print(f"  total fixture records: {total_records}")


if __name__ == "__main__":
    main()
