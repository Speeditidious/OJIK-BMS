"""Published announcement endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.announcement import Announcement, AnnouncementTag
from app.schemas import Pagination

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementTagRead(BaseModel):
    id: uuid.UUID
    name: str
    name_en: str | None = None
    name_ja: str | None = None
    color: str | None = None
    send_notification: bool = False
    display_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnnouncementRead(BaseModel):
    id: uuid.UUID
    tag: AnnouncementTagRead
    title: str
    title_en: str | None = None
    title_ja: str | None = None
    body: str
    body_en: str | None = None
    body_ja: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=Pagination[AnnouncementRead])
async def list_announcements(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=50),
    tag: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> Pagination[AnnouncementRead]:
    """List published announcements with optional tag filter."""
    filters = [Announcement.is_published.is_(True)]
    if tag:
        try:
            tag_id = uuid.UUID(tag)
            filters.append(Announcement.tag_id == tag_id)
        except ValueError:
            filters.append(AnnouncementTag.name == tag)

    query = select(Announcement).join(AnnouncementTag).options(selectinload(Announcement.tag)).where(*filters)
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = int(total_result.scalar() or 0)
    result = await db.execute(
        query.order_by(Announcement.published_at.desc().nulls_last(), Announcement.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = list(result.scalars().all())
    return Pagination(
        items=[AnnouncementRead.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.get("/latest", response_model=AnnouncementRead | None)
async def latest_announcement(db: AsyncSession = Depends(get_db)) -> AnnouncementRead | None:
    """Return the latest published announcement for the home page preview."""
    result = await db.execute(
        select(Announcement)
        .join(AnnouncementTag)
        .options(selectinload(Announcement.tag))
        .where(Announcement.is_published.is_(True))
        .order_by(Announcement.published_at.desc().nulls_last(), Announcement.created_at.desc())
        .limit(1)
    )
    announcement = result.scalar_one_or_none()
    return AnnouncementRead.model_validate(announcement) if announcement else None


@router.get("/tags", response_model=list[AnnouncementTagRead])
async def list_announcement_tags(db: AsyncSession = Depends(get_db)) -> list[AnnouncementTagRead]:
    """List announcement tags for filter controls and badges."""
    result = await db.execute(
        select(AnnouncementTag).order_by(AnnouncementTag.display_order, AnnouncementTag.name)
    )
    return [AnnouncementTagRead.model_validate(tag) for tag in result.scalars().all()]
