import uuid

from sqlalchemy import (
    Boolean,
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


class DifficultyTable(Base, TimestampMixin):
    __tablename__ = "difficulty_tables"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_difficulty_tables_source_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level_order: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<DifficultyTable id={self.id} name={self.name}>"


class UserFavoriteDifficultyTable(Base):
    __tablename__ = "user_favorite_difficulty_tables"
    __table_args__ = (
        UniqueConstraint("user_id", "table_id", name="uq_user_favorite_difficulty_tables"),
    )

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
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<UserFavoriteDifficultyTable user={self.user_id} table={self.table_id}>"


class CustomDifficultyTable(Base, TimestampMixin):
    __tablename__ = "custom_difficulty_tables"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    levels: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<CustomDifficultyTable id={self.id} name={self.name}>"


class CustomCourse(Base, TimestampMixin):
    __tablename__ = "custom_courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    song_list: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    course_file_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<CustomCourse id={self.id} name={self.name}>"
