import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class IssueTag(Base, TimestampMixin):
    """Admin-managed issue tag and body placeholder hint."""

    __tablename__ = "issue_tags"
    __table_args__ = (
        Index("ix_issue_tags_active_order", "is_active", "display_order", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name_ja: Mapped[str | None] = mapped_column(String(64), nullable=True)
    color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default=text("true"))

    def __str__(self) -> str:
        return self.name


class Issue(Base, TimestampMixin):
    """Public user-created issue thread."""

    __tablename__ = "issues"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'work_in_progress', 'completed', 'not_planned')",
            name="ck_issues_status",
        ),
        Index("ix_issues_status_activity", "status", "last_activity_at", "id"),
        Index("ix_issues_tag_status_activity", "tag_id", "status", "last_activity_at", "id"),
        Index("ix_issues_status_created_at", "status", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issue_tags.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, server_default=text("'open'"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default=text("0"))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    author = relationship("User", foreign_keys=[author_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    tag: Mapped[IssueTag] = relationship("IssueTag")
    comments: Mapped[list["IssueComment"]] = relationship("IssueComment", cascade="all, delete-orphan", back_populates="issue")


class IssueComment(Base, TimestampMixin):
    """Public comment on an issue thread."""

    __tablename__ = "issue_comments"
    __table_args__ = (
        Index("ix_issue_comments_issue_created", "issue_id", "created_at", "id"),
        Index("ix_issue_comments_author_created", "author_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # event_type is NULL for regular user comments. Non-NULL rows are system events
    # (e.g. "status_change") rendered inline in the timeline and ignored by comment_count.
    event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    issue: Mapped[Issue] = relationship("Issue", back_populates="comments")
    author = relationship("User")


class IssueUserMention(Base, TimestampMixin):
    """Resolved user mention found in an issue body or comment."""

    __tablename__ = "issue_user_mentions"
    __table_args__ = (
        UniqueConstraint("issue_id", "comment_id", "mentioned_user_id", name="uq_issue_user_mentions_source_user"),
        Index("ix_issue_user_mentions_user_created", "mentioned_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    comment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("issue_comments.id", ondelete="CASCADE"), nullable=True)
    mentioned_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_text: Mapped[str] = mapped_column(String(128), nullable=False)
    mentioned_user = relationship("User", foreign_keys=[mentioned_user_id])


class IssueIssueReference(Base, TimestampMixin):
    """Resolved issue reference found in an issue body or comment."""

    __tablename__ = "issue_issue_references"
    __table_args__ = (
        UniqueConstraint("source_issue_id", "source_comment_id", "target_issue_id", name="uq_issue_issue_refs_source_target"),
        Index("ix_issue_issue_refs_target_created", "target_issue_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    source_issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    source_comment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("issue_comments.id", ondelete="CASCADE"), nullable=True)
    target_issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    source_text: Mapped[str] = mapped_column(String(32), nullable=False)
