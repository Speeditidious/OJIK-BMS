"""Ranking calculation service.

Implements the per-chart rating formula (spec §2), EXP/Rating/BMSFORCE
aggregation (spec §4~§5), and on-demand history computation (spec, plan §Phase C).

Called by Celery tasks (post-sync single-user) and daily bulk recalculation.
"""
from __future__ import annotations

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ranking_config import (
    RankingConfig,
    TableRankingConfig,
    get_effective_dans,
)

# ── Clear-type integer → lamp name ───────────────────────────────────────────
# LR2 and Beatoraja share the same clear_type integer encoding.
# Confirmed from client/ojikbms_client/parsers/lr2.py and beatoraja.py.
CLEAR_TYPE_TO_LAMP_NAME: dict[int | None, str] = {
    None: "NOPLAY",
    0:    "NOPLAY",
    1:    "FAILED",
    2:    "ASSIST",
    3:    "EASY",
    4:    "NORMAL",
    5:    "HARD",
    6:    "EXHARD",
    7:    "FC",
    8:    "PERFECT",
    9:    "MAX",
}

RANK_ORDER = ["F", "E", "D", "C", "B", "A", "AA", "AAA"]


# ── Core data structures ──────────────────────────────────────────────────────

@dataclass
class BestScore:
    sha256: str | None
    md5: str | None
    level: str
    clear_type: int | None
    exscore: int | None
    rate: float | None      # DB stores 0–100 percentage; normalised to 0–1 inside _song_rating
    rank: str | None
    min_bp: int | None
    client_types: tuple[str, ...] = ()
    recorded_at: datetime | None = None
    sort_recorded_at: datetime | None = None


@dataclass
class RankingResult:
    user_id: uuid.UUID
    exp: float
    exp_level: int
    rating: float           # raw top-N sum (NEW meaning — not standardised)
    rating_norm: float      # BMSFORCE (standardised)
    rating_contributions: list[dict]
    exp_top_contributions: list[dict]
    dan_title: str | None


@dataclass
class RankingHistoryPoint:
    date: date
    exp: float
    exp_level: int
    rating: float       # raw top-N sum
    rating_norm: float  # BMSFORCE


# ── Per-chart formula helpers (spec §2) ──────────────────────────────────────

def _lamp_name(clear_type: int | None) -> str:
    return CLEAR_TYPE_TO_LAMP_NAME.get(clear_type, "NOPLAY")


def _f_bp(bp: float | None, floor: float, slope: float) -> float:
    """spec §2.3 — cosine easing. bp >= floor → 0, bp=0 → 1."""
    if bp is None or bp < 0 or bp >= floor:
        return 0.0
    x = ((floor - bp) / floor) ** slope
    return min((1 - math.cos(math.pi * x)) / 2, 1.0)


def _f_rate(rate: float | None, floor: float, slope: float) -> float:
    """spec §2.4 — rate in 0~1 scale. rate <= floor → 0, rate=1.0 → 1."""
    if rate is None or rate <= floor:
        return 0.0
    x = ((rate - floor) / (1 - floor)) ** slope
    return min((1 - math.cos(math.pi * x)) / 2, 1.0)


def _base(level: str, lamp: str, rank: str, cfg: TableRankingConfig) -> float:
    """spec §2.1 — Base without C_table."""
    level_weight = cfg.level_weights.get(level)
    if level_weight is None:
        return 0.0
    return (
        cfg.base_lamp_mult[lamp]
        * cfg.rank_mult.get(rank, 0.0)
        * (level_weight + cfg.upper_lamp_bonus[lamp])
    )


def _bonus(bp: float | None, rate: float | None, cfg: TableRankingConfig) -> float:
    """spec §2.2 — Bonus without C_table. rate in 0~1."""
    return (
        cfg.bonus.bp_weight * _f_bp(bp, cfg.bonus.bp_floor, cfg.bonus.bp_slope)
        + cfg.bonus.rate_weight * _f_rate(rate, cfg.bonus.rate_floor, cfg.bonus.rate_slope)
    )


