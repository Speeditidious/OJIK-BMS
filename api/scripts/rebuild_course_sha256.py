"""One-time rebuild: recalculate sha256_list for all active courses.

Runs _build_sha256_list (which now also queries user_scores as fallback)
on every active Course, so that subsequent ranking calculations can use
partial-wildcard Beatoraja matching without user_scores scans.

Run AFTER backfill_fumens_sha256.py for best coverage.

Usage:
    docker compose exec api python3 -m scripts.rebuild_course_sha256
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.course import Course
from app.services.table_import import _build_sha256_list


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Course).where(Course.is_active.is_(True)))
        courses = result.scalars().all()
        updated = 0
        for course in courses:
            new_sha256_list = await _build_sha256_list(db, course.md5_list or [])
            if new_sha256_list != course.sha256_list:
                course.sha256_list = new_sha256_list
                updated += 1
        await db.commit()
        print(f"rebuild_course_sha256: {updated}/{len(courses)} courses updated")


if __name__ == "__main__":
    asyncio.run(main())
