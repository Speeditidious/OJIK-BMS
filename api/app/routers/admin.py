"""Admin API router — dan course management and badge administration."""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.course import AdminDanCourse, UserCourseScore, UserDanBadge
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


class DanCourseCreate(BaseModel):
    course_hash: str
    name: str
    short_name: str | None = None
    category: str | None = None
    sort_order: int = 0


class DanCourseUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    category: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


@router.get("/dan-courses")
async def list_dan_courses(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all admin-designated dan courses."""
    result = await db.execute(
        select(AdminDanCourse).order_by(AdminDanCourse.sort_order, AdminDanCourse.id)
    )
    courses = result.scalars().all()
    return [
        {
            "id": c.id,
            "course_hash": c.course_hash,
            "name": c.name,
            "short_name": c.short_name,
            "category": c.category,
            "sort_order": c.sort_order,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat(),
        }
        for c in courses
    ]


@router.post("/dan-courses", status_code=status.HTTP_201_CREATED)
async def create_dan_course(
    body: DanCourseCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Designate a course as a dan course."""
    course = AdminDanCourse(
        course_hash=body.course_hash,
        name=body.name,
        short_name=body.short_name,
        category=body.category,
        sort_order=body.sort_order,
        created_by=current_user.id,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return {
        "id": course.id,
        "course_hash": course.course_hash,
        "name": course.name,
        "short_name": course.short_name,
        "category": course.category,
        "sort_order": course.sort_order,
        "is_active": course.is_active,
        "created_at": course.created_at.isoformat(),
    }


@router.patch("/dan-courses/{dan_id}")
async def update_dan_course(
    dan_id: int,
    body: DanCourseUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update a dan course's metadata."""
    result = await db.execute(select(AdminDanCourse).where(AdminDanCourse.id == dan_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dan course not found")

    if body.name is not None:
        course.name = body.name
    if body.short_name is not None:
        course.short_name = body.short_name
    if body.category is not None:
        course.category = body.category
    if body.sort_order is not None:
        course.sort_order = body.sort_order
    if body.is_active is not None:
        course.is_active = body.is_active

    await db.commit()
    await db.refresh(course)
    return {
        "id": course.id,
        "course_hash": course.course_hash,
        "name": course.name,
        "short_name": course.short_name,
        "category": course.category,
        "sort_order": course.sort_order,
        "is_active": course.is_active,
        "created_at": course.created_at.isoformat(),
    }


@router.delete("/dan-courses/{dan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_dan_course(
    dan_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete (deactivate) a dan course."""
    result = await db.execute(select(AdminDanCourse).where(AdminDanCourse.id == dan_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dan course not found")
    course.is_active = False
    await db.commit()


@router.post("/dan-courses/{dan_id}/award-badges")
async def award_badges_for_course(
    dan_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Backfill dan badges for all users who have cleared this course (improvement-only upsert)."""
    result = await db.execute(select(AdminDanCourse).where(AdminDanCourse.id == dan_id))
    dan_course = result.scalar_one_or_none()
    if dan_course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dan course not found")

    scores_result = await db.execute(
        select(UserCourseScore).where(
            UserCourseScore.course_hash == dan_course.course_hash,
            UserCourseScore.clear_type >= 3,
        )
    )
    scores = scores_result.scalars().all()

    awarded = 0
    for score in scores:
        achieved_at = score.played_at or score.synced_at or datetime.now(UTC)
        stmt = (
            insert(UserDanBadge)
            .values(
                user_id=score.user_id,
                dan_course_id=dan_id,
                clear_type=score.clear_type,
                client_type=score.client_type,
                achieved_at=achieved_at,
            )
            .on_conflict_do_update(
                constraint="uq_user_dan_badges",
                set_={
                    "clear_type": UserDanBadge.clear_type,
                    "achieved_at": achieved_at,
                },
                where=(UserDanBadge.clear_type < score.clear_type),
            )
        )
        await db.execute(stmt)
        awarded += 1

    await db.commit()
    return {"awarded": awarded}
