"""Discord OAuth2-based authentication backend for sqladmin."""
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse


class DiscordAdminAuth(AuthenticationBackend):
    """Delegates authentication entirely to Discord OAuth2.

    The actual session write happens in the Discord callback handler
    (``/auth/discord/callback?state=admin_panel``).  This backend only
    checks whether the session cookie already carries a validated admin
    user ID, and redirects to Discord if not.

    ``self.middlewares`` is intentionally cleared: the parent class adds its
    own ``SessionMiddleware`` for the sqladmin internal Starlette app, but
    that would create a second, separate session cookie that never receives
    the admin_user_id written by our callback.  By clearing it we let the
    single ``SessionMiddleware`` on the FastAPI app (added in main.py) handle
    all session state consistently across both ``/auth/discord/callback`` and
    ``/admin/*``.
    """

    def __init__(self, secret_key: str) -> None:
        super().__init__(secret_key=secret_key)
        # Disable sqladmin's own SessionMiddleware — see docstring above.
        self.middlewares = []

    async def login(self, request: Request) -> bool:
        # Login is handled externally via Discord OAuth — nothing to do here.
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool | RedirectResponse:
        if not request.session.get("admin_user_id"):
            return RedirectResponse(
                url="/auth/discord/login?state=admin_panel", status_code=302
            )
        return True