def _resolve_level(
    fumen_sha256: str | None,
    fumen_md5: str | None,
    lamp: str,
    original_level: str,
    cfg: TableRankingConfig,
) -> str:
    """spec §6.2.9 + §9.1-4 — apply level_overrides for this fumen+lamp.

    Matching rules (CLAUDE.md 'Fumen hash lookups'):
      - override.fumen_sha256 matches fumen_sha256 → hit
      - else override.fumen_md5 matches fumen_md5 (LR2 fallback) → hit
    """
    for ov in cfg.level_overrides:
        sha_match = (
            ov.fumen_sha256 is not None
            and fumen_sha256 is not None
            and ov.fumen_sha256 == fumen_sha256
        )
        md5_match = (
            not sha_match
            and ov.fumen_md5 is not None
            and fumen_md5 is not None
            and ov.fumen_md5 == fumen_md5
        )
        if sha_match or md5_match:
            return ov.lamp_to_level.get(lamp, original_level)
    return original_level


def _song_rating(
    level: str,
    lamp: str,
    rank: str,
    bp: float | None,
    rate_01: float | None,   # already normalised 0~1
    cfg: TableRankingConfig,
) -> float:
    """spec §2 — per-chart rating = C_table × (Base + Bonus)."""
    if lamp == "NOPLAY":
        return 0.0
    return cfg.c_table * (_base(level, lamp, rank, cfg) + _bonus(bp, rate_01, cfg))


def _exp_level(total_exp: float, exp_level_step: float, max_level: int) -> int:
    """spec §5.1 — threshold(n) = K × n × (n+1), capped at max_level.

    K = exp_level_step (default 100).
    n = floor((-1 + sqrt(1 + 4·total_exp / K)) / 2)
    Float-error safety: while-loop bumps n if threshold(n+1) <= total_exp.
    """
    if total_exp <= 0:
        return 0
    step = exp_level_step
    max_threshold = step * max_level * (max_level + 1)
    if total_exp >= max_threshold:
        return max_level
    n = int((-1 + math.sqrt(1 + 4 * total_exp / step)) / 2)
    while step * (n + 1) * (n + 2) <= total_exp:
        n += 1
    return min(n, max_level)


def standardize_rating(raw_top_n: float, player_level: int) -> float:
    """spec §4.1 — BMSFORCE.

    adjusted = raw_top_n × (1 + player_level × 0.0001)
    if adjusted <= 100_000:  bms_force = adjusted / 5000
    else:                    bms_force = 20 + sqrt(4 × ((adjusted - 100_000) / 5000 + 1)) − 2
    """
    if raw_top_n <= 0:
        return 0.0
    adjusted = raw_top_n * (1 + player_level * 0.0001)
    if adjusted <= 100_000:
        return adjusted / 5000.0
    return 20.0 + math.sqrt(4 * ((adjusted - 100_000) / 5000.0 + 1)) - 2.0


def _merge_best_score_fields(
    existing: BestScore | None,
    row: dict[str, Any],
    level: str,
    canonical_sha256: str | None,
    canonical_md5: str | None,
) -> tuple[BestScore | None, bool]:
    """Merge one score row into the current best snapshot for a chart."""
    current = BestScore(
        sha256=canonical_sha256,
        md5=canonical_md5,
        level=level,
        clear_type=existing.clear_type if existing is not None else None,
        exscore=existing.exscore if existing is not None else None,
        rate=existing.rate if existing is not None else None,
        rank=existing.rank if existing is not None else None,
        min_bp=existing.min_bp if existing is not None else None,
        client_types=existing.client_types if existing is not None else (),
        recorded_at=existing.recorded_at if existing is not None else None,
        sort_recorded_at=existing.sort_recorded_at if existing is not None else None,
    )
    changed = False

    if row["clear_type"] is not None and (current.clear_type is None or row["clear_type"] > current.clear_type):
        current.clear_type = row["clear_type"]
        changed = True

    if row["exscore"] is not None and (current.exscore is None or row["exscore"] > current.exscore):
        current.exscore = row["exscore"]
        current.rate = float(row["rate"]) if row["rate"] is not None else None
        current.rank = row["rank"]
        changed = True

    if row["min_bp"] is not None and (current.min_bp is None or row["min_bp"] < current.min_bp):
        current.min_bp = row["min_bp"]
        changed = True

    if changed and row.get("client_type"):
        merged_types = set(current.client_types)
        merged_types.add(str(row["client_type"]))
        current.client_types = tuple(sorted(merged_types))
        current.recorded_at = row.get("recorded_at") or current.recorded_at
        current.sort_recorded_at = row.get("effective_ts") or row.get("latest_ts") or current.sort_recorded_at

    if not changed:
        return existing, False
    return current, True


