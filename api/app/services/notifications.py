from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.announcement import Announcement
from app.models.client_update import ClientUpdateAnnouncement
from app.models.notification import Notification


async def create_announcement_notification(db: AsyncSession, announcement: Announcement) -> Notification | None:
    """Create one deduplicated notification for a published announcement."""
    if not announcement.is_published or not announcement.tag.send_notification:
        return None
    return await _create_notification(
        db,
        type_="announcement",
        dedupe_key=f"announcement:{announcement.id}",
        title=announcement.title,
        body=announcement.body[:300] if announcement.body else None,
        link_url="/announcements",
        announcement_id=announcement.id,
    )


async def create_issue_mention_notification(
    db: AsyncSession,
    *,
    issue_id: int,
    issue_title: str,
    mentioned_user_id: uuid.UUID,
    actor_username: str,
    comment_id: uuid.UUID | None = None,
) -> Notification | None:
    """Create one deduplicated targeted notification for an issue/comment mention."""
    if comment_id is None:
        dedupe_key = f"issue_mention:issue:{issue_id}:user:{mentioned_user_id}"
        body = f"{actor_username} mentioned you in issue #{issue_id}."
    else:
        dedupe_key = f"issue_mention:comment:{comment_id}:user:{mentioned_user_id}"
        body = f"{actor_username} mentioned you in a comment on issue #{issue_id}."
    return await _create_notification(
        db,
        type_="issue_mention",
        dedupe_key=dedupe_key,
        title=f"#{issue_id} {issue_title}",
        body=body,
        link_url=f"/issues/{issue_id}",
        target_user_id=mentioned_user_id,
        metadata={"issue_id": issue_id, "comment_id": str(comment_id) if comment_id else None},
    )


async def create_client_update_notification(
    db: AsyncSession,
    update: ClientUpdateAnnouncement,
) -> Notification | None:
    """Create one deduplicated notification for a published client update version."""
    if not update.is_published:
        return None
    channel = update.channel or "stable"
    return await _create_notification(
        db,
        type_="client_update",
        dedupe_key=f"client_update:{channel}:{update.version}",
        title=update.title,
        body=update.body_markdown[:300] if update.body_markdown else None,
        link_url="/download",
        metadata={"version": update.version, "channel": channel},
    )


async def _create_notification(
    db: AsyncSession,
    *,
    type_: str,
    dedupe_key: str,
    title: str,
    body: str | None,
    link_url: str | None,
    announcement_id: uuid.UUID | None = None,
    target_user_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> Notification | None:
    existing_result = await db.execute(select(Notification).where(Notification.dedupe_key == dedupe_key))
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    notification = Notification(
        type=type_,
        target_user_id=target_user_id,
        announcement_id=announcement_id,
        dedupe_key=dedupe_key,
        title=title,
        body=body,
        link_url=link_url,
        metadata_=metadata,
        is_published=True,
        created_at=datetime.now(UTC),
    )
    db.add(notification)
    return notification
