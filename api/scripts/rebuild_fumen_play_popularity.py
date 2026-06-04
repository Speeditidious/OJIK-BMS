"""Rebuild fumen_play_popularity from user_scores (O(S); ops use only)."""

import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            await db.execute(text("TRUNCATE fumen_play_popularity"))
            await db.execute(text("TRUNCATE fumen_popularity_dirty"))
            await db.execute(
                text(
                    """
                    INSERT INTO fumen_play_popularity (fumen_id, played_user_count, total_play_count, updated_at)
                    WITH resolved_scores AS (
                        SELECT COALESCE(us.fumen_id, f_sha.fumen_id, f_md5.fumen_id) AS resolved_fumen_id,
                               us.user_id,
                               us.play_count
                        FROM user_scores us
                        LEFT JOIN fumens f_sha
                          ON us.fumen_id IS NULL
                         AND us.fumen_sha256 IS NOT NULL
                         AND us.fumen_sha256 = f_sha.sha256
                        LEFT JOIN fumens f_md5
                          ON us.fumen_id IS NULL
                         AND f_sha.fumen_id IS NULL
                         AND us.fumen_md5 IS NOT NULL
                         AND us.fumen_md5 = f_md5.md5
                        WHERE us.fumen_hash_others IS NULL
                    )
                    SELECT resolved_fumen_id AS fumen_id,
                           COUNT(*)::integer,
                           COALESCE(SUM(user_plays), 0)::integer,
                           now()
                    FROM (
                        SELECT resolved_fumen_id, user_id, MAX(COALESCE(play_count, 0)) AS user_plays
                        FROM resolved_scores
                        WHERE resolved_fumen_id IS NOT NULL
                        GROUP BY resolved_fumen_id, user_id
                    ) per_user
                    GROUP BY resolved_fumen_id
                    """
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