# ── compute_ranking ───────────────────────────────────────────────────────────

def compute_ranking(
    table_cfg: TableRankingConfig,
    exp_level_step: float,
    scores: list[BestScore],
    fumen_titles: dict[tuple[str | None, str | None], str] | None = None,
) -> RankingResult:
    """spec §4~§5 — compute EXP, Rating (raw top-N), and BMSFORCE for one user.

    Flow:
      1. For each score: resolve lamp → level override → _song_rating.
         rate stored as 0–100 in DB → divide by 100 before _song_rating.
      2. total_exp = Σ all song_ratings (no top-N cut).
      3. player_level = _exp_level(total_exp, exp_level_step).
      4. raw_top_n = Σ top_N song_ratings DESC.
      5. rating_norm = standardize_rating(raw_top_n, player_level).
    """
    total_exp = 0.0
    positive_entries: list[tuple[float, dict[str, Any]]] = []

    for score in scores:
        lamp = _lamp_name(score.clear_type)
        level = _resolve_level(score.sha256, score.md5, lamp, score.level, table_cfg)

        # Normalise rate from DB's 0-100 to 0-1
        rate_01 = (score.rate / 100.0) if score.rate is not None else None

        value = _song_rating(
            level, lamp,
            score.rank or "F",
            float(score.min_bp) if score.min_bp is not None else None,
            rate_01,
            table_cfg,
        )

        total_exp += value

        hash_key = score.sha256 or score.md5 or ""
        title_key = (score.sha256, score.md5)
        title = (fumen_titles or {}).get(title_key, "")

        if value > 0:
            entry = {
                "hash": hash_key,
                "level": score.level,
                "song_rating": round(value, 3),
                "title": title,
            }
            positive_entries.append((value, entry))

    # Top-N rating
    positive_entries.sort(key=lambda x: x[0], reverse=True)
    top_n = table_cfg.top_n
    top_ratings = positive_entries[:top_n]
    raw_top_n = sum(v for v, _ in top_ratings)
    rating_contributions = [c for _, c in top_ratings]

    # EXP top-20
    exp_top = [{**entry, "song_exp": round(value, 3)} for value, entry in positive_entries[:20]]

    player_level = _exp_level(total_exp, exp_level_step, table_cfg.max_level)
    rating_norm = standardize_rating(raw_top_n, player_level)

    return RankingResult(
        user_id=uuid.UUID(int=0),   # caller sets this
        exp=total_exp,
        exp_level=player_level,
        rating=raw_top_n,
        rating_norm=rating_norm,
        rating_contributions=rating_contributions,
        exp_top_contributions=exp_top,
        dan_title=None,             # caller sets this
    )


# ── History computation (on-demand, spec plan §Phase C) ──────────────────────

