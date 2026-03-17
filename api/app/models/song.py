import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Song(Base, TimestampMixin):
    __tablename__ = "songs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    md5: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    sha256: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subtitle: Mapped[str | None] = mapped_column(String(256), nullable=True)
    artist: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subartist: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bpm: Mapped[float | None] = mapped_column(nullable=True)
    total_notes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<Song id={self.id} title={self.title}>"


class UserOwnedSong(Base):
    __tablename__ = "user_owned_songs"
    __table_args__ = (
        UniqueConstraint("user_id", "song_sha256", name="uq_user_owned_songs"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    song_md5: Mapped[str | None] = mapped_column(String(32), nullable=True)
    song_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<UserOwnedSong user_id={self.user_id} sha256={self.song_sha256}>"


class UserSongTag(Base):
    __tablename__ = "user_song_tags"
    __table_args__ = (
        UniqueConstraint("user_id", "song_sha256", "tag", name="uq_user_song_tags"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    song_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    tag: Mapped[str] = mapped_column(String(64), primary_key=True)

    def __repr__(self) -> str:
        return f"<UserSongTag user_id={self.user_id} sha256={self.song_sha256} tag={self.tag}>"
