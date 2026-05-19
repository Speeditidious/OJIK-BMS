import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Notification(Base):
    """Broadcast or targeted notification visible to users."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_published_created", "is_published", "created_at"),
        Index("ix_notifications_target_published_created", "target_user_id", "is_published", "created_at"),
        Index("ix_notifications_type_created", "type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    announcement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=True,
    )
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    announcement = relationship("Announcement")


class NotificationRead(Base):
    """Per-user read/delete override for one notification."""

    __tablename__ = "notification_reads"
    __table_args__ = (
        Index("ix_notification_reads_user_deleted", "user_id", "deleted_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationUserState(Base, TimestampMixin):
    """Aggregate per-user notification state such as read-all cutoff."""

    __tablename__ = "notification_user_states"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    read_cutoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