async def compute_ranking_history_for_user(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    cfg: RankingConfig,
    from_date: date,
    to_date: date,
    db: AsyncSession,
) -> list[RankingHistoryPoint]:
    """Compute day-by-day EXP/Rating/BMSFORCE for [from_date, to_date] from user_scores.

    Algorithm (single DB pass):
      1. Load all scores for this user+table, ordered by effective_date ASC.
      2. Maintain best_per_fumen dict (key = (sha256, md5)).
         For each score, improvement-check (exscore) before replacing.
      3. Walk from_date to to_date; compute_ranking at each date boundary.
         Dates with no score change reuse the previous point (no recalculation).

    LR2 records (sha256=NULL) are merged by md5 key per CLAUDE.md 'Fumen hash lookups'.
    """
    # 1. Load all target fumen hashes for this table
    fumen_result = await db.execute(
        text("""
            SELECT f.sha256, f.md5,
                   entry->>'level' AS level
            FROM fumens f,
                 jsonb_array_elements(f.table_entries) AS entry
            WHERE (entry->>'table_id')::uuid = :table_id
        """),
        {"table_id": str(table_cfg.table_id)},
    )
    table_fumens = fumen_result.mappings().all()

    # Build sha256→md5 pair map for LR2 merge
    sha256_to_md5: dict[str, str | None] = {}
    md5_to_sha256: dict[str, str | None] = {}
    fumen_levels: dict[tuple[str | None, str | None], str] = {}
    for row in table_fumens:
        sha = row["sha256"]
        md5 = row["md5"]
        fumen_levels[(sha, md5)] = row["level"]
        if sha:
            sha256_to_md5[sha] = md5
        if md5:
            md5_to_sha256[md5] = sha

    # 2. Load all user scores for this table, ordered by effective_date
    result = await db.execute(
        text("""
            SELECT
                us.fumen_sha256, us.fumen_md5,
                us.clear_type, us.exscore, us.rate, us.rank, us.min_bp,
                us.client_type,
                COALESCE(us.recorded_at, us.synced_at)::date AS effective_date
            FROM user_scores us
            WHERE us.user_id = :user_id
              AND us.fumen_hash_others IS NULL
              AND (
                  us.fumen_sha256 IN (
                      SELECT sha256 FROM fumens f2,
                          jsonb_array_elements(f2.table_entries) AS e2
                      WHERE (e2->>'table_id')::uuid = :table_id
                        AND f2.sha256 IS NOT NULL
                  )
                  OR (
                      us.fumen_sha256 IS NULL
                      AND us.fumen_md5 IN (
                          SELECT md5 FROM fumens f3,
                              jsonb_array_elements(f3.table_entries) AS e3
                          WHERE (e3->>'table_id')::uuid = :table_id
                            AND f3.md5 IS NOT NULL
                      )
                  )
              )
            ORDER BY effective_date ASC NULLS LAST
        """),
        {"user_id": str(user_id), "table_id": str(table_cfg.table_id)},
    )
    raw_rows = result.mappings().all()

    # 3. Group rows by effective_date
    from collections import defaultdict
    rows_by_date: dict[date, list] = defaultdict(list)
    for row in raw_rows:
        d = row["effective_date"]
        if d is not None:
            rows_by_date[d].append(row)

    # Helper: canonical key for a score row (LR2 md5-based merging)
    def canonical_key(sha: str | None, md5: str | None) -> tuple[str | None, str | None]:
        """Map LR2 row (sha=None, md5=X) to same key as Beatoraja row (sha=Y, md5=X)."""
        if sha is not None:
            return (sha, sha256_to_md5.get(sha))
        if md5 is not None:
            paired_sha = md5_to_sha256.get(md5)
            return (paired_sha, md5)
        return (None, None)

    # best_per_fumen: key → BestScore
    best_per_fumen: dict[tuple[str | None, str | None], BestScore] = {}

    def apply_scores(row_list: list) -> None:
        for row in row_list:
            sha = row["fumen_sha256"]
            md5 = row["fumen_md5"]
            key = canonical_key(sha, md5)
            level = fumen_levels.get(key) or fumen_levels.get((sha, md5), "")
            if not level:
                continue
            existing = best_per_fumen.get(key)
            merged, changed = _merge_best_score_fields(existing, row, level, key[0], key[1])
            if changed and merged is not None:
                best_per_fumen[key] = merged

    # 4. Walk date range, maintain running best_per_fumen
    from datetime import timedelta

    all_dates_with_data = sorted(d for d in rows_by_date if d <= to_date)

    # Pre-apply all scores strictly before from_date
    pre_dates = [d for d in all_dates_with_data if d < from_date]
    for d in pre_dates:
        apply_scores(rows_by_date[d])

    points: list[RankingHistoryPoint] = []
    prev_result: RankingResult | None = None

    dates_in_range = sorted(d for d in all_dates_with_data if from_date <= d <= to_date)
    dates_cursor = 0

    current = from_date
    while current <= to_date:
        # Apply all scores that occurred on this date
        changed = False
        if dates_cursor < len(dates_in_range) and dates_in_range[dates_cursor] == current:
            apply_scores(rows_by_date[current])
            dates_cursor += 1
            changed = True

        if changed or prev_result is None:
            r = compute_ranking(
                table_cfg, cfg.exp_level_step, list(best_per_fumen.values())
            )
            r.user_id = user_id
            prev_result = r

        points.append(RankingHistoryPoint(
            date=current,
            exp=prev_result.exp,
            exp_level=prev_result.exp_level,
            rating=prev_result.rating,
            rating_norm=prev_result.rating_norm,
        ))
        current += timedelta(days=1)

    return points


# ── DB query helpers ──────────────────────────────────────────────────────────

