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
    python scripts/update_tables.py                  # force-sync all DB tables with source_url
    python scripts/update_tables.py --default-only    # force-sync config.toml default tables
    python scripts/update_tables.py --slug satellite  # force-sync one DB table by slug
    python scripts/update_tables.py --url https://example.com/table.html
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.parsers.table_fetcher import get_default_table_configs
from app.services.table_sync import (
    canonicalize_table_url,
    list_table_sync_targets,
    sync_table_by_id,
    sync_table_by_url,
)


async def update_one(slug: str, name: str, url: str, symbol_fallback: str | None = None, default_order: int | None = None) -> bool:
    """Fetch one table from remote, save to disk, and upsert into DB."""
    print(f"\n[{slug}] {name}")
    print(f"  URL: {url}")

    try:
        summary = await sync_table_by_url(
            url,
            is_default=True,
            configured_slug=slug,
            configured_name=name,
            symbol_fallback=symbol_fallback,
            default_order=default_order,
            save_disk_cache=True,
        )
    except Exception as exc:
        print(f"  ✗ Update FAILED: {exc}")
        return False

    print(
        f"  ✓ DB {summary['db_status']}: {summary['fumen_count']} fumens | "
        f"{summary['stale_removed']} stale entries removed | courses {summary['courses']}"
    )
    return True


async def update_by_url(url: str) -> bool:
    """Fetch one URL-only table and upsert it into DB."""
    canonical_url = canonicalize_table_url(url)
    print(f"\n[url] {canonical_url}")
    try:
        summary = await sync_table_by_url(canonical_url, is_default=False, save_disk_cache=True)
    except Exception as exc:
        print(f"  ✗ Update FAILED: {exc}")
        return False
    print(
        f"  ✓ DB {summary['db_status']}: {summary['fumen_count']} fumens | "
        f"{summary['stale_removed']} stale entries removed | courses {summary['courses']}"
    )
    print(f"  slug: {summary['slug']}")
    return True


async def update_by_id(table_id: UUID, slug: str | None, name: str) -> bool:
    """Force-fetch one existing DB difficulty table by id."""
    label = slug or str(table_id)
    print(f"\n[{label}] {name}")
    try:
        summary = await sync_table_by_id(table_id, respect_min_interval=False)
    except Exception as exc:
        print(f"  ✗ Update FAILED: {exc}")
        return False

    if summary.get("status") != "success":
        print(f"  - {summary.get('status')}: {summary}")
        return summary.get("status") == "skipped_too_recent"

    print(
        f"  ✓ DB {summary['db_status']}: {summary['fumen_count']} fumens | "
        f"{summary['stale_removed']} stale entries removed | courses {summary['courses']}"
    )
    return True


async def update_all_db_tables(slug_filter: str | None = None) -> None:
    """Force-sync all existing DB difficulty tables with source URLs."""
    targets = await list_table_sync_targets(
        slugs=[slug_filter] if slug_filter else None,
        default_only=False,
    )
    if not targets:
        scope = f" with slug '{slug_filter}'" if slug_filter else ""
        print(f"No DB difficulty tables with source_url found{scope}.")
        sys.exit(1 if slug_filter else 0)

    results: list[tuple[str, bool]] = []
    for target in targets:
        ok = await update_by_id(target.id, target.slug, target.name)
        results.append((target.slug or str(target.id), ok))

    print_summary(results)


def print_summary(results: list[tuple[str, bool]]) -> None:
    """Print common update summary and exit non-zero on any failure."""
    print("\n── Summary ──────────────────────────────────")
    for slug, ok in results:
        status = "✓" if ok else "✗"
        print(f"  {status} {slug}")
    ok_count = sum(1 for _, ok in results if ok)
    print(f"\n{ok_count}/{len(results)} tables updated")
    if ok_count < len(results):
        sys.exit(1)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch difficulty tables from remote and upsert into DB."
    )
    parser.add_argument("--slug", help="Update only this slug")
    parser.add_argument("--url", help="Update by source URL instead of config.toml")
    parser.add_argument(
        "--default-only",
        action="store_true",
        help="Update only default_tables from difficulty_tables/config.toml",
    )
    args = parser.parse_args()

    if args.url and (args.slug or args.default_only):
        print("Use --url by itself; do not combine it with --slug or --default-only.")
        sys.exit(1)

    if args.url:
        ok = await update_by_url(args.url)
        sys.exit(0 if ok else 1)

    if not args.default_only:
        await update_all_db_tables(slug_filter=args.slug)
        return

    indexed_configs = list(enumerate(get_default_table_configs()))
    if args.slug:
        indexed_configs = [(idx, c) for idx, c in indexed_configs if c["slug"] == args.slug]
        if not indexed_configs:
            print(f"Slug '{args.slug}' not found in config.toml")
            sys.exit(1)

    results: list[tuple[str, bool]] = []
    for idx, c in indexed_configs:
        ok = await update_one(c["slug"], c["name"], c["url"], symbol_fallback=c.get("symbol"), default_order=idx)
        results.append((c["slug"], ok))

    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
