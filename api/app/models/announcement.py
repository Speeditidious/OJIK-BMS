import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AnnouncementTag(Base, TimestampMixin):
    """Admin-managed announcement tag."""

    __tablename__ = "announcement_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name_ja: Mapped[str | None] = mapped_column(String(64), nullable=True)
    color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    send_notification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default=text("0"))

    def __str__(self) -> str:
        return self.name


class Announcement(Base, TimestampMixin):
    """Admin-published site announcement."""

    __tablename__ = "announcements"
    __table_args__ = (
        Index("ix_announcements_published_at", "is_published", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_tags.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title_ja: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_ja: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tag: Mapped[AnnouncementTag] = relationship("AnnouncementTag")
