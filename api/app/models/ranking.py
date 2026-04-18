"""User ranking persistence model.

user_rankings: 유저별 최신 EXP / Rating (raw top-N) / BMSFORCE (rating_norm) — upsert.

user_ranking_history 테이블은 migration 0013 에서 제거됨.
히스토리는 user_scores 로부터 on-demand 계산 (ranking_calculator.compute_ranking_history_for_user).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, String, text
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
