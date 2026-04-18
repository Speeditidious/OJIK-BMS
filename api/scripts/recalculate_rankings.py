"""Synchronous ranking recalculation script (Celery bypass).

Use this when the Celery worker is unavailable and rankings need to be
recalculated directly against the database.

Usage:
    docker compose exec api python -m scripts.recalculate_rankings [--slug satellite]
"""
import argparse
import asyncio

from app.core.database import AsyncSessionLocal
from app.services.ranking_calculator import recalculate_table_bulk
from app.services.ranking_config import init_ranking_config


async def main(slug: str | None) -> None:
    async with AsyncSessionLocal() as db:
        config = await init_ranking_config(db)
        targets = config.tables if slug is None else [t for t in config.tables if t.slug == slug]
        if not targets:
            print(f"No tables found for slug={slug!r}. Available: {[t.slug for t in config.tables]}")
            return
        for tbl in targets:
            n = await recalculate_table_bulk(tbl, config, db)
            await db.commit()
            print(f"[{tbl.slug}] {n} users recalculated (c_table={tbl.c_table:.4f})")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Recalculate rankings synchronously (no Celery)")
    p.add_argument("--slug", default=None, help="Difficulty table slug to recalculate (default: all)")
    args = p.parse_args()
    asyncio.run(main(args.slug))
