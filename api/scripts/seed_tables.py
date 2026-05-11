"""Seed difficulty tables into the database from local disk cache.

Usage:
    cd api
    python scripts/seed_tables.py                 # seed cached DB tables
    python scripts/seed_tables.py --default-only  # seed default config tables

Loads cached header.json + data.json into PostgreSQL, upserting fumens
and courses accordingly. This command does not fetch remote URLs.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.difficulty_table import DifficultyTable
from app.parsers.table_fetcher import get_default_table_configs, load_table_from_disk
from app.services.table_import import (
    remove_stale_entries,
    upsert_courses,
    upsert_fumens,
)


async def seed(slug_filter: str | None = None, *, default_only: bool = False) -> None:
    """Upsert cached difficulty tables into the database."""
    if default_only or slug_filter:
        await seed_default_tables(slug_filter=slug_filter)
        return

    rows = await _load_existing_table_rows()
    if not rows:
        print("No DB difficulty tables found; falling back to default_tables from config.toml.")
        await seed_default_tables(slug_filter=None)
        return

    async with AsyncSessionLocal() as db:
        for row in rows:
            slug = row.slug
            if not slug:
                print(f"[skipped ] {str(row.id):20s}  {row.name:30s}  NO SLUG")
                continue

            table_data = load_table_from_disk(slug)
            if not table_data:
                print(f"[skipped ] {slug:20s}  {row.name:30s}  NO CACHE")
                continue

            async with db.begin():
                result = await db.execute(
                    select(DifficultyTable).where(DifficultyTable.id == row.id)
                )
                existing = result.scalar_one()
                effective_symbol = existing.symbol or table_data.get("symbol")
                existing.symbol = effective_symbol
                existing.level_order = table_data.get("level_order")
                existing.updated_at = datetime.now(UTC)

                seen_keys = await upsert_fumens(db, existing.id, table_data.get("songs", []))
                removed = await remove_stale_entries(db, existing.id, seen_keys)
                course_summary = await upsert_courses(db, existing.id, table_data.get("courses", []))

            print(
                f"[updated ] {slug:20s}  {row.name:30s}  "
                f"{len(seen_keys)} fumens stale_removed={removed} courses={course_summary}"
            )

    print("\nDone.")


async def _load_existing_table_rows() -> list[DifficultyTable]:
    """Load existing DB tables that can be seeded from slugged disk cache."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DifficultyTable)
            .where(DifficultyTable.slug.isnot(None))
            .order_by(DifficultyTable.is_default.desc(), DifficultyTable.default_order, DifficultyTable.name)
        )
        return list(result.scalars().all())


async def seed_default_tables(slug_filter: str | None = None) -> None:
    """Upsert default tables from disk cache into the database."""
    indexed_configs = list(enumerate(get_default_table_configs()))
    if slug_filter:
        indexed_configs = [(idx, c) for idx, c in indexed_configs if c["slug"] == slug_filter]
        if not indexed_configs:
            print(f"Slug '{slug_filter}' not found in config.toml")
            sys.exit(1)
    if not indexed_configs:
        print("No default tables configured in config.toml.")
        return

    async with AsyncSessionLocal() as db:
        for idx, cfg in indexed_configs:
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
                    existing.updated_at = datetime.now(UTC)
                    table_id = existing.id
                    status = "updated"

                fumen_count = 0
                course_summary = None
                if table_data:
                    seen_keys = await upsert_fumens(db, table_id, table_data.get("songs", []))
                    await remove_stale_entries(db, table_id, seen_keys)
                    course_summary = await upsert_courses(db, table_id, table_data.get("courses", []))
                    fumen_count = len(seen_keys)

            data_status = f"{fumen_count} fumens" if table_data else "NO DATA"
            course_status = f" courses={course_summary}" if course_summary else ""
            print(f"[{status:8s}] {slug:20s}  {name:30s}  {data_status}{course_status}")

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed difficulty tables from disk cache into DB."
    )
    parser.add_argument("--slug", help="Seed only this slug")
    parser.add_argument(
        "--default-only",
        action="store_true",
        help="Seed only default_tables from difficulty_tables/config.toml",
    )
    args = parser.parse_args()
    asyncio.run(seed(slug_filter=args.slug, default_only=args.default_only))
