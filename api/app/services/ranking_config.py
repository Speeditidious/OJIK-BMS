"""Ranking system configuration loader.

Loads ranking_tables/config.toml, resolves slug -> table_id from DB,
applies global defaults with per-table overrides, computes C_table per §3,
and validates all settings per spec §7.1.

The loaded config is cached in memory and reloaded on server restart.
"""
import logging
import math
import tomllib
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "ranking_tables" / "config.toml"

ALL_LAMP_KEYS = [
    "NOPLAY", "FAILED", "ASSIST", "EASY", "NORMAL",
    "HARD", "EXHARD", "FC", "PERFECT", "MAX",
]
ALL_RANK_KEYS = ["F", "E", "D", "C", "B", "A", "AA", "AAA"]

# Deprecated TOML keys — emit warning once, then ignore
_DEPRECATED_KEYS = {
    "table_constant", "difficulty_weights", "base_lamp_constants",
    "upper_lamp_constants", "rank_constants", "rating_20_clear_type",
    "rating_25_clear_type", "reference_25", "bp_coefficient",
    "rate_coefficient",
}


class RankingConfigError(ValueError):
    """Raised when ranking config is invalid."""


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DanConfig:
    dan_title: str
    course_name: str          # DB의 Course.name 과 매칭
    source_table: str | None  # 코스가 속한 난이도표 slug (None → 자기 테이블)
    display_text: str
    color: str
    glow_intensity: str       # "none" | "subtle" | "strong"
    priority: int


@dataclass
class ReferenceCondition:
    """spec §3 reference_20: song_rating(이 조건) == high_tier_rating_anchor."""
    level: str
    lamp: str     # e.g. "EASY" / "HARD"
    bp: int
    rank: str     # e.g. "A" / "AA"
    rate: float   # 0~1 스케일 (config 에 0.80 으로 적힌 값 그대로)


@dataclass
class BonusConfig:
    """spec §2.2 Bonus 파라미터 (per-table, global fallback)."""
    bp_weight: float
    rate_weight: float
    bp_floor: float
    bp_slope: float
    rate_floor: float   # 0~1 스케일
    rate_slope: float


@dataclass
class LevelOverride:
    """spec §6.2.9 / §9.1-4 차분 단위 레벨 예외 (Overjoy 인신사고 등)."""
    fumen_sha256: str | None
    fumen_md5: str | None
    lamp_to_level: dict[str, str]   # lamp name → level key (must be in level_weights)
    note: str | None = None


@dataclass
class TableRankingConfig:
    slug: str
    table_id: uuid.UUID
    display_name: str
    display_order: int
    level_order: list[str]

    # 새 필드
    level_weights: dict[str, float]
    base_lamp_mult: dict[str, float]
    upper_lamp_bonus: dict[str, float]
    rank_mult: dict[str, float]
    bonus: BonusConfig
    reference_20: ReferenceCondition
    c_table: float               # high_tier_rating_anchor / (Base_ref + Bonus_ref)
    top_n: int
    max_level: int = 200

    level_overrides: list[LevelOverride] = field(default_factory=list)

    # 기존 유지 — dan 배지 로직은 리워크 범위 밖
    dans: list[DanConfig] = field(default_factory=list)
    linked_dan_table: str | None = None

    # satellite ↔ stella 크로스 테이블 단 비교
    # cross_dan_tier: 0=단독, 1=하위(sl), 2=상위(st) — 높을수록 우선순위 높음
    cross_dan_peer: str | None = None
    cross_dan_tier: int = 0


@dataclass
class RankingConfig:
    tables: list[TableRankingConfig]
    exp_level_step: float          # global K for threshold(n) = K × n × (n+1)
    high_tier_rating_anchor: float # debug/validation only
    max_level: int = 200

    def get_table_by_slug(self, slug: str) -> TableRankingConfig | None:
        for t in self.tables:
            if t.slug == slug:
                return t
        return None

    def get_table_by_id(self, table_id: uuid.UUID) -> TableRankingConfig | None:
        for t in self.tables:
            if t.table_id == table_id:
                return t
        return None


