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
from app.schemas import MessageResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"


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

    from app.models.user import OAuthAccount, User

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
    discord_avatar_url = (
        f"https://cdn.discordapp.com/avatars/{discord_id}/{discord_avatar_hash}.png"
        if discord_avatar_hash
        else None
    )

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
        user = User(username=discord_username, is_active=True, is_public=True)
        db.add(user)
        await db.flush()

        oauth_account = OAuthAccount(
            user_id=user.id,
            provider="discord",
            provider_account_id=discord_id,
            provider_username=discord_username,
            discord_avatar_url=discord_avatar_url,
        )
        db.add(oauth_account)

        # Add all default difficulty tables to favorites
        from app.models.table import DifficultyTable, UserFavoriteTable

        default_tables_result = await db.execute(
            select(DifficultyTable)
            .where(DifficultyTable.is_default.is_(True))
            .order_by(DifficultyTable.id)
        )
        for order, table in enumerate(default_tables_result.scalars().all()):
            db.add(UserFavoriteTable(user_id=user.id, table_id=table.id, display_order=order))

        await db.commit()
    else:
        # Update provider username and avatar if changed
        oauth_account.provider_username = discord_username
        if discord_avatar_url:
            oauth_account.discord_avatar_url = discord_avatar_url
        # Load user separately to avoid async lazy-load
        user_result = await db.execute(select(User).where(User.id == oauth_account.user_id))
        user = user_result.scalar_one()

        # Ensure default tables are favorited — handles accounts created before
        # the auto-favorite logic was introduced (one-time idempotent init).
        from app.models.table import DifficultyTable, UserFavoriteTable

        existing_fav = await db.execute(
            select(UserFavoriteTable).where(UserFavoriteTable.user_id == user.id).limit(1)
        )
        if existing_fav.scalar_one_or_none() is None:
            default_tables_result = await db.execute(
                select(DifficultyTable)
                .where(DifficultyTable.is_default.is_(True))
                .order_by(DifficultyTable.id)
            )
            for order, table in enumerate(default_tables_result.scalars().all()):
                db.add(UserFavoriteTable(user_id=user.id, table_id=table.id, display_order=order))

        await db.commit()

    if not user.is_active:
        error_params = urllib.parse.urlencode({"error": "account_banned"})
        redirect_base = _resolve_redirect_base(state, settings.FRONTEND_URL)
        return RedirectResponse(
            url=f"{redirect_base}?{error_params}",
            status_code=302,
        )

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
