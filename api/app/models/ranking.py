"""User ranking persistence models."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Double,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserRanking(Base):
    __tablename__ = "user_rankings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("difficulty_tables.id", ondelete="CASCADE"),
        primary_key=True,
    )
    exp: Mapped[float] = mapped_column(Double, nullable=False, server_default="0")
    exp_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rating: Mapped[float] = mapped_column(Double, nullable=False, server_default="0")
    rating_norm: Mapped[float] = mapped_column(Double, nullable=False, server_default="0")
    rating_contributions: Mapped[list | dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    exp_top_contributions: Mapped[list | dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    dan_title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class UserTableRatingCheckpoint(Base):
    __tablename__ = "user_table_rating_checkpoints"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("difficulty_tables.id", ondelete="CASCADE"),
        primary_key=True,
    )
    effective_date: Mapped[date] = mapped_column(Date, primary_key=True)
    exp: Mapped[float] = mapped_column(Double, nullable=False, server_default="0")
    rating: Mapped[float] = mapped_column(Double, nullable=False, server_default="0")


class UserTableRatingUpdateDaily(Base):
    __tablename__ = "user_table_rating_update_daily"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("difficulty_tables.id", ondelete="CASCADE"),
        primary_key=True,
    )
    effective_date: Mapped[date] = mapped_column(Date, primary_key=True)
    update_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class UserRatingUpdateDaily(Base):
    __tablename__ = "user_rating_update_daily"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    effective_date: Mapped[date] = mapped_column(Date, primary_key=True)
    update_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