def get_effective_dans(
    table_cfg: TableRankingConfig,
    config: RankingConfig,
) -> list[DanConfig]:
    """Return the effective dan definitions for a table, following linked sources."""
    if table_cfg.dans:
        return table_cfg.dans
    if table_cfg.linked_dan_table:
        linked = config.get_table_by_slug(table_cfg.linked_dan_table)
        if linked is not None:
            return linked.dans
    return []


def find_dan_config(
    dan_title: str | None,
    table_cfg: TableRankingConfig,
    config: RankingConfig,
) -> DanConfig | None:
    """Find a dan config by title, falling back to linked dan sources when needed."""
    if not dan_title:
        return None

    for dan in get_effective_dans(table_cfg, config):
        if dan.dan_title == dan_title:
            return dan

    if table_cfg.linked_dan_table:
        linked = config.get_table_by_slug(table_cfg.linked_dan_table)
        if linked is not None:
            for dan in linked.dans:
                if dan.dan_title == dan_title:
                    return dan

    return None


# ── C_table computation ───────────────────────────────────────────────────────

def _compute_c_table(
    ref: ReferenceCondition,
    bonus_cfg: BonusConfig,
    level_weights: dict[str, float],
    base_lamp_mult: dict[str, float],
    upper_lamp_bonus: dict[str, float],
    rank_mult: dict[str, float],
    anchor: float,
) -> float:
    """Compute C_table = anchor / (Base_ref + Bonus_ref). spec §3."""
    level_weight = level_weights[ref.level]
    base_ref = (
        base_lamp_mult[ref.lamp]
        * rank_mult[ref.rank]
        * (level_weight + upper_lamp_bonus[ref.lamp])
    )

    # f_bp for reference bp
    bp_val = float(ref.bp)
    if bp_val >= bonus_cfg.bp_floor:
        f_bp_ref = 0.0
    else:
        x = ((bonus_cfg.bp_floor - bp_val) / bonus_cfg.bp_floor) ** bonus_cfg.bp_slope
        f_bp_ref = min((1 - math.cos(math.pi * x)) / 2, 1.0)

    # f_rate for reference rate (already 0~1)
    rate_val = ref.rate
    if rate_val <= bonus_cfg.rate_floor:
        f_rate_ref = 0.0
    else:
        x = ((rate_val - bonus_cfg.rate_floor) / (1 - bonus_cfg.rate_floor)) ** bonus_cfg.rate_slope
        f_rate_ref = min((1 - math.cos(math.pi * x)) / 2, 1.0)

    bonus_ref = bonus_cfg.bp_weight * f_bp_ref + bonus_cfg.rate_weight * f_rate_ref
    total_ref = base_ref + bonus_ref
    if total_ref <= 0:
        raise RankingConfigError(
            f"Base_ref + Bonus_ref = {total_ref} <= 0 for reference_20 "
            f"(level={ref.level}, lamp={ref.lamp}, rank={ref.rank}). "
            "C_table is undefined."
        )
    return anchor / total_ref


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_table(slug: str, cfg_raw: dict, level_weights: dict, base_lamp: dict, upper_lamp: dict, rank_mult: dict, bonus: BonusConfig) -> None:
    """Validate per-table ranking config per spec §7.1."""
    # 1) reference_20.level must exist in level_weights
    ref_level = cfg_raw.get("reference_20", {}).get("level")
    if ref_level is not None and ref_level not in level_weights:
        raise RankingConfigError(
            f"[{slug}] reference_20.level '{ref_level}' not in level_weights keys"
        )

    # 2) All 10 lamp keys must exist
    missing_base = set(ALL_LAMP_KEYS) - set(base_lamp.keys())
    if missing_base:
        raise RankingConfigError(f"[{slug}] base_lamp_mult missing keys: {missing_base}")
    missing_upper = set(ALL_LAMP_KEYS) - set(upper_lamp.keys())
    if missing_upper:
        raise RankingConfigError(f"[{slug}] upper_lamp_bonus missing keys: {missing_upper}")

    # 3) All 8 rank keys must exist
    missing_rank = set(ALL_RANK_KEYS) - set(rank_mult.keys())
    if missing_rank:
        raise RankingConfigError(f"[{slug}] rank_mult missing keys: {missing_rank}")

    # 4) At least one base lamp (base=1.0 AND upper=0.0)
    has_base_lamp = any(
        abs(base_lamp[k] - 1.0) < 1e-9 and abs(upper_lamp[k]) < 1e-9
        for k in ALL_LAMP_KEYS
    )
    if not has_base_lamp:
        raise RankingConfigError(
            f"[{slug}] No base lamp found (base_lamp_mult=1.0 AND upper_lamp_bonus=0.0 required)"
        )

    # 5) Bonus param sanity
    if bonus.bp_floor <= 0:
        raise RankingConfigError(f"[{slug}] bonus.bp_floor must be > 0")
    if not (0 <= bonus.rate_floor < 1):
        raise RankingConfigError(f"[{slug}] bonus.rate_floor must be in [0, 1)")
    if bonus.bp_slope <= 0:
        raise RankingConfigError(f"[{slug}] bonus.bp_slope must be > 0")
    if bonus.rate_slope <= 0:
        raise RankingConfigError(f"[{slug}] bonus.rate_slope must be > 0")

    # 6) level_overrides: each lamp_to_level value must be in level_weights
    for ov_raw in cfg_raw.get("level_overrides", []):
        for lamp, lvl in ov_raw.get("lamp_to_level", {}).items():
            if lvl not in level_weights:
                raise RankingConfigError(
                    f"[{slug}] level_override lamp_to_level['{lamp}'] = '{lvl}' "
                    f"not in level_weights keys"
                )


