"""Seed default difficulty tables into the database from local disk cache.

Usage:
    cd api
    python scripts/seed_tables.py

Reads config from difficulty_tables/config.toml and loads each table's
header.json + data.json into the PostgreSQL database.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from the api/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.table import DifficultyTable
from app.parsers.table_fetcher import get_default_table_configs, load_table_from_disk


async def seed() -> None:
    """Upsert all default tables from disk cache into the database."""
    configs = get_default_table_configs()
    if not configs:
        print("No default tables configured in config.toml.")
        return

    async with AsyncSessionLocal() as db:
        for cfg in configs:
            slug: str = cfg["slug"]
            name: str = cfg["name"]
            symbol: str | None = cfg.get("symbol")
            url: str = cfg["url"]

            table_data = load_table_from_disk(slug)

            async with db.begin():
                result = await db.execute(
                    select(DifficultyTable).where(DifficultyTable.slug == slug)
                )
                existing = result.scalar_one_or_none()

                if existing is None:
                    row = DifficultyTable(
                        name=name,
                        symbol=symbol,
                        slug=slug,
                        source_url=url,
                        is_default=True,
                        table_data=table_data,
                        last_synced_at=datetime.now(timezone.utc) if table_data else None,
                    )
                    db.add(row)
                    status = "inserted"
                else:
                    existing.name = name
                    existing.symbol = symbol
                    existing.source_url = url
                    existing.is_default = True
                    if table_data:
                        existing.table_data = table_data
                        existing.last_synced_at = datetime.now(timezone.utc)
                    status = "updated"

            song_count = len(table_data["songs"]) if table_data else 0
            data_status = f"{song_count} songs" if table_data else "NO DATA"
            print(f"[{status:8s}] {slug:20s}  {name:30s}  {data_status}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(seed())
