import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserDayNote(Base, TimestampMixin):
    """User-authored free-text (markdown) note pinned to a calendar day."""

    __tablename__ = "user_day_notes"
    __table_args__ = (
        Index("uq_user_day_notes_user_date", "user_id", "note_date", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    note_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<UserDayNote user_id={self.user_id} date={self.note_date}>"
