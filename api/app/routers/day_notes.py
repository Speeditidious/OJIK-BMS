"""Per-day calendar note endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.day_note import UserDayNote
from app.models.user import User

router = APIRouter(tags=["day-notes"])

_MAX_CONTENT_LEN = 2000


class DayNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    content: str
    created_at: str
    updated_at: str


class DayNoteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    updated_at: str


class DayNotePayload(BaseModel):
    content: str


def _parse_date(date_str: str) -> date:
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")


@router.get("/users/{user_id}/day-notes", response_model=list[DayNoteSummary])
async def list_month_notes(
    user_id: uuid.UUID,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
) -> list[DayNoteSummary]:
    """Return dates with notes for the given user/month (no content — icon display only)."""
    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    rows = (await db.execute(
        select(UserDayNote.note_date, UserDayNote.updated_at)
        .where(and_(
            UserDayNote.user_id == user_id,
            UserDayNote.note_date >= month_start,
            UserDayNote.note_date < month_end,
        ))
        .order_by(UserDayNote.note_date)
    )).all()

    return [
        DayNoteSummary(date=r.note_date, updated_at=r.updated_at.isoformat())
        for r in rows
    ]


@router.get("/users/{user_id}/day-notes/{date_str}", response_model=DayNoteRead | None)
async def get_day_note(
    user_id: uuid.UUID,
    date_str: str,
    db: AsyncSession = Depends(get_db),
) -> DayNoteRead | None:
    """Return single note for user/date, or null if none."""
    note_date = _parse_date(date_str)
    row = (await db.execute(
        select(UserDayNote)
        .where(and_(
            UserDayNote.user_id == user_id,
            UserDayNote.note_date == note_date,
        ))
    )).scalar_one_or_none()

    if row is None:
        return None
    return DayNoteRead(
        date=row.note_date,
        content=row.content,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@router.put("/me/day-notes/{date_str}", response_model=DayNoteRead | None)
async def upsert_day_note(
    date_str: str,
    payload: DayNotePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DayNoteRead | None:
    """Upsert a day note. Empty content after strip = delete. Max 2000 chars."""
    note_date = _parse_date(date_str)
    content = payload.content.strip()

    if not content:
        await db.execute(
            delete(UserDayNote).where(
                and_(
                    UserDayNote.user_id == current_user.id,
                    UserDayNote.note_date == note_date,
                )
            )
        )
        await db.commit()
        return None

    if len(content) > _MAX_CONTENT_LEN:
        raise HTTPException(status_code=422, detail=f"content exceeds {_MAX_CONTENT_LEN} characters")

    stmt = (
        pg_insert(UserDayNote)
        .values(user_id=current_user.id, note_date=note_date, content=content)
        .on_conflict_do_update(
            index_elements=["user_id", "note_date"],
            set_={"content": content, "updated_at": func.now()},
        )
        .returning(UserDayNote.note_date, UserDayNote.content, UserDayNote.created_at, UserDayNote.updated_at)
    )
    row = (await db.execute(stmt)).one()
    await db.commit()
    return DayNoteRead(
        date=row.note_date,
        content=row.content,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@router.delete("/me/day-notes/{date_str}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_day_note(
    date_str: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a day note."""
    note_date = _parse_date(date_str)
    await db.execute(
        delete(UserDayNote).where(
            and_(
                UserDayNote.user_id == current_user.id,
                UserDayNote.note_date == note_date,
            )
        )
    )
    await db.commit()
