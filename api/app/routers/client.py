"""Public desktop client release/update endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.client_update import ClientUpdateAnnouncement
from app.services.client_update import (
    ReleaseTarget,
    get_latest_visible_release,
    get_latest_visible_update,
    published_at_for,
)

router = APIRouter(prefix="/client", tags=["client"])


class ClientUpdateAnnouncementResponse(BaseModel):
    id: uuid.UUID
    version: str
    title: str
    body_markdown: str
    release_page_url: str | None
    mandatory: bool
    asset_size_bytes: int | None
    published_at: datetime


class ClientUpdatePolicyResponse(BaseModel):
    update_available: bool
    message: str | None = None
    announcement: ClientUpdateAnnouncementResponse | None = None


class ClientLatestReleaseResponse(BaseModel):
    version: str
    installer_url: str
    release_page_url: str | None
    release_notes: str
    asset_size_bytes: int | None
    asset_sha256: str | None
    published_at: datetime


class TauriUpdateResponse(BaseModel):
    version: str
    pub_date: datetime
    url: str
    signature: str
    notes: str


@router.get("/update-policy", response_model=ClientUpdatePolicyResponse)
async def get_update_policy(
    version: str,
    target: str = "windows",
    arch: str = "x86_64",
    channel: str = "stable",
    installer_kind: str = "nsis",
    db: AsyncSession = Depends(get_db),
) -> ClientUpdatePolicyResponse:
    """Return the admin-published update announcement for an installed client."""
    announcement = await get_latest_visible_update(
        db,
        version,
        ReleaseTarget(target, arch, channel, installer_kind),
    )
    if announcement is None:
        return ClientUpdatePolicyResponse(update_available=False)
    return ClientUpdatePolicyResponse(
        update_available=True,
        announcement=_announcement_response(announcement),
    )


@router.get("/latest-release", response_model=ClientLatestReleaseResponse | None)
async def get_latest_release(
    target: str = "windows",
    arch: str = "x86_64",
    channel: str = "stable",
    installer_kind: str = "nsis",
    db: AsyncSession = Depends(get_db),
) -> ClientLatestReleaseResponse | None:
    """Return the latest admin-published installer for the download page."""
    release = await get_latest_visible_release(
        db,
        ReleaseTarget(target, arch, channel, installer_kind),
    )
    if release is None:
        return None
    return ClientLatestReleaseResponse(
        version=release.version,
        installer_url=release.update_url,
        release_page_url=release.release_page_url,
        release_notes=release.body_markdown,
        asset_size_bytes=release.asset_size_bytes,
        asset_sha256=release.asset_sha256,
        published_at=published_at_for(release),
    )


@router.get("/tauri-update/{target}/{arch}/{current_version}", response_model=TauriUpdateResponse)
async def get_tauri_update(
    target: str,
    arch: str,
    current_version: str,
    channel: str = "stable",
    installer_kind: str = "nsis",
    db: AsyncSession = Depends(get_db),
) -> TauriUpdateResponse | Response:
    """Return Tauri updater metadata, or 204 when no signed update is visible."""
    update = await get_latest_visible_update(
        db,
        current_version,
        ReleaseTarget(target, arch, channel, installer_kind),
    )
    if update is None or not update.tauri_signature:
        return Response(status_code=204)
    return TauriUpdateResponse(
        version=update.version,
        pub_date=published_at_for(update),
        url=update.update_url,
        signature=update.tauri_signature,
        notes=update.body_markdown,
    )


def _announcement_response(row: ClientUpdateAnnouncement) -> ClientUpdateAnnouncementResponse:
    return ClientUpdateAnnouncementResponse(
        id=row.id,
        version=row.version,
        title=row.title,
        body_markdown=row.body_markdown,
        release_page_url=row.release_page_url,
        mandatory=row.mandatory,
        asset_size_bytes=row.asset_size_bytes,
        published_at=published_at_for(row),
    )
