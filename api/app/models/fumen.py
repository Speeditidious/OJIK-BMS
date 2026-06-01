import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Fumen(Base, TimestampMixin):
    """Single BMS chart (차분) identified by MD5 and/or SHA256.

    ``fumen_id`` is the stable internal identity. Hashes remain unique lookup
    keys because sync clients only know md5/sha256 values.
    """

    __tablename__ = "fumens"
    __table_args__ = (
        # Exactly one of md5 or sha256 must be present
        CheckConstraint("md5 IS NOT NULL OR sha256 IS NOT NULL", name="chk_fumens_hash"),
        # Partial unique indexes (declared here for Alembic; also applied in migration 0031)
        Index(
            "uq_fumens_sha256",
            "sha256",
            unique=True,
            postgresql_where=text("sha256 IS NOT NULL"),
        ),
        Index(
            "uq_fumens_md5",
            "md5",
            unique=True,
            postgresql_where=text("md5 IS NOT NULL AND sha256 IS NULL"),
        ),
    )

    fumen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    md5: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    artist: Mapped[str | None] = mapped_column(Text, nullable=True)
    bpm_min: Mapped[float | None] = mapped_column(nullable=True)
    bpm_max: Mapped[float | None] = mapped_column(nullable=True)
    bpm_main: Mapped[float | None] = mapped_column(nullable=True)
    notes_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes_ln: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes_ls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keymode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Fumen id={self.fumen_id} sha256={self.sha256} md5={self.md5} title={self.title}>"


class FumenTableEntry(Base, TimestampMixin):
    """Membership of one fumen in one difficulty table."""

    __tablename__ = "fumen_table_entries"
    __table_args__ = (
        Index("ix_fumen_table_entries_table_id_level", "table_id", "level", "fumen_id"),
    )

    fumen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fumens.fumen_id", ondelete="CASCADE"),
        primary_key=True,
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("difficulty_tables.id", ondelete="CASCADE"),
        primary_key=True,
    )
    level: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<FumenTableEntry fumen={self.fumen_id} table={self.table_id} level={self.level}>"


class UserFumenTag(Base):
    """User-defined tag per fumen (차분).

    Tags only apply to registered fumens, so they reference ``fumen_id``
    directly instead of repeating hash fallback logic.
    """

    __tablename__ = "user_fumen_tags"
    __table_args__ = (
        Index("uq_user_fumen_tags_fumen", "user_id", "fumen_id", "tag", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fumen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fumens.fumen_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    def __repr__(self) -> str:
        return f"<UserFumenTag user_id={self.user_id} fumen_id={self.fumen_id} tag={self.tag}>"
