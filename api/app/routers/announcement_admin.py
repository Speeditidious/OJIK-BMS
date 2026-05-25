"""Admin-only announcement endpoints (create, update, publish, list all)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.announcement import Announcement, AnnouncementTag
from app.routers.announcements import AnnouncementRead
from app.schemas import Pagination
from app.services.announcements import publish_announcement

router = APIRouter(prefix="/announcements/admin", tags=["announcements-admin"])


class AnnouncementWrite(BaseModel):
    """Schema for creating or updating an announcement."""

    tag_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    title_ja: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1)
    body_en: str | None = None
    body_ja: str | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=Pagination[AnnouncementRead])
async def admin_list_announcements(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    tag: str | None = Query(default=None),
    published: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> Pagination[AnnouncementRead]:
    """List all announcements (published + unpublished drafts) with optional filters."""
    filters = []

    if published is not None:
        filters.append(Announcement.is_published.is_(published))

    if tag:
        try:
            tag_id = uuid.UUID(tag)
            filters.append(Announcement.tag_id == tag_id)
        except ValueError:
            filters.append(AnnouncementTag.name == tag)

    query = (
        select(Announcement)
        .join(AnnouncementTag)
        .options(selectinload(Announcement.tag))
    )
    if filters:
        query = query.where(*filters)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = int(total_result.scalar() or 0)

    result = await db.execute(
        query.order_by(Announcement.created_at.desc())
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


@router.get("/{announcement_id}", response_model=AnnouncementRead)
async def admin_get_announcement(
    announcement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> AnnouncementRead:
    """Get a single announcement by ID (published or draft)."""
    result = await db.execute(
        select(Announcement)
        .options(selectinload(Announcement.tag))
        .where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    return AnnouncementRead.model_validate(announcement)


@router.post("/", response_model=AnnouncementRead, status_code=status.HTTP_201_CREATED)
async def admin_create_announcement(
    payload: AnnouncementWrite,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> AnnouncementRead:
    """Create an unpublished draft announcement."""
    tag_result = await db.execute(
        select(AnnouncementTag).where(AnnouncementTag.id == payload.tag_id)
    )
    tag = tag_result.scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag not found")

    now = datetime.now(UTC)
    announcement = Announcement(
        tag_id=payload.tag_id,
        title=payload.title,
        title_en=payload.title_en,
        title_ja=payload.title_ja,
        body=payload.body,
        body_en=payload.body_en,
        body_ja=payload.body_ja,
        is_published=False,
        published_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(announcement)
    await db.flush()
    await db.refresh(announcement, ["tag"])
    await db.commit()
    await db.refresh(announcement, ["tag"])
    return AnnouncementRead.model_validate(announcement)


@router.patch("/{announcement_id}", response_model=AnnouncementRead)
async def admin_update_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementWrite,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> AnnouncementRead:
    """Edit an existing announcement (published or draft). Does not clear published_at."""
    result = await db.execute(
        select(Announcement)
        .options(selectinload(Announcement.tag))
        .where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")

    # Validate tag exists
    tag_result = await db.execute(
        select(AnnouncementTag).where(AnnouncementTag.id == payload.tag_id)
    )
    if tag_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag not found")

    announcement.tag_id = payload.tag_id
    announcement.title = payload.title
    announcement.title_en = payload.title_en
    announcement.title_ja = payload.title_ja
    announcement.body = payload.body
    announcement.body_en = payload.body_en
    announcement.body_ja = payload.body_ja
    announcement.updated_at = datetime.now(UTC)
    # NOTE: published_at is intentionally NOT cleared on content changes

    await db.commit()
    await db.refresh(announcement, ["tag"])
    return AnnouncementRead.model_validate(announcement)


@router.post("/{announcement_id}/publish", response_model=AnnouncementRead)
async def admin_publish_announcement(
    announcement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> AnnouncementRead:
    """Publish an announcement and create its notification."""
    announcement = await publish_announcement(db, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    await db.commit()
    await db.refresh(announcement, ["tag"])
    return AnnouncementRead.model_validate(announcement)
