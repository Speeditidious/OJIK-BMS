"""Rankings API router."""
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.user import User
from app.services.ranking_config import (
    RankingConfig,
    TableRankingConfig,
    find_dan_config,
    get_ranking_config,
)
from app.services.ranking_dashboard import (
    build_user_contribution_rows,
    compute_exp_progress_fields,
    get_user_ranking_version,
)

router = APIRouter(prefix="/rankings", tags=["rankings"])
_CONTRIBUTION_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_dan_decoration(
    dan_title: str | None,
    table_cfg: TableRankingConfig,
    config: RankingConfig,
) -> dict | None:
    """Resolve dan_title string → decoration dict from TOML config."""
    dan = find_dan_config(dan_title, table_cfg, config)
    if dan is not None:
        return {
            "dan_title": dan.dan_title,
            "display_text": dan.display_text,
            "color": dan.color,
            "glow_intensity": dan.glow_intensity,
        }
    return None


def _best_dan_across_tables(
    title_a: str | None,
    cfg_a: TableRankingConfig,
    title_b: str | None,
    cfg_b: TableRankingConfig,
) -> tuple[str | None, TableRankingConfig]:
    """두 테이블의 dan_title을 비교해 global 우선순위가 높은 쪽을 반환.

    global_priority = cross_dan_tier * 10000 + dan.priority
    cross_dan_tier 가 높은 테이블(stella=2)이 낮은 테이블(satellite=1)보다 항상 우선.
    """
    def global_priority(title: str | None, cfg: TableRankingConfig) -> int:
        if not title:
            return -1
        for d in cfg.dans:
            if d.dan_title == title:
                return cfg.cross_dan_tier * 10000 + d.priority
        return -1

    if global_priority(title_a, cfg_a) >= global_priority(title_b, cfg_b):
        return title_a, cfg_a
    return title_b, cfg_b


def _get_config_or_503() -> RankingConfig:
    try:
        return get_ranking_config()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Ranking config not initialised")


async def _resolve_target_user(
    user_id: uuid.UUID | None,
    current_user: User | None,
    db: AsyncSession,
) -> User:
    """Resolve the requested ranking target user."""
    if user_id is None:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return current_user

    if current_user is not None and current_user.id == user_id:
        return current_user

    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if target_user is None or not target_user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    return target_user


# ── GET /rankings/tables ──────────────────────────────────────────────────────

@router.get("/tables")
async def list_ranking_tables() -> list[dict[str, Any]]:
    """Return the list of ranking-enabled difficulty tables."""
    try:
        config = get_ranking_config()
    except RuntimeError:
        return []

    return [
        {
            "slug": t.slug,
            "table_id": str(t.table_id),
            "display_name": t.display_name,
            "display_order": t.display_order,
            "top_n": t.top_n,
            "has_exp": True,
            "has_rating": True,
            "has_bmsforce": True,
            "dan_decorations": [d.dan_title for d in t.dans],
        }
        for t in sorted(config.tables, key=lambda table: table.display_order)
    ]


# ── GET /rankings/{table_slug} ────────────────────────────────────────────────

