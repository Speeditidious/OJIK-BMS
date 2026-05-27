"""Discord OAuth2 authentication endpoints."""
import urllib.parse

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.models.user import OAuthAccount, User
from app.schemas import MessageResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"
USERNAME_MAX_LENGTH = 64


def build_discord_avatar_url(discord_id: str, avatar_hash: str | None) -> str | None:
    """Return the Discord CDN URL for the current avatar hash."""
    if not avatar_hash:
        return None
    ext = "gif" if avatar_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.{ext}"


def _resolve_redirect_base(state: str | None, frontend_url: str) -> str:
    """Resolve the OAuth redirect base URL.

    If state is 'agent:PORT', redirect to local agent callback server.
    Otherwise, redirect to the frontend callback page.
    """
    if state and state.startswith("agent:"):
        port = state.removeprefix("agent:")
        if port.isdigit():
            return f"http://localhost:{port}/callback"
    return f"{frontend_url}/auth/callback"


async def _generate_unique_username(db: AsyncSession, preferred_username: str) -> str:
    """Return an available username based on the OAuth provider username."""
    base = (preferred_username or "user").strip() or "user"
    base = base[:USERNAME_MAX_LENGTH]

    suffix = 1
    while True:
        if suffix == 1:
            candidate = base
        else:
            suffix_text = str(suffix)
            candidate = f"{base[:USERNAME_MAX_LENGTH - len(suffix_text)]}{suffix_text}"

        result = await db.execute(select(User).where(User.username == candidate))
        if result.scalar_one_or_none() is None:
            return candidate

        suffix += 1


@router.get("/discord/login")
async def discord_login(state: str | None = None) -> RedirectResponse:
    """Redirect user to Discord OAuth2 authorization page."""
    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
    }
    if state:
        params["state"] = state
    url = f"{DISCORD_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/discord/callback")
async def discord_callback(
    request: Request,
    code: str,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Discord OAuth2 callback and redirect to frontend with JWT tokens."""
    import httpx

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_response = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": settings.DISCORD_CLIENT_ID,
                "client_secret": settings.DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_response.status_code != 200:
            error_params = urllib.parse.urlencode({"error": "oauth_token_failed"})
            redirect_base = _resolve_redirect_base(state, settings.FRONTEND_URL)
            return RedirectResponse(
                url=f"{redirect_base}?{error_params}",
                status_code=302,
            )

        token_data = token_response.json()
        discord_access_token = token_data["access_token"]

        # Fetch Discord user info
        user_response = await client.get(
            DISCORD_USER_URL,
            headers={"Authorization": f"Bearer {discord_access_token}"},
        )

        if user_response.status_code != 200:
            error_params = urllib.parse.urlencode({"error": "oauth_user_failed"})
            redirect_base = _resolve_redirect_base(state, settings.FRONTEND_URL)
            return RedirectResponse(
                url=f"{redirect_base}?{error_params}",
                status_code=302,
            )

        discord_user = user_response.json()

    discord_id = discord_user["id"]
    discord_username = discord_user.get("username", "")
    discord_avatar_hash = discord_user.get("avatar")
    discord_avatar_url = build_discord_avatar_url(discord_id, discord_avatar_hash)

    # Find or create user
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "discord",
            OAuthAccount.provider_account_id == discord_id,
        )
    )
    oauth_account = result.scalar_one_or_none()

    if oauth_account is None:
        # Create new user
        username = await _generate_unique_username(db, discord_username)
        user = User(username=username, is_active=True)
        db.add(user)
        await db.flush()

        oauth_account = OAuthAccount(
            user_id=user.id,
            provider="discord",
            provider_account_id=discord_id,
            provider_username=discord_username,
            discord_avatar_hash=discord_avatar_hash,
            discord_avatar_url=discord_avatar_url,
        )
        db.add(oauth_account)

        # Add all default difficulty tables to favorites
        from app.models.difficulty_table import (
            DifficultyTable,
            UserFavoriteDifficultyTable,
        )
        from app.services.default_table_order import sort_difficulty_tables

        default_tables_result = await db.execute(
            select(DifficultyTable)
            .where(DifficultyTable.is_default.is_(True))
        )
        default_tables = sort_difficulty_tables(
            list(default_tables_result.scalars().all())
        )
        for order, table in enumerate(default_tables):
            db.add(
                UserFavoriteDifficultyTable(
                    user_id=user.id,
                    table_id=table.id,
                    display_order=order,
                )
            )

        await db.commit()
    else:
        # Update provider username and avatar if changed
        oauth_account.provider_username = discord_username
        oauth_account.discord_avatar_hash = discord_avatar_hash
        oauth_account.discord_avatar_url = discord_avatar_url
        # Load user separately to avoid async lazy-load
        user_result = await db.execute(select(User).where(User.id == oauth_account.user_id))
        user = user_result.scalar_one()

        # Ensure default tables are favorited — handles accounts created before
        # the auto-favorite logic was introduced (one-time idempotent init).
        from app.models.difficulty_table import (
            DifficultyTable,
            UserFavoriteDifficultyTable,
        )
        from app.services.default_table_order import sort_difficulty_tables

        existing_fav = await db.execute(
            select(UserFavoriteDifficultyTable).where(UserFavoriteDifficultyTable.user_id == user.id).limit(1)
        )
        if existing_fav.scalar_one_or_none() is None:
            default_tables_result = await db.execute(
                select(DifficultyTable)
                .where(DifficultyTable.is_default.is_(True))
            )
            default_tables = sort_difficulty_tables(
                list(default_tables_result.scalars().all())
            )
            for order, table in enumerate(default_tables):
                db.add(
                    UserFavoriteDifficultyTable(
                        user_id=user.id,
                        table_id=table.id,
                        display_order=order,
                    )
                )

        await db.commit()

    if not user.is_active:
        error_params = urllib.parse.urlencode({"error": "account_banned"})
        redirect_base = _resolve_redirect_base(state, settings.FRONTEND_URL)
        return RedirectResponse(
            url=f"{redirect_base}?{error_params}",
            status_code=302,
        )

    # Account deletion verification flow: issue a short-lived delete token and redirect to popup callback.
    if state and state.startswith("delete_verify"):
        from app.core.security import create_delete_verification_token

        delete_token = create_delete_verification_token(discord_id)
        if state == "delete_verify_redirect":
            # Fallback: popup was blocked, redirect back to settings page
            redirect_url = (
                f"{settings.FRONTEND_URL}/settings?tab=account&delete_token={delete_token}"
            )
        else:
            redirect_url = f"{settings.FRONTEND_URL}/auth/delete-callback?token={delete_token}"
        return RedirectResponse(url=redirect_url, status_code=302)

    # Admin panel flow: write session and redirect to /admin instead of issuing JWTs.
    if state == "admin_panel":
        if not user.is_admin:
            error_params = urllib.parse.urlencode({"error": "admin_access_denied"})
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth/callback?{error_params}",
                status_code=302,
            )
        request.session["admin_user_id"] = str(user.id)
        return RedirectResponse(url="/admin", status_code=302)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    # Redirect to frontend or agent callback with tokens in query params
    callback_params = urllib.parse.urlencode(
        {"access_token": access_token, "refresh_token": refresh_token}
    )
    redirect_base = _resolve_redirect_base(state, settings.FRONTEND_URL)
    return RedirectResponse(
        url=f"{redirect_base}?{callback_params}",
        status_code=302,
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using a valid refresh token."""
    user_id = verify_token(body.refresh_token, token_type="refresh")

    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout() -> MessageResponse:
    """Logout endpoint (client should discard tokens)."""
    return MessageResponse(message="Successfully logged out")
