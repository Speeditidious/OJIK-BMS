"""Update difficulty tables: fetch from remote, save to disk, and upsert into DB.

Combines fetch (test_table_fetch) and seed (seed_tables) into one command.

Usage:
    cd api
    python scripts/update_tables.py                  # all tables
    python scripts/update_tables.py --slug satellite  # single table
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.table import DifficultyTable
from app.parsers.table_fetcher import (
    TABLES_DIR,
    fetch_table,
    get_default_table_configs,
    load_table_from_disk,
    save_table_to_disk,
)


async def update_one(slug: str, name: str, url: str) -> bool:
    """Fetch one table from remote, save to disk, and upsert into DB."""
    print(f"\n[{slug}] {name}")
    print(f"  URL: {url}")

    # Step 1: fetch from remote
    try:
        data = await fetch_table(url)
        if data is None:
            print("  → 304 Not Modified — using cached disk data")
        else:
            songs = data.get("songs", [])
            level_order = data.get("level_order", [])
            print(f"  → {len(songs)} songs | levels: {level_order[:6]}{'...' if len(level_order) > 6 else ''}")
            save_table_to_disk(slug, data)
            header_path = TABLES_DIR / slug / "header.json"
            data_path = TABLES_DIR / slug / "data.json"
            assert header_path.exists(), "header.json not found"
            assert data_path.exists(), "data.json not found"
            print(f"  ✓ difficulty_tables/{slug}/header.json + data.json saved")
    except Exception as exc:
        print(f"  ✗ Fetch FAILED: {exc}")
        return False

    # Step 2: load from disk and upsert into DB
    table_data = load_table_from_disk(slug)

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
                        slug=slug,
                        source_url=url,
                        is_default=True,
                        table_data=table_data,
                        last_synced_at=datetime.now(timezone.utc) if table_data else None,
                    )
                    db.add(row)
                    db_status = "inserted"
                else:
                    existing.name = name
                    existing.source_url = url
                    existing.is_default = True
                    if table_data:
                        existing.table_data = table_data
                        existing.last_synced_at = datetime.now(timezone.utc)
                    db_status = "updated"

        song_count = len(table_data["songs"]) if table_data else 0
        data_status = f"{song_count} songs" if table_data else "NO DATA"
        print(f"  ✓ DB {db_status}: {data_status}")
        return True
    except Exception as exc:
        print(f"  ✗ DB upsert FAILED: {exc}")
        return False


async def main() -> None:
    """Fetch all (or one) difficulty tables and upsert into DB."""
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
    for c in configs:
        ok = await update_one(c["slug"], c["name"], c["url"])
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
