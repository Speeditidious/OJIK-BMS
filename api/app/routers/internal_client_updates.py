"""Internal CI ingest endpoint for client update draft rows.

Only accessible with a pre-shared token stored in the CLIENT_UPDATE_INGEST_TOKEN env var.
CI creates unpublished draft rows; a human must review and publish via /admin.
"""

import re
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.client_update import ClientUpdateAnnouncement

router = APIRouter(prefix="/internal", tags=["internal"])

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_RELEASE_HOSTS = ("github.com",)


class ClientUpdateDraftIngestRequest(BaseModel):
    version: str
    channel: str = "stable"
    target_os: str = "windows"
    arch: str = "x86_64"
    installer_kind: str = "nsis"
    title: str
    body_markdown: str
    body_markdown_en: str | None = None
    body_markdown_ja: str | None = None
    release_page_url: str
    update_url: str
    tauri_signature: str
    asset_size_bytes: int
    asset_sha256: str
    mandatory: bool = False
    min_supported_version: str | None = None

    @field_validator("update_url")
    @classmethod
    def validate_update_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("update_url must start with https://")
        if "/releases/tag/" in v:
            raise ValueError("update_url must be a direct download URL, not a release page")
        if "/releases/download/" not in v:
            raise ValueError("update_url must be a direct GitHub release asset URL")
        return v

    @field_validator("release_page_url")
    @classmethod
    def validate_release_page_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("release_page_url must start with https://")
        host = v.split("/")[2] if len(v.split("/")) > 2 else ""
        if not any(host == h or host.endswith(f".{h}") for h in _ALLOWED_RELEASE_HOSTS):
            raise ValueError(f"release_page_url host must be one of: {_ALLOWED_RELEASE_HOSTS}")
        return v

    @field_validator("tauri_signature")
    @classmethod
    def validate_tauri_signature(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("tauri_signature must not be empty")
        return v.strip()

    @field_validator("asset_sha256")
    @classmethod
    def validate_asset_sha256(cls, v: str) -> str:
        if not _SHA256_RE.match(v):
            raise ValueError("asset_sha256 must be a lowercase 64-character hex string")
        return v

    @field_validator("asset_size_bytes")
    @classmethod
    def validate_asset_size_bytes(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("asset_size_bytes must be greater than zero")
        return v


class ClientUpdateDraftIngestResponse(BaseModel):
    id: uuid.UUID
    version: str
    is_published: bool
    created: bool


def _require_ingest_token(x_ojik_internal_token: str = Header(default="")) -> None:
    """Reject requests without the correct CI ingest token."""
    expected = settings.CLIENT_UPDATE_INGEST_TOKEN
    if not expected or not secrets.compare_digest(
        x_ojik_internal_token.encode(), expected.encode()
    ):
        raise HTTPException(status_code=404)


@router.post(
    "/client-updates/from-release",
    response_model=ClientUpdateDraftIngestResponse,
    status_code=200,
    dependencies=[],
)
async def ingest_client_update_draft(
    payload: ClientUpdateDraftIngestRequest,
    x_ojik_internal_token: str = Header(default=""),
) -> ClientUpdateDraftIngestResponse | Response:
    """Create or update an unpublished client update row from CI."""
    _require_ingest_token(x_ojik_internal_token)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ClientUpdateAnnouncement).where(
                ClientUpdateAnnouncement.version == payload.version,
                ClientUpdateAnnouncement.channel == payload.channel,
                ClientUpdateAnnouncement.target_os == payload.target_os,
                ClientUpdateAnnouncement.arch == payload.arch,
                ClientUpdateAnnouncement.installer_kind == payload.installer_kind,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None and existing.is_published:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A published update row for version {payload.version!r} already exists. "
                    "Unpublish it or create a new version before re-ingesting."
                ),
            )

        now = datetime.now(UTC)
        if existing is None:
            row = ClientUpdateAnnouncement(
                version=payload.version,
                channel=payload.channel,
                target_os=payload.target_os,
                arch=payload.arch,
                installer_kind=payload.installer_kind,
                title=payload.title,
                body_markdown=payload.body_markdown,
                body_markdown_en=payload.body_markdown_en,
                body_markdown_ja=payload.body_markdown_ja,
                release_page_url=payload.release_page_url,
                update_url=payload.update_url,
                tauri_signature=payload.tauri_signature,
                asset_size_bytes=payload.asset_size_bytes,
                asset_sha256=payload.asset_sha256,
                mandatory=payload.mandatory,
                min_supported_version=payload.min_supported_version,
                is_published=False,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return ClientUpdateDraftIngestResponse(
                id=row.id,
                version=row.version,
                is_published=row.is_published,
                created=True,
            )

        existing.title = payload.title
        existing.body_markdown = payload.body_markdown
        if "body_markdown_en" in payload.model_fields_set:
            existing.body_markdown_en = payload.body_markdown_en
        if "body_markdown_ja" in payload.model_fields_set:
            existing.body_markdown_ja = payload.body_markdown_ja
        existing.release_page_url = payload.release_page_url
        existing.update_url = payload.update_url
        existing.tauri_signature = payload.tauri_signature
        existing.asset_size_bytes = payload.asset_size_bytes
        existing.asset_sha256 = payload.asset_sha256
        existing.mandatory = payload.mandatory
        existing.min_supported_version = payload.min_supported_version
        existing.updated_at = now
        await db.commit()
        return ClientUpdateDraftIngestResponse(
            id=existing.id,
            version=existing.version,
            is_published=existing.is_published,
            created=False,
        )
