"""Chatbot SSE endpoints."""
import asyncio
import json
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.models.chatbot import ChatbotConversation, ChatbotMessage, ChatbotUsageLimit
from app.models.user import User
from app.schemas import MessageResponse

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

DAILY_REQUEST_LIMIT = 50
DAILY_TOKEN_LIMIT = 100_000


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ConversationRead(BaseModel):
    id: str
    user_id: str | None
    summary: str | None


async def _check_usage_limit(
    user: User,
    db: AsyncSession,
) -> None:
    """Check and enforce daily usage limits."""
    from datetime import date
    today = date.today()

    result = await db.execute(
        select(ChatbotUsageLimit).where(
            ChatbotUsageLimit.user_id == user.id,
            ChatbotUsageLimit.date == today,
        )
    )
    limit_record = result.scalar_one_or_none()

    if limit_record and limit_record.request_count >= DAILY_REQUEST_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily request limit of {DAILY_REQUEST_LIMIT} reached",
        )


async def _sse_generator(
    user_message: str,
    conversation_id: str,
    user: User | None,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for the chatbot response."""
    # Placeholder: In production, this calls the LLM service
    placeholder_response = (
        "안녕하세요! OJIK BMS 챗봇입니다. "
        "현재 LLM 서비스가 설정되지 않았습니다. "
        "OPENAI_API_KEY 또는 ANTHROPIC_API_KEY를 설정해주세요."
    )

    # Stream token by token
    for char in placeholder_response:
        yield f"data: {json.dumps({'type': 'token', 'content': char})}\n\n"
        await asyncio.sleep(0.02)

    yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"


@router.post("/conversations", response_model=ConversationRead)
async def create_conversation(
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    """Create a new chatbot conversation."""
    conversation = ChatbotConversation(
        user_id=current_user.id if current_user else None,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return ConversationRead(
        id=str(conversation.id),
        user_id=str(conversation.user_id) if conversation.user_id else None,
        summary=conversation.summary,
    )


@router.get("/conversations", response_model=List[ConversationRead])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ConversationRead]:
    """List current user's conversations."""
    result = await db.execute(
        select(ChatbotConversation)
        .where(ChatbotConversation.user_id == current_user.id)
        .order_by(ChatbotConversation.created_at.desc())
        .limit(50)
    )
    conversations = result.scalars().all()

    return [
        ConversationRead(
            id=str(c.id),
            user_id=str(c.user_id) if c.user_id else None,
            summary=c.summary,
        )
        for c in conversations
    ]


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Send a message and receive a streaming SSE response.
    Returns Server-Sent Events.
    """
    if current_user:
        await _check_usage_limit(current_user, db)

    # Get or create conversation
    conversation_id = payload.conversation_id
    if conversation_id is None:
        conversation = ChatbotConversation(
            user_id=current_user.id if current_user else None,
        )
        db.add(conversation)
        await db.flush()
        conversation_id = str(conversation.id)
    else:
        result = await db.execute(
            select(ChatbotConversation).where(
                ChatbotConversation.id == uuid.UUID(conversation_id)
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

    # Save user message
    user_msg = ChatbotMessage(
        conversation_id=uuid.UUID(conversation_id),
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    await db.commit()

    return StreamingResponse(
        _sse_generator(payload.message, conversation_id, current_user, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
