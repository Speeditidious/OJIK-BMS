"""User notification endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, case, false, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.notification import (
    Notification,
    NotificationRead,
    NotificationUserState,
)
from app.models.user import User
from app.schemas import Pagination

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationReadItem(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str | None = None
    link_url: str | None = None
    metadata: dict | None = None
    created_at: datetime
    is_read: bool

    model_config = ConfigDict(from_attributes=True)


class NotificationIdsRequest(BaseModel):
    notification_ids: list[uuid.UUID]


class UnreadCountRead(BaseModel):
    count: int


@router.get("/", response_model=Pagination[NotificationReadItem])
async def list_notifications(
    type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    keyword: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Pagination[NotificationReadItem]:
    """List notifications visible to the current user."""
    now = datetime.now(UTC)
    state = await _get_user_notification_state(current_user.id, db)
    read_cutoff_at = state.read_cutoff_at if state else None
    is_read_expr = _is_read_expression(current_user, read_cutoff_at)

    query = (
        select(Notification, is_read_expr.label("is_read"))
        .outerjoin(
            NotificationRead,
            and_(
                NotificationRead.notification_id == Notification.id,
                NotificationRead.user_id == current_user.id,
            ),
        )
        .where(
            Notification.is_published.is_(True),
            Notification.created_at <= now,
            or_(Notification.target_user_id.is_(None), Notification.target_user_id == current_user.id),
            or_(NotificationRead.deleted_at.is_(None), NotificationRead.user_id.is_(None)),
        )
    )
    if type:
        query = query.where(Notification.type == type)
    if date_from:
        query = query.where(Notification.created_at >= date_from)
    if date_to:
        query = query.where(Notification.created_at <= date_to)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.where(or_(Notification.title.ilike(pattern), Notification.body.ilike(pattern)))
    if unread_only:
        query = query.where(is_read_expr.is_(False))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = int(total_result.scalar() or 0)
    result = await db.execute(
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = [_notification_item(notification, is_read) for notification, is_read in result.all()]
    return Pagination(items=items, total=total, page=page, size=size, pages=(total + size - 1) // size)


@router.get("/unread-count", response_model=UnreadCountRead)
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountRead:
    """Return unread notification count for navbar polling."""
    now = datetime.now(UTC)
    state = await _get_user_notification_state(current_user.id, db)
    read_cutoff_at = state.read_cutoff_at if state else None
    is_read_expr = _is_read_expression(current_user, read_cutoff_at)
    query = (
        select(func.count())
        .select_from(Notification)
        .outerjoin(
            NotificationRead,
            and_(
                NotificationRead.notification_id == Notification.id,
                NotificationRead.user_id == current_user.id,
            ),
        )
        .where(
            Notification.is_published.is_(True),
            Notification.created_at <= now,
            Notification.created_at >= current_user.created_at,
            or_(Notification.target_user_id.is_(None), Notification.target_user_id == current_user.id),
            or_(NotificationRead.deleted_at.is_(None), NotificationRead.user_id.is_(None)),
            is_read_expr.is_(False),
        )
    )
    result = await db.execute(query)
    return UnreadCountRead(count=int(result.scalar() or 0))


@router.post("/read", response_model=UnreadCountRead)
async def mark_notifications_read(
    body: NotificationIdsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountRead:
    """Mark selected notifications as read."""
    now = datetime.now(UTC)
    for notification_id in body.notification_ids:
        stmt = (
            insert(NotificationRead)
            .values(user_id=current_user.id, notification_id=notification_id, read_at=now)
            .on_conflict_do_update(
                index_elements=[NotificationRead.user_id, NotificationRead.notification_id],
                set_={"read_at": now},
            )
        )
        await db.execute(stmt)
    await db.commit()
    return await unread_count(current_user, db)


@router.post("/read-all", response_model=UnreadCountRead)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountRead:
    """Mark all current notifications as read by moving the user's cutoff."""
    now = datetime.now(UTC)
    stmt = (
        insert(NotificationUserState)
        .values(user_id=current_user.id, read_cutoff_at=now)
        .on_conflict_do_update(
            index_elements=[NotificationUserState.user_id],
            set_={"read_cutoff_at": now, "updated_at": now},
        )
    )
    await db.execute(stmt)
    await db.commit()
    return UnreadCountRead(count=0)


@router.post("/delete", response_model=UnreadCountRead)
async def delete_notifications(
    body: NotificationIdsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountRead:
    """Hide selected notifications for the current user."""
    now = datetime.now(UTC)
    for notification_id in body.notification_ids:
        stmt = (
            insert(NotificationRead)
            .values(user_id=current_user.id, notification_id=notification_id, deleted_at=now)
            .on_conflict_do_update(
                index_elements=[NotificationRead.user_id, NotificationRead.notification_id],
                set_={"deleted_at": now},
            )
        )
        await db.execute(stmt)
    await db.commit()
    return await unread_count(current_user, db)


async def _get_user_notification_state(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> NotificationUserState | None:
    result = await db.execute(select(NotificationUserState).where(NotificationUserState.user_id == user_id))
    return result.scalar_one_or_none()


def _is_read_expression(user: User, read_cutoff_at: datetime | None):
    cutoff_expr = Notification.created_at <= read_cutoff_at if read_cutoff_at else false()
    before_signup_expr = Notification.created_at < user.created_at
    explicit_read_expr = NotificationRead.read_at.isnot(None)
    return case(
        (before_signup_expr, True),
        (cutoff_expr, True),
        (explicit_read_expr, True),
        else_=False,
    )


def _notification_item(notification: Notification, is_read: bool) -> NotificationReadItem:
    return NotificationReadItem(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        link_url=notification.link_url,
        metadata=notification.metadata_,
        created_at=notification.created_at,
        is_read=bool(is_read),
    )