@router.get("/{table_slug}/history")
async def get_ranking_history(
    table_slug: str,
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    user_id: uuid.UUID | None = Query(None),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return day-by-day EXP/Rating/BMSFORCE for a user over [from, to].

    History is computed on-demand from user_scores (no stored snapshots).
    This means formula changes are immediately reflected in all historical values.
    """
    config = _get_config_or_503()

    target_uid = user_id or (current_user.id if current_user else None)
    if target_uid is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if to < from_:
        raise HTTPException(status_code=400, detail="'from' must be <= 'to'")
    if (to - from_).days > 400:
        raise HTTPException(status_code=400, detail="Date range too large (max 400 days)")

    table_cfg = config.get_table_by_slug(table_slug)
    if table_cfg is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_slug}' not found")

    from app.services.ranking_calculator import compute_ranking_history_for_user
    points = await compute_ranking_history_for_user(
        target_uid, table_cfg, config, from_, to, db
    )

    return {
        "table_slug": table_slug,
        "user_id": str(target_uid),
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "points": [
            {
                "date": p.date.isoformat(),
                "exp": round(p.exp, 2),
                "exp_level": p.exp_level,
                "rating": round(p.rating, 2),
                "rating_norm": round(p.rating_norm, 3),
            }
            for p in points
        ],
    }


@router.get("/{table_slug}/me")
async def get_my_rank(
    table_slug: str,
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the authenticated user's ranking data for a table."""
    target_user = await _resolve_target_user(user_id, current_user, db)
    config = _get_config_or_503()

    table_cfg = config.get_table_by_slug(table_slug)
    if table_cfg is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_slug}' not found")

    row = await db.execute(
        text("""
            SELECT ur.exp, ur.exp_level, ur.rating, ur.rating_norm, ur.dan_title,
                   ur.rating_contributions, ur.exp_top_contributions,
                   ur.calculated_at
            FROM user_rankings ur
            WHERE ur.user_id = :user_id AND ur.table_id = :table_id
        """),
        {"user_id": str(target_user.id), "table_id": str(table_cfg.table_id)},
    )
    ranking = row.mappings().one_or_none()
    if ranking is None:
        score_exists = await db.execute(
            text("SELECT 1 FROM user_scores WHERE user_id = :uid LIMIT 1"),
            {"uid": str(target_user.id)},
        )
        has_scores = score_exists.scalar_one_or_none() is not None
        progress_fields = compute_exp_progress_fields(
            0.0,
            0,
            config.exp_level_step,
            table_cfg.max_level,
        )
        return {
            "table_slug": table_slug,
            "status": "pending" if has_scores else "no_scores",
            "exp": 0, "exp_level": 0, "exp_rank": 0, "exp_total_users": 0,
            "rating": 0.0, "rating_rank": 0, "rating_total_users": 0,
            "rating_norm": 0.0, "rating_norm_rank": 0, "rating_norm_total_users": 0,
            "last_synced_at": None, "calculated_at": None,
            "dan_decoration": None,
            "top_n": table_cfg.top_n,
            "max_level": table_cfg.max_level,
            **progress_fields,
            "rating_contributions": [], "exp_top_contributions": [],
        }

    my_exp = float(ranking["exp"])
    my_rating = float(ranking["rating"])
    my_rating_norm = float(ranking["rating_norm"])
    table_id_str = str(table_cfg.table_id)

    exp_rank_result = await db.execute(
        text("SELECT COUNT(*) + 1 FROM user_rankings WHERE table_id = :t AND exp > :v"),
        {"t": table_id_str, "v": my_exp},
    )
    exp_rank = exp_rank_result.scalar_one()

    rating_rank_result = await db.execute(
        text("SELECT COUNT(*) + 1 FROM user_rankings WHERE table_id = :t AND rating > :v"),
        {"t": table_id_str, "v": my_rating},
    )
    rating_rank = rating_rank_result.scalar_one()

    rating_norm_rank_result = await db.execute(
        text("SELECT COUNT(*) + 1 FROM user_rankings WHERE table_id = :t AND rating_norm > :v"),
        {"t": table_id_str, "v": my_rating_norm},
    )
    rating_norm_rank = rating_norm_rank_result.scalar_one()

    total_result = await db.execute(
        text("SELECT COUNT(*) FROM user_rankings WHERE table_id = :t"),
        {"t": table_id_str},
    )
    total_users = total_result.scalar_one()

    last_synced_result = await db.execute(
        text("SELECT MAX(synced_at) FROM user_scores WHERE user_id = :uid"),
        {"uid": str(target_user.id)},
    )
    last_synced_at = last_synced_result.scalar_one()

    # cross-table 최고단 resolve: satellite ↔ stella
    my_dan_title = ranking["dan_title"]
    my_dan_cfg = table_cfg
    if table_cfg.cross_dan_peer:
        peer_cfg = config.get_table_by_slug(table_cfg.cross_dan_peer)
        if peer_cfg is not None:
            peer_row = await db.execute(
                text("""
                    SELECT dan_title
                    FROM user_rankings
                    WHERE user_id = :user_id AND table_id = :peer_table_id
                """),
                {"user_id": str(target_user.id), "peer_table_id": str(peer_cfg.table_id)},
            )
            peer_dan = peer_row.scalar_one_or_none()
            my_dan_title, my_dan_cfg = _best_dan_across_tables(
                my_dan_title, table_cfg, peer_dan, peer_cfg
            )

    dan_deco = _resolve_dan_decoration(my_dan_title, my_dan_cfg, config)
    progress_fields = compute_exp_progress_fields(
        my_exp,
        ranking["exp_level"],
        config.exp_level_step,
        table_cfg.max_level,
    )

    return {
        "table_slug": table_slug,
        "status": "ok",
        "exp": round(my_exp, 2),
        "exp_level": ranking["exp_level"],
        "exp_rank": exp_rank,
        "exp_total_users": total_users,
        "rating": round(my_rating, 2),
        "rating_rank": rating_rank,
        "rating_total_users": total_users,
        "rating_norm": round(my_rating_norm, 3),
        "rating_norm_rank": rating_norm_rank,
        "rating_norm_total_users": total_users,
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        "calculated_at": ranking["calculated_at"].isoformat(),
        "dan_decoration": dan_deco,
        "top_n": table_cfg.top_n,
        "max_level": table_cfg.max_level,
        **progress_fields,
        "rating_contributions": ranking["rating_contributions"] or [],
        "exp_top_contributions": ranking["exp_top_contributions"] or [],
    }


