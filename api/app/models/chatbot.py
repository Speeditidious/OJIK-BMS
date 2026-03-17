import uuid
from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

try:
    from pgvector.sqlalchemy import Vector
    VECTOR_AVAILABLE = True
except ImportError:
    VECTOR_AVAILABLE = False

from app.models.base import Base


class ChatbotDocument(Base):
    __tablename__ = "chatbot_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pgvector Vector(1536) - using conditional import for portability
    if VECTOR_AVAILABLE:
        embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    else:
        embedding: Mapped[list | None] = mapped_column(nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ChatbotDocument id={self.id} title={self.title}>"


class ChatbotConversation(Base):
    __tablename__ = "chatbot_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ChatbotConversation id={self.id} user={self.user_id}>"


class ChatbotMessage(Base):
    __tablename__ = "chatbot_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatbot_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant / system
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ChatbotMessage id={self.id} role={self.role}>"


class ChatbotUsageLimit(Base):
    __tablename__ = "chatbot_usage_limits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<ChatbotUsageLimit user={self.user_id} date={self.date}>"
