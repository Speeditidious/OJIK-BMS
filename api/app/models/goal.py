"""User goal model — quest/goal system for tracking chart or course targets.

A goal binds a user to a target outcome (clear type / min BP / rank / rate) on
either a single chart ("chart" goal) or a course ("course" goal), scoped to a
specific client (lr2 / beatoraja / qwilight). Achievement state (``status``,
``achieved_at``, ``achieved_recorded_at``) is only ever mutated by the goal
evaluator service (see plan §3.1 / Task 8) — never by direct admin edits.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserGoal(Base):
    """A user-defined goal targeting a chart or course outcome.

    ``baseline_snapshot`` captures the qualifying client's best record at
    goal-creation time so the evaluator can detect improvement without
    re-deriving history. ``projected_rating`` is display-only and must never
    be used in achievement judgment.
    """

    __tablename__ = "user_goals"
    __table_args__ = (
        Index("ix_user_goals_user_status", "user_id", "status"),
        Index(
            "ix_user_goals_chart_sha_lookup",
            "user_id", "client_type", "fumen_sha256",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_user_goals_chart_md5_lookup",
            "user_id", "client_type", "fumen_md5",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_user_goals_course_lookup", "user_id", "course_id"),
        # Partial unique index preventing duplicate active chart goals.
        # NULLs are coalesced to '' because Postgres treats NULL as distinct
        # from NULL in a plain unique index — see CLAUDE.md's fumen hash
        # lookup discipline (sha256/md5 dual-lookup for LR2 records).
        Index(
            "uq_user_goals_active_chart",
            "user_id", "client_type",
            text("COALESCE(fumen_sha256, '')"),
            text("COALESCE(fumen_md5, '')"),
            "table_slug",
            unique=True,
            postgresql_where=text("status = 'active' AND goal_type = 'chart' AND deleted_at IS NULL"),
        ),
        # Partial unique index preventing duplicate active course goals.
        Index(
            "uq_user_goals_active_course",
            "user_id", "client_type", "course_id",
            unique=True,
            postgresql_where=text("status = 'active' AND goal_type = 'course' AND deleted_at IS NULL"),
        ),
    )

    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    goal_type: Mapped[str] = mapped_column(String(8), nullable=False)  # 'chart' | 'course'
    client_type: Mapped[str] = mapped_column(String(32), nullable=False)  # lr2 / beatoraja / qwilight
    table_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    fumen_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    fumen_md5: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Course goal target. No FK constraint to `courses.id` — informational only
    # (per plan §3.1), since a course goal snapshots the course identity via
    # course_md5_list rather than tracking live course row changes.
    course_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    course_md5_list: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    target_clear_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_min_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_rank: Mapped[str | None] = mapped_column(String(4), nullable=True)
    target_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0~100
    # Display-only projected rating; never used in achievement judgment.
    projected_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # 'active' | 'achieved'
    baseline_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The triggering score's recorded_at — attributes goal achievement to the
    # correct calendar/day-sheet date (plan §3.6), distinct from achieved_at
    # (the server-side timestamp of when the evaluator marked it achieved).
    achieved_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<UserGoal goal_id={self.goal_id} user={self.user_id} type={self.goal_type} status={self.status}>"
