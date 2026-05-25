"""Announcement publishing service.

Provides ``publish_announcement`` and ``publish_announcements`` so that both
the sqladmin bulk-action and the form ``on_model_change`` / ``after_model_change``
hooks share the same business logic.

Important: these functions do **not** commit — callers are responsible for
calling ``db.commit()`` after the call returns.
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.announcement import Announcement, AnnouncementTemplate
from app.services.notifications import create_announcement_notification

# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

_ALLOWED_PLACEHOLDERS: frozenset[str] = frozenset({"date", "yyyy", "mm", "dd"})
_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")


def validate_template_placeholders(template: str) -> None:
    """Raise HTTP 422 if *template* contains any unsupported ``{...}`` tokens.

    Only ``{date}``, ``{yyyy}``, ``{mm}``, and ``{dd}`` are allowed.
    """
    for match in _PLACEHOLDER_RE.finditer(template):
        token = match.group(1)
        if token not in _ALLOWED_PLACEHOLDERS:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown placeholder '{{{token}}}'. "
                       f"Allowed: {{date}}, {{yyyy}}, {{mm}}, {{dd}}.",
            )


def render_template(template: str | None, ref_date: date) -> str | None:
    """Replace date placeholders in *template* using *ref_date*.

    Returns ``None`` if *template* is ``None``.
    """
    if template is None:
        return None
    return (
        template
        .replace("{date}", ref_date.strftime("%Y-%m-%d"))
        .replace("{yyyy}", ref_date.strftime("%Y"))
        .replace("{mm}", ref_date.strftime("%m"))
        .replace("{dd}", ref_date.strftime("%d"))
    )


def render_announcement_template(
    tmpl: AnnouncementTemplate | None,
    ref_date: date | None = None,
) -> dict[str, Any]:
    """Render an ``AnnouncementTemplate`` row to a dict of expanded strings.

    If *tmpl* is ``None`` all fields default to empty strings / ``None``.
    *ref_date* defaults to today (UTC) when not provided.
    """
    d = ref_date or datetime.now(UTC).date()
    if tmpl is None:
        return {
            "tag_id": None,
            "title": "",
            "title_en": None,
            "title_ja": None,
            "body": "",
            "body_en": None,
            "body_ja": None,
        }
    return {
        "tag_id": tmpl.tag_id,
        "title": render_template(tmpl.title_template, d) or "",
        "title_en": render_template(tmpl.title_en_template, d),
        "title_ja": render_template(tmpl.title_ja_template, d),
        "body": render_template(tmpl.body_template, d) or "",
        "body_en": render_template(tmpl.body_en_template, d),
        "body_ja": render_template(tmpl.body_ja_template, d),
    }


async def publish_announcement(
    db: AsyncSession,
    announcement_id: uuid.UUID,
    now: datetime | None = None,
) -> Announcement | None:
    """Publish one announcement and create its notification.

    - Loads the announcement with its tag relationship eagerly.
    - Sets ``is_published = True``.
    - Sets ``published_at`` to *now* if it is not already set.
    - Sets ``updated_at`` to *now*.
    - Calls ``create_announcement_notification`` (deduplication is handled there).

    Returns the updated ``Announcement`` instance, or ``None`` if not found.
    Caller must commit.
    """
    if now is None:
        now = datetime.now(UTC)

    result = await db.execute(
        select(Announcement)
        .options(selectinload(Announcement.tag))
        .where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()
    if announcement is None:
        return None

    announcement.is_published = True
    if announcement.published_at is None:
        announcement.published_at = now
    announcement.updated_at = now

    await create_announcement_notification(db, announcement)
    return announcement


async def publish_announcements(
    db: AsyncSession,
    announcement_ids: list[uuid.UUID],
    now: datetime | None = None,
) -> list[Announcement]:
    """Bulk-publish a list of announcements.

    Uses a single UPDATE to flip the DB rows, then loads them and calls
    ``publish_announcement`` logic (notification + published_at) for each.

    Returns the list of updated ``Announcement`` objects. Caller must commit.
    """
    if not announcement_ids:
        return []

    if now is None:
        now = datetime.now(UTC)

    # Bulk-update: set is_published, coalesce published_at, set updated_at.
    await db.execute(
        update(Announcement)
        .where(Announcement.id.in_(announcement_ids))
        .values(
            is_published=True,
            published_at=func.coalesce(Announcement.published_at, now),
            updated_at=now,
        )
    )

    # Reload to get the current state (including coalesced published_at) and tag.
    result = await db.execute(
        select(Announcement)
        .options(selectinload(Announcement.tag))
        .where(Announcement.id.in_(announcement_ids))
    )
    announcements = result.scalars().all()

    for announcement in announcements:
        await create_announcement_notification(db, announcement)

    return list(announcements)
