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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Fumen(Base, TimestampMixin):
    """Single BMS chart (차분) identified by MD5 and/or SHA256.

    No surrogate PK — md5/sha256 partial unique indexes serve as the identity.
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

    # Composite mapper-level PK (sha256, md5). No real DB PK constraint — uniqueness is
    # enforced by partial indexes uq_fumens_sha256 and uq_fumens_md5 (see migration 0031).
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, primary_key=True, index=True)
    md5: Mapped[str | None] = mapped_column(String(32), nullable=True, primary_key=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artist: Mapped[str | None] = mapped_column(String(256), nullable=True)
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
    youtube_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_entries: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Fumen sha256={self.sha256} md5={self.md5} title={self.title}>"


class UserFumenTag(Base):
    """User-defined tag per fumen (차분).

    Either fumen_sha256 or fumen_md5 must be set (not both null).
    Partial unique indexes enforce dedup per hash type.
    """

    __tablename__ = "user_fumen_tags"
    __table_args__ = (
        # Dedup when sha256 is present
        Index(
            "uq_user_fumen_tags_sha256",
            "user_id", "fumen_sha256", "tag",
            unique=True,
            postgresql_where=text("fumen_sha256 IS NOT NULL"),
        ),
        # Dedup when md5 is present (and sha256 is absent)
        Index(
            "uq_user_fumen_tags_md5",
            "user_id", "fumen_md5", "tag",
            unique=True,
            postgresql_where=text("fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"),
        ),
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
    fumen_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    fumen_md5: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    tag: Mapped[str] = mapped_column(String(64), nullable=False)

    def __repr__(self) -> str:
        hash_key = self.fumen_sha256 or self.fumen_md5
        return f"<UserFumenTag user_id={self.user_id} hash={hash_key} tag={self.tag}>"
