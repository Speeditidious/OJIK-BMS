"""Admin action audit and progress log models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AdminActionLog(Base):
    """Top-level sqladmin action log row."""

    __tablename__ = "admin_action_logs"
    __table_args__ = (
        Index("ix_admin_action_logs_parent_log_id", "parent_log_id"),
        Index("ix_admin_action_logs_action_name", "action_name"),
        Index("ix_admin_action_logs_target", "target_kind", "target_id"),
        Index("ix_admin_action_logs_status", "status"),
        Index("ix_admin_action_logs_started_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parent_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_action_logs.id", ondelete="CASCADE"),
        nullable=True,
    )
    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lines: Mapped[list["AdminActionLogLine"]] = relationship(
        "AdminActionLogLine",
        back_populates="log",
        cascade="all, delete-orphan",
        order_by="AdminActionLogLine.created_at",
        lazy="selectin",
    )


class AdminActionLogLine(Base):
    """Append-only line for a sqladmin action log."""

    __tablename__ = "admin_action_log_lines"
    __table_args__ = (
        Index("ix_admin_action_log_lines_log_created", "log_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_action_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    level: Mapped[str] = mapped_column(Text, nullable=False, server_default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    log: Mapped[AdminActionLog] = relationship("AdminActionLog", back_populates="lines", lazy="selectin")
