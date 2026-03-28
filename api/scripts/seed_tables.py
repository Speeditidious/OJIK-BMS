"""Seed default difficulty tables into the database from local disk cache.

Usage:
    cd api
    python scripts/seed_tables.py

Reads config from difficulty_tables/config.toml and loads each table's
header.json + data.json into the PostgreSQL database, upserting fumens
and courses accordingly.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.difficulty_table import DifficultyTable
from app.parsers.table_fetcher import get_default_table_configs, load_table_from_disk
from app.services.table_import import remove_stale_entries, upsert_courses, upsert_fumens


async def seed() -> None:
    """Upsert all default tables from disk cache into the database."""
    configs = get_default_table_configs()
    if not configs:
        print("No default tables configured in config.toml.")
        return

    async with AsyncSessionLocal() as db:
        for idx, cfg in enumerate(configs):
            slug: str = cfg["slug"]
            name: str = cfg["name"]
            symbol: str | None = cfg.get("symbol")
            url: str = cfg["url"]

            table_data = load_table_from_disk(slug)
            effective_symbol = symbol or (table_data.get("symbol") if table_data else None)

            async with db.begin():
                result = await db.execute(
                    select(DifficultyTable).where(DifficultyTable.slug == slug)
                )
                existing = result.scalar_one_or_none()

                if existing is None:
                    row = DifficultyTable(
                        name=name,
                        symbol=effective_symbol,
                        slug=slug,
                        source_url=url,
                        is_default=True,
                        default_order=idx,
                        level_order=table_data.get("level_order") if table_data else None,
                    )
                    db.add(row)
                    await db.flush()
                    table_id = row.id
                    status = "inserted"
                else:
                    existing.name = name
                    existing.symbol = effective_symbol
                    existing.source_url = url
                    existing.is_default = True
                    existing.default_order = idx
                    if table_data:
                        existing.level_order = table_data.get("level_order")
                    table_id = existing.id
                    status = "updated"

                fumen_count = 0
                if table_data:
                    seen_keys = await upsert_fumens(db, table_id, table_data.get("songs", []))
                    await remove_stale_entries(db, table_id, seen_keys)
                    await upsert_courses(db, table_id, table_data.get("courses", []))
                    fumen_count = len(seen_keys)

            data_status = f"{fumen_count} fumens" if table_data else "NO DATA"
            print(f"[{status:8s}] {slug:20s}  {name:30s}  {data_status}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(seed())
