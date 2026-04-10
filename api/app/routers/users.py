"""User profile CRUD endpoints."""
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, verify_delete_token
from app.models.user import OAuthAccount, User

router = APIRouter(prefix="/users", tags=["users"])

AVATAR_DIR = Path(settings.UPLOADS_DIR) / "avatars"
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB


class UserRead(BaseModel):
    id: str
    username: str
    bio: str | None = None
    is_active: bool
    avatar_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class UserPublicRead(BaseModel):
    id: str
    username: str
    bio: str | None = None
    avatar_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    username: str | None = None
    bio: str | None = None


class OAuthAccountRead(BaseModel):
    provider: str
    provider_username: str | None
    model_config = ConfigDict(from_attributes=True)


class DeleteAccountRequest(BaseModel):
    verification_token: str
    confirmation_text: str


EXPECTED_CONFIRMATION = "Yes, I want to delete my OJIK BMS account"


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


async def _delete_all_user_data(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Delete all data associated with a user. Must be called within a transaction."""
    from app.models.difficulty_table import (
        CustomCourse,
        CustomDifficultyTable,
        UserFavoriteDifficultyTable,
    )
    from app.models.fumen import UserFumenTag
    from app.models.schedule import Schedule
    from app.models.score import UserPlayerStats, UserScore

    uid = user_id

    await db.execute(delete(UserScore).where(UserScore.user_id == uid))
    await db.execute(delete(UserPlayerStats).where(UserPlayerStats.user_id == uid))
    await db.execute(delete(UserFumenTag).where(UserFumenTag.user_id == uid))
    await db.execute(delete(UserFavoriteDifficultyTable).where(UserFavoriteDifficultyTable.user_id == uid))
    await db.execute(delete(CustomCourse).where(CustomCourse.owner_id == uid))
    await db.execute(delete(CustomDifficultyTable).where(CustomDifficultyTable.owner_id == uid))
    await db.execute(delete(Schedule).where(Schedule.user_id == uid))
    # users row (oauth_accounts cascade-deleted automatically)
    await db.execute(delete(User).where(User.id == uid))

    await db.commit()


@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Get current user's profile."""
    return UserRead(
        id=str(current_user.id),
        username=current_user.username,
        bio=current_user.bio,
        is_active=current_user.is_active,
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

    if update_data.bio is not None:
        current_user.bio = update_data.bio.strip() or None

    await db.commit()
    await db.refresh(current_user)

    return UserRead(
        id=str(current_user.id),
        username=current_user.username,
        bio=current_user.bio,
        is_active=current_user.is_active,
        avatar_url=await _resolve_avatar(current_user, db),
    )


@router.delete("/me")
async def delete_my_account(
    body: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Permanently delete the current user's account and all associated data.

    Requires:
    1. Active JWT (already authenticated)
    2. Discord re-auth token (issued within 5 minutes)
    3. Exact confirmation text
    """
    if body.confirmation_text != EXPECTED_CONFIRMATION:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmation text does not match")

    discord_id = verify_delete_token(body.verification_token)

    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == current_user.id,
            OAuthAccount.provider == "discord",
        )
    )
    oauth = result.scalar_one_or_none()
    if not oauth or oauth.provider_account_id != discord_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Discord account mismatch")

    await _delete_all_user_data(db, current_user.id)
    return {"message": "Account deleted successfully"}


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
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    dest = AVATAR_DIR / filename
    dest.write_bytes(contents)

    current_user.avatar_url = f"/uploads/avatars/{filename}"
    await db.commit()
    await db.refresh(current_user)

    return UserRead(
        id=str(current_user.id),
        username=current_user.username,
        bio=current_user.bio,
        is_active=current_user.is_active,
        avatar_url=current_user.avatar_url,
    )


class PreferencesUpdateRequest(BaseModel):
    preferences: dict[str, Any]


@router.get("/me/preferences")
async def get_my_preferences(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current user's stored preferences."""
    return {"preferences": current_user.preferences or {}}


@router.patch("/me/preferences")
async def update_my_preferences(
    request: PreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Partially update current user's preferences (shallow merge with existing)."""
    existing = current_user.preferences or {}
    current_user.preferences = {**existing, **request.preferences}
    db.add(current_user)
    await db.commit()
    return {"preferences": current_user.preferences}


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
            provider=account.provider,
            provider_username=account.provider_username,
        )
        for account in accounts
    ]


@router.get("/by-id/{user_id}")
async def get_user_profile_by_id(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> UserPublicRead:
    """Get a user's public profile by UUID."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserPublicRead(
        id=str(user.id),
        username=user.username,
        bio=user.bio,
        avatar_url=await _resolve_avatar(user, db),
    )


@router.get("/{username}")
async def get_user_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
) -> UserPublicRead:
    """Get a user's public profile by username."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserPublicRead(
        id=str(user.id),
        username=user.username,
        bio=user.bio,
        avatar_url=await _resolve_avatar(user, db),
    )
