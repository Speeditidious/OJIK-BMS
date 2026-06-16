import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Weekly(Base):
    """One generated weekly instance for a (category, bracket, period)."""

    __tablename__ = "weeklies"
    __table_args__ = (
        UniqueConstraint(
            "category_key", "bracket_key", "period_start",
            name="uq_weeklies_category_bracket_period",
        ),
        Index(
            "ix_weeklies_category_bracket_period",
            "category_key", "bracket_key", "period_start",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    category_key: Mapped[str] = mapped_column(String(64), nullable=False)
    bracket_key: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_forced: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    def __repr__(self) -> str:
        return f"<Weekly {self.category_key}/{self.bracket_key} {self.period_start}>"


class WeeklyFumen(Base):
    """One chart selected into a weekly, with frozen display metadata."""

    __tablename__ = "weekly_fumens"
    __table_args__ = (
        Index("ix_weekly_fumens_weekly_id", "weekly_id"),
        Index("ix_weekly_fumens_fumen_id", "fumen_id"),
    )

    weekly_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weeklies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    fumen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fumens.fumen_id", ondelete="CASCADE"),
        nullable=False,
    )
    table_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("difficulty_tables.id", ondelete="SET NULL"),
        nullable=True,
    )
    level: Mapped[str] = mapped_column(Text, nullable=False)
    table_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def __repr__(self) -> str:
        return f"<WeeklyFumen weekly={self.weekly_id} slot={self.slot} fumen={self.fumen_id}>"
