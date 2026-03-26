"""Custom table and course management endpoints."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.difficulty_table import CustomCourse, CustomDifficultyTable
from app.models.user import User
from app.schemas import MessageResponse

router = APIRouter(prefix="/custom", tags=["custom"])


class CustomTableCreate(BaseModel):
    name: str
    is_public: bool = False
    levels: list[dict[str, Any]] | None = None


class CustomTableRead(BaseModel):
    id: str
    owner_id: str
    name: str
    is_public: bool
    levels: list[Any] | None
    model_config = ConfigDict(from_attributes=True)


class CustomCourseCreate(BaseModel):
    name: str
    song_list: list[str] | None = None  # list of sha256 hashes
    course_file_config: dict[str, Any] | None = None


class CustomCourseRead(BaseModel):
    id: str
    owner_id: str
    name: str
    song_list: list[Any] | None
    course_file_config: dict[str, Any] | None
    model_config = ConfigDict(from_attributes=True)


# --- Custom Tables ---

@router.get("/tables", response_model=list[CustomTableRead])
async def list_custom_tables(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CustomTableRead]:
    """List current user's custom tables."""
    result = await db.execute(
        select(CustomDifficultyTable).where(CustomDifficultyTable.owner_id == current_user.id)
    )
    tables = result.scalars().all()
    return [
        CustomTableRead(
            id=str(t.id),
            owner_id=str(t.owner_id),
            name=t.name,
            is_public=t.is_public,
            levels=t.levels,
        )
        for t in tables
    ]


@router.post("/tables", response_model=CustomTableRead)
async def create_custom_table(
    payload: CustomTableCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomTableRead:
    """Create a new custom table."""
    table = CustomDifficultyTable(
        owner_id=current_user.id,
        name=payload.name,
        is_public=payload.is_public,
        levels=payload.levels,
    )
    db.add(table)
    await db.commit()
    await db.refresh(table)

    return CustomTableRead(
        id=str(table.id),
        owner_id=str(table.owner_id),
        name=table.name,
        is_public=table.is_public,
        levels=table.levels,
    )


@router.delete("/tables/{table_id}", response_model=MessageResponse)
async def delete_custom_table(
    table_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a custom table."""
    import uuid as _uuid
    result = await db.execute(
        select(CustomDifficultyTable).where(
            CustomDifficultyTable.id == _uuid.UUID(table_id),
            CustomDifficultyTable.owner_id == current_user.id,
        )
    )
    table = result.scalar_one_or_none()

    if table is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    await db.delete(table)
    await db.commit()
    return MessageResponse(message="Table deleted")


# --- Custom Courses ---

@router.get("/courses", response_model=list[CustomCourseRead])
async def list_custom_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CustomCourseRead]:
    """List current user's custom courses."""
    result = await db.execute(
        select(CustomCourse).where(CustomCourse.owner_id == current_user.id)
    )
    courses = result.scalars().all()
    return [
        CustomCourseRead(
            id=str(c.id),
            owner_id=str(c.owner_id),
            name=c.name,
            song_list=c.song_list,
            course_file_config=c.course_file_config,
        )
        for c in courses
    ]


@router.post("/courses", response_model=CustomCourseRead)
async def create_custom_course(
    payload: CustomCourseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomCourseRead:
    """Create a new custom course."""
    course = CustomCourse(
        owner_id=current_user.id,
        name=payload.name,
        song_list=payload.song_list,
        course_file_config=payload.course_file_config,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)

    return CustomCourseRead(
        id=str(course.id),
        owner_id=str(course.owner_id),
        name=course.name,
        song_list=course.song_list,
        course_file_config=course.course_file_config,
    )