def _warn_deprecated(slug: str, raw: dict) -> None:
    for key in _DEPRECATED_KEYS:
        if key in raw:
            logger.warning("[%s] deprecated TOML key '%s' — ignored", slug, key)


# ── Loader ────────────────────────────────────────────────────────────────────

async def load_ranking_config(db_session) -> RankingConfig:
    """Load and validate ranking config from TOML, resolving slug -> table_id via DB.

    Raises RankingConfigError on validation failure.
    """
    from sqlalchemy import select

    from app.models.course import Course
    from app.models.difficulty_table import DifficultyTable

    with open(CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)

    global_raw = raw.get("global", {})
    global_top_n: int = int(global_raw.get("top_n", 100))
    anchor: float = float(global_raw.get("high_tier_rating_anchor", 1000))
    exp_level_step: float = float(global_raw.get("exp_level_step", 100))
    global_max_level: int = int(global_raw.get("max_level", 200))
    if global_max_level <= 0:
        raise RankingConfigError(f"global.max_level must be > 0 (got {global_max_level})")

    # Global rank_mult
    global_rank_mult: dict[str, float] = {
        k: float(v) for k, v in global_raw.get("rank_mult", {}).items()
    }

    # Global bonus defaults
    global_bonus_raw = global_raw.get("bonus", {})
    global_bonus = BonusConfig(
        bp_weight=float(global_bonus_raw.get("bp_weight", 0.15)),
        rate_weight=float(global_bonus_raw.get("rate_weight", 0.40)),
        bp_floor=float(global_bonus_raw.get("bp_floor", 150)),
        bp_slope=float(global_bonus_raw.get("bp_slope", 1.0)),
        rate_floor=float(global_bonus_raw.get("rate_floor", 0.70)),
        rate_slope=float(global_bonus_raw.get("rate_slope", 1.0)),
    )

    tables_raw = raw.get("tables", [])
    if not tables_raw:
        return RankingConfig(
            tables=[],
            exp_level_step=exp_level_step,
            high_tier_rating_anchor=anchor,
            max_level=global_max_level,
        )

    # Collect all slugs referenced (tables + dans source_table + linked_dan_table)
    all_slugs: set[str] = set()
    for t_raw in tables_raw:
        all_slugs.add(t_raw["slug"])
        for d in t_raw.get("dans", []):
            if d.get("source_table"):
                all_slugs.add(d["source_table"])
        if t_raw.get("linked_dan_table"):
            all_slugs.add(t_raw["linked_dan_table"])

    result = await db_session.execute(
        select(DifficultyTable).where(DifficultyTable.slug.in_(all_slugs))
    )
    all_dts = result.scalars().all()
    slug_to_dt = {dt.slug: dt for dt in all_dts}

    tables: list[TableRankingConfig] = []
    for t_raw in tables_raw:
        slug: str = t_raw["slug"]

        # Warn on deprecated keys
        _warn_deprecated(slug, t_raw)

        # Slug must exist in DB
        dt = slug_to_dt.get(slug)
        if dt is None:
            raise RankingConfigError(f"TOML slug '{slug}' not found in difficulty_tables")

        level_order: list[str] = dt.level_order or []

        # level_weights
        level_weights: dict[str, float] = {
            str(k): float(v) for k, v in t_raw.get("level_weights", {}).items()
        }

        # base_lamp_mult / upper_lamp_bonus — table overrides global (no global defaults)
        base_lamp_mult: dict[str, float] = {
            k: float(v) for k, v in t_raw.get("base_lamp_mult", {}).items()
        }
        upper_lamp_bonus: dict[str, float] = {
            k: float(v) for k, v in t_raw.get("upper_lamp_bonus", {}).items()
        }

        # rank_mult — merge global + table override (table wins)
        rank_mult: dict[str, float] = {
            **global_rank_mult,
            **{k: float(v) for k, v in t_raw.get("rank_mult", {}).items()},
        }

        # bonus — key-level merge: table overrides global per key
        table_bonus_raw = t_raw.get("bonus", {})
        bonus = BonusConfig(
            bp_weight=float(table_bonus_raw.get("bp_weight", global_bonus.bp_weight)),
            rate_weight=float(table_bonus_raw.get("rate_weight", global_bonus.rate_weight)),
            bp_floor=float(table_bonus_raw.get("bp_floor", global_bonus.bp_floor)),
            bp_slope=float(table_bonus_raw.get("bp_slope", global_bonus.bp_slope)),
            rate_floor=float(table_bonus_raw.get("rate_floor", global_bonus.rate_floor)),
            rate_slope=float(table_bonus_raw.get("rate_slope", global_bonus.rate_slope)),
        )

        # top_n
        top_n: int = int(t_raw.get("top_n", global_top_n))
        table_max_level: int = int(t_raw.get("max_level", global_max_level))
        if table_max_level <= 0:
            raise RankingConfigError(f"[{slug}] max_level must be > 0 (got {table_max_level})")

        # reference_20
        ref_raw = t_raw.get("reference_20", {})
        if not ref_raw:
            raise RankingConfigError(f"[{slug}] missing [tables.reference_20] block")
        reference_20 = ReferenceCondition(
            level=str(ref_raw["level"]),
            lamp=str(ref_raw["lamp"]),
            bp=int(ref_raw["bp"]),
            rank=str(ref_raw["rank"]),
            rate=float(ref_raw["rate"]),
        )

        # linked_dan_table
        linked_dan_table: str | None = t_raw.get("linked_dan_table")

        # cross_dan_peer / cross_dan_tier (satellite ↔ stella)
        cross_dan_peer: str | None = t_raw.get("cross_dan_peer")
        cross_dan_tier: int = int(t_raw.get("cross_dan_tier", 0))

        # Validate
        _validate_table(slug, t_raw, level_weights, base_lamp_mult, upper_lamp_bonus, rank_mult, bonus)

        # C_table
        c_table = _compute_c_table(
            reference_20, bonus, level_weights,
            base_lamp_mult, upper_lamp_bonus, rank_mult, anchor,
        )

        # level_overrides
        level_overrides: list[LevelOverride] = []
        for ov_raw in t_raw.get("level_overrides", []):
            sha256_val = ov_raw.get("fumen_sha256") or None
            md5_val = ov_raw.get("fumen_md5") or None
            # Skip placeholder values
            if sha256_val and sha256_val.startswith("TODO"):
                sha256_val = None
            if md5_val and md5_val.startswith("TODO"):
                logger.warning("[%s] level_override has placeholder fumen_md5 — skipped", slug)
                md5_val = None
            if sha256_val is None and md5_val is None:
                logger.warning("[%s] level_override has no valid hash — skipped", slug)
                continue
            level_overrides.append(LevelOverride(
                fumen_sha256=sha256_val,
                fumen_md5=md5_val,
                lamp_to_level={str(k): str(v) for k, v in ov_raw.get("lamp_to_level", {}).items()},
                note=ov_raw.get("note"),
            ))

        # Dans — course existence warnings
        dan_raw_list: list[dict] = t_raw.get("dans", [])
        if dan_raw_list:
            for d in dan_raw_list:
                source_slug = d.get("source_table") or slug
                source_dt = slug_to_dt.get(source_slug)
                if source_dt is None:
                    logger.warning(
                        "[%s] source_table '%s' not found for dan '%s'",
                        slug, source_slug, d["dan_title"],
                    )
                    continue
                course_result = await db_session.execute(
                    select(Course.name).where(
                        Course.source_table_id == source_dt.id,
                        Course.name == d["course_name"],
                        Course.is_active.is_(True),
                    )
                )
                if course_result.scalar_one_or_none() is None:
                    logger.warning(
                        "[%s] course '%s' not found for dan '%s'",
                        slug, d["course_name"], d["dan_title"],
                    )

        dans = [
            DanConfig(
                dan_title=d["dan_title"],
                course_name=d["course_name"],
                source_table=d.get("source_table"),
                display_text=d["display_text"],
                color=d["color"],
                glow_intensity=d["glow_intensity"],
                priority=d["priority"],
            )
            for d in dan_raw_list
        ]

        tables.append(TableRankingConfig(
            slug=slug,
            table_id=dt.id,
            display_name=t_raw.get("display_name", dt.name),
            display_order=t_raw.get("display_order", 999),
            level_order=level_order,
            level_weights=level_weights,
            base_lamp_mult=base_lamp_mult,
            upper_lamp_bonus=upper_lamp_bonus,
            rank_mult=rank_mult,
            bonus=bonus,
            reference_20=reference_20,
            c_table=c_table,
            top_n=top_n,
            max_level=table_max_level,
            level_overrides=level_overrides,
            linked_dan_table=linked_dan_table,
            dans=dans,
            cross_dan_peer=cross_dan_peer,
            cross_dan_tier=cross_dan_tier,
        ))

        logger.info(
            "[%s] loaded: c_table=%.4f, %d level_weights, %d overrides, %d dans",
            slug, c_table, len(level_weights), len(level_overrides), len(dans),
        )

    # 2nd pass: linked_dan_table resolve
    for table_cfg in tables:
        if table_cfg.linked_dan_table:
            source = next((t for t in tables if t.slug == table_cfg.linked_dan_table), None)
            if source:
                table_cfg.dans = source.dans
            else:
                logger.warning(
                    "[%s] linked_dan_table '%s' not found",
                    table_cfg.slug, table_cfg.linked_dan_table,
                )

    tables.sort(key=lambda x: x.display_order)
    return RankingConfig(
        tables=tables,
        exp_level_step=exp_level_step,
        high_tier_rating_anchor=anchor,
        max_level=global_max_level,
    )


# ── Module-level cache ────────────────────────────────────────────────────────
_cached_config: RankingConfig | None = None


def get_ranking_config() -> RankingConfig:
    """Return the cached ranking config. Call init_ranking_config() first."""
    if _cached_config is None:
        raise RuntimeError("Ranking config not initialised. Call init_ranking_config() at startup.")
    return _cached_config


async def init_ranking_config(db_session) -> RankingConfig:
    """Load and cache ranking config. Called once during application lifespan."""
    global _cached_config
    _cached_config = await load_ranking_config(db_session)
    return _cached_config
