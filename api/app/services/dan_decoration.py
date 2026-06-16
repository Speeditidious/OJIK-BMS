"""Resolve each user's best dan (단위인정) decoration across all ranking tables.

Shared by the ranking list and the weekly leaderboard so decorations stay
consistent. Uses the same global priority rule as
`rankings._best_dan_across_tables`: cross_dan_tier * 10000 + dan.priority.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ranking_config import (
    TableRankingConfig,
    find_dan_config,
    get_effective_dans,
    get_ranking_config,
)


async def resolve_dan_decorations(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[str, dict | None]:
    """Return {user_id_str: decoration_dict | None} for the given users.

    decoration_dict = {dan_title, display_text, color, glow_intensity}.
    Users with no qualifying dan are simply absent from the mapping.
    """
    if not user_ids:
        return {}
    try:
        config = get_ranking_config()
    except RuntimeError:
        return {}

    cfg_by_table = {str(t.table_id): t for t in config.tables}
    return await _resolve_dan_decorations_for_configs(db, user_ids, cfg_by_table)


async def resolve_dan_decorations_for_table(
    db: AsyncSession, user_ids: list[uuid.UUID], table_slug: str
) -> dict[str, dict | None]:
    """Return dan decorations from one ranking table only."""
    if not user_ids:
        return {}
    try:
        config = get_ranking_config()
    except RuntimeError:
        return {}

    table_cfg = config.get_table_by_slug(table_slug)
    if table_cfg is None:
        return {}

    return await _resolve_dan_decorations_for_configs(
        db, user_ids, {str(table_cfg.table_id): table_cfg}
    )


async def resolve_dan_decorations_for_tables(
    db: AsyncSession, user_ids: list[uuid.UUID], table_slugs: list[str]
) -> dict[str, dict | None]:
    """Return best dan decorations from the requested ranking table slugs."""
    if not user_ids or not table_slugs:
        return {}
    try:
        config = get_ranking_config()
    except RuntimeError:
        return {}

    cfg_by_table = {}
    for slug in table_slugs:
        table_cfg = config.get_table_by_slug(slug)
        if table_cfg is not None:
            cfg_by_table[str(table_cfg.table_id)] = table_cfg
    if not cfg_by_table:
        return {}

    return await _resolve_dan_decorations_for_configs(db, user_ids, cfg_by_table)


async def _resolve_dan_decorations_for_configs(
    db: AsyncSession, user_ids: list[uuid.UUID], cfg_by_table: dict[str, TableRankingConfig]
) -> dict[str, dict | None]:
    """Resolve decorations for the supplied table config map."""
    try:
        config = get_ranking_config()
    except RuntimeError:
        return {}

    rows = await db.execute(
        text(
            """
            SELECT user_id::text AS uid, table_id::text AS tid, dan_title
            FROM user_rankings
            WHERE user_id = ANY(:uids) AND dan_title IS NOT NULL
              AND table_id = ANY(:table_ids)
            """
        ),
        {"uids": [str(u) for u in user_ids], "table_ids": list(cfg_by_table.keys())},
    )

    # Pick the highest-priority (table, dan_title) per user.
    best: dict[str, tuple[int, str, TableRankingConfig]] = {}
    for r in rows.mappings().all():
        tcfg = cfg_by_table.get(r["tid"])
        if tcfg is None:
            continue
        priority = -1
        for d in get_effective_dans(tcfg, config):
            if d.dan_title == r["dan_title"]:
                priority = tcfg.cross_dan_tier * 10000 + d.priority
                break
        if priority < 0:
            continue
        current = best.get(r["uid"])
        if current is None or priority > current[0]:
            best[r["uid"]] = (priority, r["dan_title"], tcfg)

    out: dict[str, dict | None] = {}
    for uid, (_, title, tcfg) in best.items():
        dan = find_dan_config(title, tcfg, config)
        out[uid] = (
            {
                "dan_title": dan.dan_title,
                "display_text": dan.display_text,
                "color": dan.color,
                "glow_intensity": dan.glow_intensity,
            }
            if dan is not None
            else None
        )
    return out
