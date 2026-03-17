"""User profile CRUD endpoints."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import OAuthAccount, User
from app.schemas import MessageResponse

router = APIRouter(prefix="/users", tags=["users"])

AVATAR_DIR = Path("/app/uploads/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB


class UserRead(BaseModel):
    id: str
    username: str
    is_active: bool
    is_public: bool
    avatar_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class UserPublicRead(BaseModel):
    id: str
    username: str
    is_public: bool
    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    username: str | None = None
    is_public: bool | None = None


class OAuthAccountRead(BaseModel):
    id: int
    provider: str
    provider_username: str | None
    model_config = ConfigDict(from_attributes=True)


async def _resolve_avatar(user: User, db: AsyncSession) -> str | None:
    """Return custom avatar if set, otherwise Discord avatar from OAuth account."""
    if user.avatar_url:
        return user.avatar_url
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == "discord",
        )
    )
    oauth = result.scalar_one_or_none()
    return oauth.discord_avatar_url if oauth else None


@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Get current user's profile."""
    return UserRead(
        id=str(current_user.id),
        username=current_user.username,
        is_active=current_user.is_active,
        is_public=current_user.is_public,
        avatar_url=await _resolve_avatar(current_user, db),
    )


@router.patch("/me")
async def update_my_profile(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Update current user's profile."""
    if update_data.username is not None:
        result = await db.execute(
            select(User).where(User.username == update_data.username, User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        current_user.username = update_data.username

    if update_data.is_public is not None:
        current_user.is_public = update_data.is_public

    await db.commit()
    await db.refresh(current_user)

    return UserRead(
        id=str(current_user.id),
        username=current_user.username,
        is_active=current_user.is_active,
        is_public=current_user.is_public,
        avatar_url=await _resolve_avatar(current_user, db),
    )


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Upload a custom profile avatar (JPEG/PNG/WebP/GIF, max 5 MB)."""
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Use JPEG, PNG, WebP, or GIF.",
        )

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB.",
        )

    ext = (file.filename or "avatar").rsplit(".", 1)[-1].lower()
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    dest = AVATAR_DIR / filename
    dest.write_bytes(contents)

    current_user.avatar_url = f"/uploads/avatars/{filename}"
    await db.commit()
    await db.refresh(current_user)

    return UserRead(
        id=str(current_user.id),
        username=current_user.username,
        is_active=current_user.is_active,
        is_public=current_user.is_public,
        avatar_url=current_user.avatar_url,
    )


@router.get("/me/oauth")
async def get_my_oauth_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OAuthAccountRead]:
    """Get current user's connected OAuth accounts."""
    result = await db.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()
    return [
        OAuthAccountRead(
            id=account.id,
            provider=account.provider,
            provider_username=account.provider_username,
        )
        for account in accounts
    ]


@router.get("/{username}")
async def get_user_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
) -> UserPublicRead:
    """Get a user's public profile."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User profile is private",
        )

    return UserPublicRead(
        id=str(user.id),
        username=user.username,
        is_public=user.is_public,
    )
