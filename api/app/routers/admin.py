"""Admin API router — course management and badge administration."""
import uuid as _uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.course import Course
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


class CourseCreate(BaseModel):
    name: str
    source_table_id: _uuid.UUID | None = None
    md5_list: list[str]
    dan_title: str = ""


class CourseUpdate(BaseModel):
    name: str | None = None
    md5_list: list[str] | None = None
    is_active: bool | None = None
    dan_title: str | None = None


@router.get("/dan-courses")
async def list_dan_courses(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all courses (active first)."""
    result = await db.execute(
        select(Course).order_by(Course.is_active.desc(), Course.synced_at.desc())
    )
    courses = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "source_table_id": c.source_table_id,
            "md5_list": c.md5_list,
            "is_active": c.is_active,
            "dan_title": c.dan_title,
            "synced_at": c.synced_at.isoformat(),
        }
        for c in courses
    ]


@router.post("/dan-courses", status_code=status.HTTP_201_CREATED)
async def create_dan_course(
    body: CourseCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a course (admin-direct, source_table_id=NULL)."""
    course = Course(
        name=body.name,
        source_table_id=body.source_table_id,
        md5_list=body.md5_list,
        dan_title=body.dan_title,
        synced_at=datetime.now(UTC),
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return {
        "id": str(course.id),
        "name": course.name,
        "source_table_id": course.source_table_id,
        "md5_list": course.md5_list,
        "is_active": course.is_active,
        "dan_title": course.dan_title,
        "synced_at": course.synced_at.isoformat(),
    }


@router.patch("/dan-courses/{course_id}")
async def update_dan_course(
    course_id: str,
    body: CourseUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update a course's metadata."""
    try:
        cid = _uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid course ID")

    result = await db.execute(select(Course).where(Course.id == cid))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if body.name is not None:
        course.name = body.name
    if body.md5_list is not None:
        course.md5_list = body.md5_list
    if body.is_active is not None:
        course.is_active = body.is_active
    if body.dan_title is not None:
        course.dan_title = body.dan_title

    await db.commit()
    await db.refresh(course)
    return {
        "id": str(course.id),
        "name": course.name,
        "source_table_id": course.source_table_id,
        "md5_list": course.md5_list,
        "is_active": course.is_active,
        "dan_title": course.dan_title,
        "synced_at": course.synced_at.isoformat(),
    }


@router.delete("/dan-courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_dan_course(
    course_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete (deactivate) a course."""
    try:
        cid = _uuid.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid course ID")

    result = await db.execute(select(Course).where(Course.id == cid))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    course.is_active = False
    await db.commit()


