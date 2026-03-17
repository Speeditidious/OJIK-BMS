"""Course and course score models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Course(Base):
    """Defines a multi-song course, identified by its ordered song hash list."""

    __tablename__ = "courses"

    course_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)   # 'lr2' | 'beatoraja'
    song_count: Mapped[int] = mapped_column(Integer, nullable=False)
    song_hashes: Mapped[list] = mapped_column(JSONB, nullable=False)  # [{song_md5, song_sha256}, ...]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Course hash={self.course_hash[:16]}... songs={self.song_count}>"


class UserCourseScore(Base):
    """Best course score per user — upserted on improvement (mirrors UserScore logic)."""

    __tablename__ = "user_course_scores"
    __table_args__ = (
        UniqueConstraint("user_id", "course_hash", "client_type", name="uq_user_course_scores"),
        Index("ix_user_course_scores_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_hash: Mapped[str] = mapped_column(
        Text,
        ForeignKey("courses.course_hash", ondelete="CASCADE"),
        nullable=False,
    )
    client_type: Mapped[str] = mapped_column(String(32), nullable=False)
    clear_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_combo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    play_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clear_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<UserCourseScore user={self.user_id} hash={self.course_hash[:16]}...>"


class CourseScoreHistory(Base):
    """Append-only history of course score improvements (mirrors ScoreHistory)."""

    __tablename__ = "course_score_history"
    __table_args__ = (
        Index("ix_course_score_history_user_id_recorded_at", "user_id", "recorded_at"),
        Index("ix_course_score_history_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_hash: Mapped[str] = mapped_column(Text, nullable=False)
    client_type: Mapped[str] = mapped_column(String(32), nullable=False)
    clear_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_clear_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    old_score_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_combo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<CourseScoreHistory id={self.id} user={self.user_id}>"
