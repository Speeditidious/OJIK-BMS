import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ClientUpdateAnnouncement(Base, TimestampMixin):
    """Admin-published desktop client update announcement."""

    __tablename__ = "client_update_announcements"
    __table_args__ = (
        UniqueConstraint(
            "version",
            "channel",
            "target_os",
            "arch",
            "installer_kind",
            name="uq_client_update_announcements_release_target",
        ),
        Index(
            "ix_client_update_announcements_visible_target",
            "channel",
            "target_os",
            "arch",
            "installer_kind",
            "is_published",
            "publish_after",
        ),
        Index("ix_client_update_announcements_version", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), default="stable", nullable=False, server_default=text("'stable'"))
    target_os: Mapped[str] = mapped_column(String(16), default="windows", nullable=False, server_default=text("'windows'"))
    arch: Mapped[str] = mapped_column(String(16), default="x86_64", nullable=False, server_default=text("'x86_64'"))
    installer_kind: Mapped[str] = mapped_column(String(16), default="nsis", nullable=False, server_default=text("'nsis'"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    release_page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    update_url: Mapped[str] = mapped_column(Text, nullable=False)
    tauri_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    asset_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    min_supported_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    publish_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ClientUpdateAnnouncement version={self.version} channel={self.channel}>"