@router.get("/{table_slug}/me/contributions")
async def get_my_contributions(
    table_slug: str,
    metric: str = Query("exp", pattern="^(exp|rating)$"),
    scope: str = Query("top", pattern="^(top|all)$"),
    sort_by: str = Query(
        "value",
        pattern="^(value|level|title|clear_type|min_bp|rate|rank_grade|env)$",
    ),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
    query: str | None = Query(None, max_length=200),
    user_id: uuid.UUID | None = Query(None, description="Target user ID"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return contribution rows for the authenticated user's rating detail view."""
    target_user = await _resolve_target_user(user_id, current_user, db)
    config = _get_config_or_503()

    table_cfg = config.get_table_by_slug(table_slug)
    if table_cfg is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_slug}' not found")

    table_row = await db.execute(
        text("SELECT symbol FROM difficulty_tables WHERE id = :table_id"),
        {"table_id": str(table_cfg.table_id)},
    )
    table_symbol = table_row.scalar_one_or_none() or ""

    max_synced_at, calculated_at = await get_user_ranking_version(target_user.id, table_cfg.table_id, db)
    effective_sort_by = "value" if scope == "top" else sort_by
    effective_sort_dir = "desc" if scope == "top" else sort_dir
    cache_key = (
        str(target_user.id),
        table_slug,
        metric,
        scope,
        effective_sort_by,
        effective_sort_dir,
        page,
        limit,
        query or "",
        max_synced_at,
        calculated_at,
    )
    cached = _CONTRIBUTION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    payload = await build_user_contribution_rows(
        user_id=target_user.id,
        table_cfg=table_cfg,
        db=db,
        metric=metric,
        scope=scope,
        sort_by=effective_sort_by,
        sort_dir=effective_sort_dir,
        page=page,
        limit=limit,
        query=query,
        table_symbol=table_symbol,
    )
    response = {
        "table_slug": table_slug,
        "metric": metric,
        "scope": scope,
        "calculated_at": calculated_at,
        **payload,
    }
    _CONTRIBUTION_CACHE[cache_key] = response
    return response


@router.get("/{table_slug}")
async def get_rankings(
    table_slug: str,
    type: str = Query(..., pattern="^(exp|rating|bmsforce)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return paginated ranking entries for a table.

    type: "exp" → sort by exp | "rating" → sort by raw top-N | "bmsforce" → sort by rating_norm
    """
    config = _get_config_or_503()

    table_cfg = config.get_table_by_slug(table_slug)
    if table_cfg is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_slug}' not found")

    offset = (page - 1) * limit

    order_col = {
        "exp": "exp",
        "rating": "rating",
        "bmsforce": "rating_norm",
    }[type]

    result = await db.execute(
        text(f"""
            SELECT
                ur.user_id, ur.exp, ur.exp_level, ur.rating, ur.rating_norm,
                ur.dan_title,
                u.username,
                COALESCE(u.avatar_url, oa.discord_avatar_url) AS avatar_url,
                COUNT(*) OVER () AS total_count
            FROM user_rankings ur
            JOIN users u ON u.id = ur.user_id
            LEFT JOIN oauth_accounts oa
                ON oa.user_id = u.id AND oa.provider = 'discord'
            WHERE ur.table_id = :table_id
            ORDER BY ur.{order_col} DESC
            LIMIT :limit OFFSET :offset
        """),
        {"table_id": str(table_cfg.table_id), "limit": limit, "offset": offset},
    )
    rows = result.mappings().all()

    # cross-table 최고단 resolve: satellite ↔ stella
    peer_dan_by_uid: dict[str, str | None] = {}
    peer_cfg: TableRankingConfig | None = None
    if rows and table_cfg.cross_dan_peer:
        peer_cfg = config.get_table_by_slug(table_cfg.cross_dan_peer)
        if peer_cfg is not None:
            user_ids = [str(row["user_id"]) for row in rows]
            peer_result = await db.execute(
                text("""
                    SELECT user_id::text, dan_title
                    FROM user_rankings
                    WHERE table_id = :peer_table_id
                      AND user_id = ANY(:user_ids)
                """),
                {"peer_table_id": str(peer_cfg.table_id), "user_ids": user_ids},
            )
            for pr in peer_result.mappings().all():
                peer_dan_by_uid[pr["user_id"]] = pr["dan_title"]

    total_count = rows[0]["total_count"] if rows else 0
    entries = []
    for i, row in enumerate(rows):
        rank = offset + i + 1
        uid_str = str(row["user_id"])
        if peer_cfg is not None:
            best_title, best_cfg = _best_dan_across_tables(
                row["dan_title"], table_cfg,
                peer_dan_by_uid.get(uid_str), peer_cfg,
            )
        else:
            best_title, best_cfg = row["dan_title"], table_cfg
        dan_deco = _resolve_dan_decoration(best_title, best_cfg, config)
        entry: dict[str, Any] = {
            "rank": rank,
            "user_id": uid_str,
            "username": row["username"],
            "avatar_url": row["avatar_url"],
            "dan_decoration": dan_deco,
            "exp_level": row["exp_level"],
        }
        if type == "exp":
            entry["exp"] = round(float(row["exp"]), 2)
            entry["rating"] = None
            entry["bms_force"] = None
        else:
            entry["exp"] = None
            entry["rating"] = round(float(row["rating"]), 2)
            entry["bms_force"] = round(float(row["rating_norm"]), 3)
        entries.append(entry)

    return {
        "table_slug": table_slug,
        "display_name": table_cfg.display_name,
        "type": type,
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "entries": entries,
    }
