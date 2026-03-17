"""Schedule (calendar todo) endpoints."""
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.table import Schedule
from app.models.user import User

router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    scheduled_time: Optional[str] = None  # HH:MM


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    scheduled_time: Optional[str] = None
    is_completed: Optional[bool] = None


def _schedule_to_dict(s: Schedule) -> Dict[str, Any]:
    return {
        "id": str(s.id),
        "title": s.title,
        "description": s.description,
        "scheduled_date": s.scheduled_date.isoformat() if s.scheduled_date else None,
        "scheduled_time": s.scheduled_time,
        "is_completed": s.is_completed,
    }


@router.get("/")
async def list_schedules(
    target_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List schedules for the current user, optionally filtered by date."""
    query = select(Schedule).where(Schedule.user_id == current_user.id)

    if target_date is not None:
        from sqlalchemy import cast, Date
        query = query.where(cast(Schedule.scheduled_date, Date) == target_date)

    query = query.order_by(Schedule.scheduled_date.asc().nullslast(), Schedule.id)
    result = await db.execute(query)
    schedules = result.scalars().all()

    return {"schedules": [_schedule_to_dict(s) for s in schedules]}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new schedule entry."""
    schedule = Schedule(
        user_id=current_user.id,
        title=body.title,
        description=body.description,
        scheduled_date=body.scheduled_date,
        scheduled_time=body.scheduled_time,
        is_completed=False,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return _schedule_to_dict(schedule)


@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update a schedule entry."""
    result = await db.execute(
        select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.user_id == current_user.id,
        )
    )
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    if body.title is not None:
        schedule.title = body.title
    if body.description is not None:
        schedule.description = body.description
    if body.scheduled_date is not None:
        schedule.scheduled_date = body.scheduled_date
    if body.scheduled_time is not None:
        schedule.scheduled_time = body.scheduled_time
    if body.is_completed is not None:
        schedule.is_completed = body.is_completed

    await db.commit()
    await db.refresh(schedule)
    return _schedule_to_dict(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a schedule entry."""
    result = await db.execute(
        select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.user_id == current_user.id,
        )
    )
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    await db.delete(schedule)
    await db.commit()