async def query_target_fumens(
    table_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    """Return [{sha256, md5, level}] for all fumens in the given table."""
    result = await db.execute(
        text("""
            SELECT f.sha256, f.md5,
                   entry->>'level' AS level
            FROM fumens f,
                 jsonb_array_elements(f.table_entries) AS entry
            WHERE (entry->>'table_id')::uuid = :table_id
        """),
        {"table_id": str(table_id)},
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]


async def bulk_query_best_scores(
    table_id: uuid.UUID,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, list[BestScore]]:
    """Bulk-fetch best scores for all users (or single user) for a table's fumens.

    Returns {user_id: [BestScore, ...]}
    """
    params: dict[str, Any] = {"table_id": str(table_id)}
    user_filter = ""
    if user_id is not None:
        user_filter = "AND us.user_id = :user_id"
        params["user_id"] = str(user_id)

    result = await db.execute(
        text(f"""
            WITH target_fumens AS (
                SELECT f.sha256, f.md5,
                       entry->>'level' AS level
                FROM fumens f,
                     jsonb_array_elements(f.table_entries) AS entry
                WHERE (entry->>'table_id')::uuid = :table_id
            ),
            latest_per_client AS (
                SELECT
                    us.user_id,
                    us.fumen_sha256,
                    us.fumen_md5,
                    us.client_type,
                    us.clear_type, us.exscore, us.rate, us.rank, us.min_bp,
                    CASE
                        WHEN us.recorded_at IS NOT NULL THEN us.recorded_at
                        WHEN us.synced_at IS NULL THEN NULL
                        WHEN u.first_synced_at IS NULL THEN us.synced_at
                        WHEN u.first_synced_at->>us.client_type IS NULL THEN us.synced_at
                        WHEN us.synced_at <= ((u.first_synced_at->>us.client_type)::timestamptz + interval '1 hour') THEN NULL
                        ELSE us.synced_at
                    END AS display_recorded_at,
                    COALESCE(us.recorded_at, us.synced_at) AS latest_ts,
                    ROW_NUMBER() OVER (
                        PARTITION BY us.user_id,
                                     COALESCE(us.fumen_sha256, us.fumen_md5),
                                     us.client_type
                        ORDER BY COALESCE(us.recorded_at, us.synced_at) DESC
                    ) AS rn
                FROM user_scores us
                JOIN users u ON u.id = us.user_id
                WHERE us.fumen_hash_others IS NULL
                  {user_filter}
                  AND (
                      (us.fumen_sha256 IS NOT NULL
                        AND us.fumen_sha256 IN (SELECT sha256 FROM target_fumens WHERE sha256 IS NOT NULL))
                      OR (us.fumen_md5 IS NOT NULL
                        AND us.fumen_md5 IN (SELECT md5 FROM target_fumens WHERE md5 IS NOT NULL))
                  )
            ),
            joined AS (
                -- sha256 경로: sha256 이 기록된 행과 tf.sha256 매칭
                SELECT lpc.user_id, tf.sha256 AS tf_sha256, tf.md5 AS tf_md5, tf.level,
                       lpc.client_type, lpc.clear_type, lpc.exscore, lpc.rate, lpc.rank, lpc.min_bp,
                       lpc.display_recorded_at, lpc.latest_ts
                FROM latest_per_client lpc
                JOIN target_fumens tf ON lpc.fumen_sha256 = tf.sha256
                WHERE lpc.rn = 1 AND lpc.fumen_sha256 IS NOT NULL
                UNION ALL
                -- md5 경로: LR2 또는 tf.sha256=null 인 fumen 에 대한 Beatoraja 기록
                SELECT lpc.user_id, tf.sha256 AS tf_sha256, tf.md5 AS tf_md5, tf.level,
                       lpc.client_type, lpc.clear_type, lpc.exscore, lpc.rate, lpc.rank, lpc.min_bp,
                       lpc.display_recorded_at, lpc.latest_ts
                FROM latest_per_client lpc
                JOIN target_fumens tf ON lpc.fumen_md5 = tf.md5
                WHERE lpc.rn = 1 AND lpc.fumen_md5 IS NOT NULL
            ),
            best_scores AS (
                SELECT
                    user_id,
                    tf_sha256, tf_md5, level,
                    MAX(clear_type) AS clear_type,
                    MAX(exscore) AS exscore,
                    (array_agg(rate ORDER BY exscore DESC NULLS LAST))[1] AS rate,
                    (array_agg(rank ORDER BY exscore DESC NULLS LAST))[1] AS rank,
                    MIN(min_bp) AS min_bp,
                    array_agg(DISTINCT client_type) AS client_types,
                    (array_agg(display_recorded_at ORDER BY latest_ts DESC NULLS LAST))[1] AS recorded_at,
                    MAX(latest_ts) AS latest_ts
                FROM joined
                GROUP BY user_id, tf_sha256, tf_md5, level
            )
            SELECT
                user_id,
                tf_sha256 AS sha256,
                tf_md5 AS md5,
                level,
                clear_type, exscore, rate, rank, min_bp, client_types, recorded_at, latest_ts
            FROM best_scores
        """),
        params,
    )
    rows = result.mappings().all()

    user_scores: dict[uuid.UUID, list[BestScore]] = defaultdict(list)
    for row in rows:
        uid = uuid.UUID(str(row["user_id"]))
        user_scores[uid].append(BestScore(
            sha256=row["sha256"],
            md5=row["md5"],
            level=row["level"],
            clear_type=row["clear_type"],
            exscore=row["exscore"],
            rate=float(row["rate"]) if row["rate"] is not None else None,
            rank=row["rank"],
            min_bp=row["min_bp"],
            client_types=tuple(sorted(row["client_types"] or ())),
            recorded_at=row["recorded_at"],
            sort_recorded_at=row["latest_ts"],
        ))
    return user_scores


def _partial_sha256_match(stored: str, sha_list: list[str | None]) -> bool:
    """Check Beatoraja fumen_hash_others against a partially-known sha256 list.

    sha_list contains sha256 values for each course member in order.
    None positions are treated as wildcards (any 64-char hex accepted).
    stored must be exactly 64 * len(sha_list) characters long.
    """
    if len(stored) != 64 * len(sha_list):
        return False
    for i, sha in enumerate(sha_list):
        if sha is None:
            continue
        if stored[i * 64 : (i + 1) * 64] != sha:
            return False
    return True


async def check_dan_clearance(
    user_id: uuid.UUID,
    table_cfg: TableRankingConfig,
    config: RankingConfig,
    db: AsyncSession,
) -> str | None:
    """Return the highest-priority cleared dan_title for a user, or None."""
    dans = get_effective_dans(table_cfg, config)
    if not dans:
        return None

    from app.models.course import Course

    cleared_dans: list[str] = []
    for dan in dans:
        source_slug = dan.source_table or table_cfg.slug
        source_cfg = config.get_table_by_slug(source_slug)
        source_table_id = source_cfg.table_id if source_cfg else table_cfg.table_id

        course_result = await db.execute(
            select(Course).where(
                Course.source_table_id == source_table_id,
                Course.name == dan.course_name,
                Course.is_active.is_(True),
            )
        )
        course = course_result.scalar_one_or_none()
        if course is None:
            continue

        md5_list = course.md5_list or []
        if not md5_list:
            continue
        joined_md5 = "".join(str(m) for m in md5_list if m)
        sha256_list = course.sha256_list or []
        # Build partial-match LIKE pattern: None positions → '_' × 64 (SQL LIKE wildcard).
        # Only activate Beatoraja matching when at least one sha256 is known.
        bea_pattern: str | None = None
        if (
            sha256_list
            and len(sha256_list) == len(md5_list)
            and any(s for s in sha256_list)
        ):
            bea_pattern = "".join(s if s else "_" * 64 for s in sha256_list)

        conditions: list[str] = []
        params: dict[str, Any] = {"user_id": str(user_id)}
        if joined_md5:
            conditions.append("fumen_hash_others LIKE :lr2_pattern")
            params["lr2_pattern"] = f"%{joined_md5}"
        if bea_pattern:
            # sha256 hex contains only 0-9a-f, so '_' and '%' escaping is unnecessary
            conditions.append("fumen_hash_others LIKE :bea_pattern")
            params["bea_pattern"] = bea_pattern
        if not conditions:
            continue

        score_result = await db.execute(
            text(f"""
                SELECT MAX(clear_type) AS best_clear
                FROM user_scores
                WHERE user_id = :user_id
                  AND ({' OR '.join(conditions)})
            """),
            params,
        )
        best_clear = score_result.scalar_one_or_none()
        if best_clear is not None and best_clear >= 2:
            cleared_dans.append(dan.dan_title)

    if not cleared_dans:
        return None

    cleared_set = set(cleared_dans)
    candidates = [d for d in dans if d.dan_title in cleared_set]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.priority).dan_title


