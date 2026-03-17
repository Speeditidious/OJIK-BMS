import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserPlayerStats(Base):
    __tablename__ = "user_player_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    client_type: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    total_notes_hit: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_play_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<UserPlayerStats user={self.user_id} client={self.client_type}>"


class UserPlayerStatsHistory(Base):
    __tablename__ = "user_player_stats_history"
    __table_args__ = (
        UniqueConstraint("user_id", "client_type", "sync_date", name="uq_player_stats_history"),
        Index("ix_player_stats_history_user_date", "user_id", "sync_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    client_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sync_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_notes_hit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_play_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<UserPlayerStatsHistory user={self.user_id} client={self.client_type} date={self.sync_date}>"


class UserScore(Base):
    __tablename__ = "user_scores"
    __table_args__ = (
        # Unique enforcement: migration 0006 creates a functional unique index
        # uq_user_scores_coalesce ON (user_id, COALESCE(song_sha256, song_md5), client_type).
        # Not declared here because SQLAlchemy cannot express COALESCE in __table_args__.
        Index("ix_user_scores_user_id_played_at", "user_id", "played_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # ForeignKey referenced as string to avoid circular imports
        nullable=False,
        index=True,
    )
    song_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    song_md5: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    client_type: Mapped[str] = mapped_column(String(32), nullable=False)  # lr2 / beatoraja / qwilight
    clear_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_combo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    judgments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    play_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clear_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    hit_notes: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<UserScore id={self.id} user={self.user_id} sha256={self.song_sha256}>"


class ScoreHistory(Base):
    __tablename__ = "score_history"
    __table_args__ = (
        Index("ix_score_history_user_id_recorded_at", "user_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    song_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    song_md5: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    client_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sync_date: Mapped[date] = mapped_column(Date, nullable=False)
    clear_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_clear_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    old_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    combo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_combo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_min_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clear_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_clear_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    play_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_play_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ScoreHistory id={self.id} user={self.user_id}>"
