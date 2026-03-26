import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class UserPlayerStats(Base):
    __tablename__ = "user_player_stats"
    # Uniqueness enforced by functional index: (user_id, client_type, (synced_at AT TIME ZONE 'UTC')::date)
    # Managed in migration 0039 — not representable as a standard SQLAlchemy UniqueConstraint.

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    client_type: Mapped[str] = mapped_column(String(32), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    playcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clearcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playtime: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    judgments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<UserPlayerStats user={self.user_id} client={self.client_type} synced_at={self.synced_at}>"


class UserScore(Base):
    __tablename__ = "user_scores"
    __table_args__ = (
        Index("ix_user_scores_user_id_recorded_at", "user_id", "recorded_at"),
        # Partial unique index for scorehash deduplication
        Index(
            "uq_user_scores_scorehash",
            "scorehash", "user_id", "client_type",
            unique=True,
            postgresql_where=text("scorehash IS NOT NULL"),
        ),
        Index("ix_user_scores_user_id_fumen_sha256", "user_id", "fumen_sha256"),
        Index("ix_user_scores_user_id_fumen_md5", "user_id", "fumen_md5"),
        Index("ix_user_scores_user_id_fumen_hash_others", "user_id", "fumen_hash_others"),
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
    client_type: Mapped[str] = mapped_column(String(32), nullable=False)  # lr2 / beatoraja / qwilight
    scorehash: Mapped[str | None] = mapped_column(Text, nullable=True)
    fumen_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fumen_md5: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fumen_hash_others: Mapped[str | None] = mapped_column(Text, nullable=True)
    clear_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exscore: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[str | None] = mapped_column(String(4), nullable=True)
    max_combo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    play_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clear_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    judgments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=True,
    )
    def __repr__(self) -> str:
        return f"<UserScore id={self.id} user={self.user_id} sha256={self.fumen_sha256}>"