# ── UPSERT helpers ────────────────────────────────────────────────────────────

async def upsert_user_ranking(
    result: RankingResult,
    table_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """INSERT OR UPDATE a single user's ranking row."""
    import json
    await db.execute(
        text("""
            INSERT INTO user_rankings
                (user_id, table_id, exp, exp_level, rating, rating_norm,
                 rating_contributions, exp_top_contributions, dan_title, calculated_at)
            VALUES
                (:user_id, :table_id, :exp, :exp_level, :rating, :rating_norm,
                 CAST(:rating_contributions AS jsonb), CAST(:exp_top_contributions AS jsonb),
                 :dan_title, :calculated_at)
            ON CONFLICT (user_id, table_id) DO UPDATE SET
                exp = EXCLUDED.exp,
                exp_level = EXCLUDED.exp_level,
                rating = EXCLUDED.rating,
                rating_norm = EXCLUDED.rating_norm,
                rating_contributions = EXCLUDED.rating_contributions,
                exp_top_contributions = EXCLUDED.exp_top_contributions,
                dan_title = EXCLUDED.dan_title,
                calculated_at = EXCLUDED.calculated_at
        """),
        {
            "user_id": str(result.user_id),
            "table_id": str(table_id),
            "exp": result.exp,
            "exp_level": result.exp_level,
            "rating": result.rating,
            "rating_norm": result.rating_norm,
            "rating_contributions": json.dumps(result.rating_contributions),
            "exp_top_contributions": json.dumps(result.exp_top_contributions),
            "dan_title": result.dan_title,
            "calculated_at": datetime.now(UTC),
        },
    )


async def get_prev_ranking(
    user_id: uuid.UUID,
    table_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[float, float, float]:
    """Return (prev_exp, prev_rating, prev_rating_norm) or (0, 0, 0) if not found."""
    row = await db.execute(
        text("""
            SELECT exp, rating, rating_norm FROM user_rankings
            WHERE user_id = :user_id AND table_id = :table_id
        """),
        {"user_id": str(user_id), "table_id": str(table_id)},
    )
    result = row.one_or_none()
    if result is None:
        return 0.0, 0.0, 0.0
    return float(result[0]), float(result[1]), float(result[2])


# ── Per-user recalculation (post-sync) ───────────────────────────────────────

async def recalculate_user(
    user_id: uuid.UUID,
    config: RankingConfig,
    db: AsyncSession,
) -> None:
    """Recalculate all table rankings for a single user."""
    from app.services.rating_derived_data import rebuild_user_rating_derived_data

    for table_cfg in config.tables:
        user_scores_map = await bulk_query_best_scores(table_cfg.table_id, db, user_id=user_id)
        scores = user_scores_map.get(user_id, [])

        result = compute_ranking(table_cfg, config.exp_level_step, scores)
        result.user_id = user_id
        result.dan_title = await check_dan_clearance(user_id, table_cfg, config, db)

        await upsert_user_ranking(result, table_cfg.table_id, db)

    await rebuild_user_rating_derived_data(user_id, config, db)


async def batch_check_dan_clearance(
    user_ids: set[uuid.UUID],
    table_cfg: TableRankingConfig,
    config: RankingConfig,
    db: AsyncSession,
) -> dict[uuid.UUID, str | None]:
    """Batch dan clearance check for multiple users (~14 queries instead of N×14)."""
    dans = get_effective_dans(table_cfg, config)
    if not dans or not user_ids:
        return {uid: None for uid in user_ids}

    from app.models.course import Course

    course_hashes_map: list[tuple] = []
    for dan in dans:
        source_slug = dan.source_table or table_cfg.slug
        source_cfg = config.get_table_by_slug(source_slug)
        source_table_id = source_cfg.table_id if source_cfg else table_cfg.table_id

        course_result = await db.execute(
            select(Course).where(
                Course.source_table_id == source_table_id,
                Course.name == dan.course_name,
                Course.is_active.is_(True),
            )
        )
        course = course_result.scalar_one_or_none()
        if not course or not course.md5_list:
            continue
        joined_md5 = "".join(m for m in course.md5_list if m)
        sha256_list = course.sha256_list or []
        bea_sha_list: list[str | None] | None = None
        if (
            sha256_list
            and len(sha256_list) == len(course.md5_list)
            and any(s for s in sha256_list)
        ):
            bea_sha_list = list(sha256_list)
        if joined_md5 or bea_sha_list:
            course_hashes_map.append((dan, joined_md5, bea_sha_list))

    if not course_hashes_map:
        return {uid: None for uid in user_ids}

    result = await db.execute(
        text("""
            SELECT user_id, client_type, fumen_hash_others, MAX(clear_type) AS best_clear
            FROM user_scores
            WHERE user_id = ANY(:user_ids)
              AND fumen_hash_others IS NOT NULL
            GROUP BY user_id, client_type, fumen_hash_others
        """),
        {"user_ids": [str(uid) for uid in user_ids]},
    )

    clearance_map: dict[tuple[uuid.UUID, int], int] = {}
    for row in result.mappings().all():
        uid = uuid.UUID(str(row["user_id"]))
        stored_hash = row["fumen_hash_others"] or ""
        client = row["client_type"]
        best_clear = row["best_clear"]
        for i, (dan, joined_md5, bea_sha_list) in enumerate(course_hashes_map):
            matched = False
            if client == "lr2" and joined_md5 and stored_hash.endswith(joined_md5):
                matched = True
            elif client == "beatoraja" and bea_sha_list:
                matched = _partial_sha256_match(stored_hash, bea_sha_list)
            if matched:
                key = (uid, i)
                if key not in clearance_map or best_clear > clearance_map[key]:
                    clearance_map[key] = best_clear

    user_dans: dict[uuid.UUID, str | None] = {}
    for uid in user_ids:
        cleared = []
        for i, (dan, _jmd5, _bsl) in enumerate(course_hashes_map):
            bc = clearance_map.get((uid, i))
            if bc is not None and bc >= 2:
                cleared.append(dan)
        if cleared:
            best_dan = max(cleared, key=lambda d: d.priority)
            user_dans[uid] = best_dan.dan_title
        else:
            user_dans[uid] = None

    return user_dans


# ── Bulk recalculation (daily batch) ─────────────────────────────────────────

async def recalculate_table_bulk(
    table_cfg: TableRankingConfig,
    config: RankingConfig,
    db: AsyncSession,
) -> int:
    """Recalculate rankings for all users in a table. Returns number of users processed."""
    from app.services.rating_derived_data import rebuild_user_rating_derived_data

    all_scores = await bulk_query_best_scores(table_cfg.table_id, db)
    if not all_scores:
        return 0

    recently_synced_result = await db.execute(
        text("""
            SELECT DISTINCT us.user_id
            FROM user_scores us
            LEFT JOIN user_rankings ur
                ON ur.user_id = us.user_id AND ur.table_id = :table_id
            WHERE us.synced_at > COALESCE(ur.calculated_at, '1970-01-01'::timestamptz)
        """),
        {"table_id": str(table_cfg.table_id)},
    )
    recently_synced = {uuid.UUID(str(r[0])) for r in recently_synced_result.all()}

    existing_dans_result = await db.execute(
        text("""
            SELECT user_id, dan_title FROM user_rankings WHERE table_id = :table_id
        """),
        {"table_id": str(table_cfg.table_id)},
    )
    existing_dans = {uuid.UUID(str(r[0])): r[1] for r in existing_dans_result.all()}

    dan_refresh_targets = {
        user_id
        for user_id in all_scores
        if user_id in recently_synced or existing_dans.get(user_id) is None
    }
    dan_results = await batch_check_dan_clearance(dan_refresh_targets, table_cfg, config, db)

    processed = 0
    for user_id, scores in all_scores.items():
        result = compute_ranking(table_cfg, config.exp_level_step, scores)
        result.user_id = user_id

        if user_id in dan_refresh_targets:
            result.dan_title = dan_results.get(user_id)
        else:
            result.dan_title = existing_dans.get(user_id)

        await upsert_user_ranking(result, table_cfg.table_id, db)
        await rebuild_user_rating_derived_data(user_id, config, db)
        processed += 1

    return processed
