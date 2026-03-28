"""Update difficulty tables: fetch from remote, save to disk, and upsert into DB.

Combines fetch and seed into one command. On each run:
  1. Fetches header.json + data.json from remote
  2. Saves to local disk cache
  3. Upserts DifficultyTable row (name, level_order, etc.)
  4. Upserts Fumen rows (table_entries JSONB merge, artist / url fields)
  5. Removes stale table_entries entries for fumens no longer in the table
  6. Upserts Course rows from header course/grade fields

Usage:
    cd api
    python scripts/update_tables.py                  # all tables
    python scripts/update_tables.py --slug satellite  # single table
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.difficulty_table import DifficultyTable
from app.parsers.table_fetcher import (
    TABLES_DIR,
    fetch_table,
    get_default_table_configs,
    load_table_from_disk,
    save_table_to_disk,
)
from app.services.table_import import remove_stale_entries, upsert_courses, upsert_fumens


async def update_one(slug: str, name: str, url: str, symbol_fallback: str | None = None, default_order: int | None = None) -> bool:
    """Fetch one table from remote, save to disk, and upsert into DB."""
    print(f"\n[{slug}] {name}")
    print(f"  URL: {url}")

    # Step 1: fetch from remote
    try:
        data = await fetch_table(url)
        songs = data.get("songs", [])
        level_order = data.get("level_order", [])
        effective_symbol = data.get("symbol") or symbol_fallback
        print(f"  → {len(songs)} songs | levels: {level_order[:6]}{'...' if len(level_order) > 6 else ''}")
        save_table_to_disk(slug, data)
        print(f"  ✓ difficulty_tables/{slug}/header.json + data.json saved")
    except Exception as exc:
        print(f"  ✗ Fetch FAILED: {exc}")
        return False

    # Step 2: load from disk and upsert into DB
    table_data = load_table_from_disk(slug)
    if not table_data:
        print("  ✗ Failed to load from disk after save")
        return False

    try:
        async with AsyncSessionLocal() as db:
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
                        default_order=default_order,
                        level_order=table_data.get("level_order"),
                    )
                    db.add(row)
                    await db.flush()
                    table_id = row.id
                    db_status = "inserted"
                else:
                    existing.name = name
                    existing.symbol = effective_symbol
                    existing.source_url = url
                    existing.is_default = True
                    if default_order is not None:
                        existing.default_order = default_order
                    existing.level_order = table_data.get("level_order")
                    table_id = existing.id
                    db_status = "updated"

                seen_keys = await upsert_fumens(db, table_id, table_data.get("songs", []))
                removed = await remove_stale_entries(db, table_id, seen_keys)
                await upsert_courses(db, table_id, table_data.get("courses", []))

        print(f"  ✓ DB {db_status}: {len(seen_keys)} fumens | {removed} stale entries removed")
        return True
    except Exception as exc:
        print(f"  ✗ DB upsert FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch difficulty tables from remote and upsert into DB."
    )
    parser.add_argument("--slug", help="Update only this slug (from config.toml)")
    args = parser.parse_args()

    configs = get_default_table_configs()
    if args.slug:
        configs = [c for c in configs if c["slug"] == args.slug]
        if not configs:
            print(f"Slug '{args.slug}' not found in config.toml")
            sys.exit(1)

    results: list[tuple[str, bool]] = []
    for idx, c in enumerate(configs):
        ok = await update_one(c["slug"], c["name"], c["url"], symbol_fallback=c.get("symbol"), default_order=idx)
        results.append((c["slug"], ok))

    print("\n── Summary ──────────────────────────────────")
    for slug, ok in results:
        status = "✓" if ok else "✗"
        print(f"  {status} {slug}")
    ok_count = sum(1 for _, ok in results if ok)
    print(f"\n{ok_count}/{len(results)} tables updated")
    if ok_count < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
