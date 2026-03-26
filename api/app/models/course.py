"""Course model."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Course(Base):
    """Course (단위 코스 등) — sourced from difficulty table header or admin-created."""

    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_source_table_id", "source_table_id"),
        Index("ix_courses_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_table_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("difficulty_tables.id", ondelete="SET NULL"),
        nullable=True,
    )
    md5_list: Mapped[list] = mapped_column(JSONB, nullable=False)
    sha256_list: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    dan_title: Mapped[str] = mapped_column(Text, nullable=False, server_default="''")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    def __repr__(self) -> str:
        return f"<Course id={self.id} name={self.name}>"


