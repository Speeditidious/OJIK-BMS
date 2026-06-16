"""Resolve fumen pools and generate weekly instances."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.difficulty_table import DifficultyTable
from app.models.fumen import FumenTableEntry
from app.models.weekly import Weekly, WeeklyFumen
from app.services.weekly_config import Bracket, Selector, WeeklyConfigError


@dataclass(frozen=True)
class PoolEntry:
    fumen_id: uuid.UUID
    table_id: uuid.UUID | None
    level: str
    table_symbol: str | None


def resolve_levels(level_order: list[str], selector: Selector) -> list[str]:
    """Expand a selector into a concrete list of level strings."""
    if selector.levels:
        return list(selector.levels)
    if not selector.level_range:
        raise WeeklyConfigError(f"Selector for '{selector.table}' has neither levels nor level_range")
    lo = level_order or []
    lo_from, lo_to = selector.level_range
    if lo_from not in lo or lo_to not in lo:
        raise WeeklyConfigError(
            f"level_range bound not in level_order for table '{selector.table}': "
            f"{selector.level_range} not within {lo}"
        )
    i, j = lo.index(lo_from), lo.index(lo_to)
    if i > j:
        i, j = j, i
    return lo[i : j + 1]


def dedup_pool(pool: list[PoolEntry]) -> list[PoolEntry]:
    """Drop duplicate fumen_ids, keeping the first occurrence (selector order)."""
    seen: set[uuid.UUID] = set()
    out: list[PoolEntry] = []
    for entry in pool:
        if entry.fumen_id in seen:
            continue
        seen.add(entry.fumen_id)
        out.append(entry)
    return out


def pick(pool: list[PoolEntry], count: int, rng: random.Random) -> list[PoolEntry]:
    """Pick up to *count* unique entries at random (caps at pool size)."""
    if count >= len(pool):
        return list(pool)
    return rng.sample(pool, count)


async def resolve_pool(db: AsyncSession, bracket: Bracket) -> tuple[list[PoolEntry], dict]:
    """Resolve the deduped fumen pool for a bracket and the resolved-levels snapshot.

    Returns (deduped_pool, {selectors: [...]}).
    """
    pool: list[PoolEntry] = []
    resolved_snapshot: list[dict] = []
    for selector in bracket.selectors:
        tbl_result = await db.execute(
            select(DifficultyTable.id, DifficultyTable.symbol, DifficultyTable.level_order)
            .where(DifficultyTable.slug == selector.table)
            .limit(1)
        )
        tbl = tbl_result.first()
        if tbl is None:
            raise WeeklyConfigError(f"Difficulty table slug not found: {selector.table}")
        levels = resolve_levels(list(tbl.level_order or []), selector)
        resolved_snapshot.append({"table": selector.table, "levels": levels})

        entry_result = await db.execute(
            select(FumenTableEntry.fumen_id, FumenTableEntry.level)
            .where(
                FumenTableEntry.table_id == tbl.id,
                FumenTableEntry.level.in_(levels),
            )
        )
        for row in entry_result.all():
            pool.append(
                PoolEntry(
                    fumen_id=row.fumen_id,
                    table_id=tbl.id,
                    level=row.level,
                    table_symbol=tbl.symbol,
                )
            )

    return dedup_pool(pool), {"selectors": resolved_snapshot}


def build_snapshot(bracket: Bracket, resolved: dict) -> dict:
    """Build the frozen config_snapshot for a weekly."""
    return {
        "bracket_group": bracket.group,
        "color": bracket.color,
        "pick_count": bracket.pick_count,
        "selectors": resolved["selectors"],
    }


async def generate_weekly(
    db: AsyncSession,
    category_key: str,
    category_name: str,
    bracket: Bracket,
    period_start: datetime,
    period_end: datetime,
    *,
    forced: bool = False,
    rng: random.Random | None = None,
) -> Weekly:
    """Idempotently create a weekly for (category, bracket, period_start).

    If one exists and forced is False, return it unchanged. If forced, delete and recreate.
    """
    existing_result = await db.execute(
        select(Weekly).where(
            Weekly.category_key == category_key,
            Weekly.bracket_key == bracket.key,
            Weekly.period_start == period_start,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if not forced:
            return existing
        await db.delete(existing)
        await db.flush()

    rng = rng or random.Random()
    pool, resolved = await resolve_pool(db, bracket)
    chosen = pick(pool, bracket.pick_count, rng)

    snapshot = build_snapshot(bracket, resolved)
    snapshot["category_name"] = category_name

    weekly = Weekly(
        category_key=category_key,
        bracket_key=bracket.key,
        period_start=period_start,
        period_end=period_end,
        config_snapshot=snapshot,
        is_forced=forced,
        created_at=datetime.now(UTC),
    )
    db.add(weekly)
    await db.flush()

    for slot, entry in enumerate(chosen):
        db.add(
            WeeklyFumen(
                weekly_id=weekly.id,
                slot=slot,
                fumen_id=entry.fumen_id,
                table_id=entry.table_id,
                level=entry.level,
                table_symbol=entry.table_symbol,
            )
        )
    await db.flush()
    return weekly
