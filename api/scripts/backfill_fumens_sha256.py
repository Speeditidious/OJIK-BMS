"""One-time backfill: populate fumens.sha256 from existing user_scores.

Picks up (fumen_md5, fumen_sha256) pairs that Beatoraja users have synced
and writes them back to the fumens table where sha256 is currently NULL.

Usage:
    docker compose exec api python3 -m scripts.backfill_fumens_sha256
"""
import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal

SQL = """
WITH pairs AS (
    SELECT DISTINCT ON (fumen_md5) fumen_md5, fumen_sha256
    FROM user_scores
    WHERE fumen_sha256 IS NOT NULL AND fumen_md5 IS NOT NULL
)
UPDATE fumens f
   SET sha256 = p.fumen_sha256
  FROM pairs p
 WHERE f.md5 = p.fumen_md5
   AND f.sha256 IS NULL
   AND NOT EXISTS (
       SELECT 1 FROM fumens f2 WHERE f2.sha256 = p.fumen_sha256
   );
"""


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(SQL))
        await db.commit()
        print(f"backfill_fumens_sha256: {result.rowcount} rows updated")


if __name__ == "__main__":
    asyncio.run(main())
