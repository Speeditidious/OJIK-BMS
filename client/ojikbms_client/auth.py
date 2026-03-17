"""Authentication management for the OJIK agent."""
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import keyring

KEYRING_SERVICE = "ojikbms-client"
ACCESS_TOKEN_KEY = "access_token"
REFRESH_TOKEN_KEY = "refresh_token"


def save_tokens(access_token: str, refresh_token: str) -> None:
    """Save tokens to the system keychain."""
    keyring.set_password(KEYRING_SERVICE, ACCESS_TOKEN_KEY, access_token)
    keyring.set_password(KEYRING_SERVICE, REFRESH_TOKEN_KEY, refresh_token)


def load_access_token() -> str | None:
    """Load access token from system keychain."""
    return keyring.get_password(KEYRING_SERVICE, ACCESS_TOKEN_KEY)


def load_refresh_token() -> str | None:
    """Load refresh token from system keychain."""
    return keyring.get_password(KEYRING_SERVICE, REFRESH_TOKEN_KEY)


def clear_tokens() -> None:
    """Remove tokens from system keychain."""
    try:
        keyring.delete_password(KEYRING_SERVICE, ACCESS_TOKEN_KEY)
    except keyring.errors.PasswordDeleteError:
        pass
    try:
        keyring.delete_password(KEYRING_SERVICE, REFRESH_TOKEN_KEY)
    except keyring.errors.PasswordDeleteError:
        pass


def is_logged_in() -> bool:
    """Check if a token exists in the keychain."""
    return load_access_token() is not None


async def refresh_access_token(api_url: str) -> bool:
    """
    Attempt to refresh the access token using the refresh token.

    Returns:
        True if refresh succeeded, False otherwise.
    """
    refresh_token = load_refresh_token()
    if not refresh_token:
        return False

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{api_url}/auth/refresh",
                json={"refresh_token": refresh_token},
                timeout=10.0,
            )

            if response.status_code != 200:
                clear_tokens()
                return False

            data = response.json()
            save_tokens(data["access_token"], data["refresh_token"])
            return True

        except httpx.RequestError:
            return False


async def make_authenticated_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    api_url: str,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make an authenticated HTTP request, refreshing the token if needed.

    Args:
        client: httpx.AsyncClient instance.
        method: HTTP method (GET, POST, etc.).
        url: Full URL to request.
        api_url: Base API URL for token refresh.
        **kwargs: Additional kwargs passed to the request.

    Returns:
        httpx.Response
    """
    token = load_access_token()
    if token:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        kwargs["headers"] = headers

    response = await client.request(method, url, **kwargs)

    # Attempt token refresh on 401
    if response.status_code == 401:
        refreshed = await refresh_access_token(api_url)
        if refreshed:
            token = load_access_token()
            headers = kwargs.get("headers", {})
            headers["Authorization"] = f"Bearer {token}"
            kwargs["headers"] = headers
            response = await client.request(method, url, **kwargs)

    return response


def get_discord_login_url(api_url: str, state: str | None = None) -> str:
    """Get the Discord login URL, optionally with a state parameter."""
    url = f"{api_url}/auth/discord/login"
    if state:
        url += f"?state={state}"
    return url


def find_free_port() -> int:
    """Find an available local TCP port."""
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_oauth_callback(port: int, timeout: int = 120) -> dict | None:
    """Start a local HTTP server and capture OAuth tokens from the callback redirect.

    Args:
        port: Local port to listen on.
        timeout: Seconds to wait before giving up.

    Returns:
        Dict with 'access_token' and 'refresh_token', or None on timeout/error.
    """
    result: dict | None = None
    event = threading.Event()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            nonlocal result
            params = parse_qs(urlparse(self.path).query)
            if "access_token" in params and "refresh_token" in params:
                result = {
                    "access_token": params["access_token"][0],
                    "refresh_token": params["refresh_token"][0],
                }
                body = (
                    "<html><body><h2>OJIK BMS: 로그인 성공!</h2>"
                    "<p>이 창을 닫고 터미널로 돌아가세요.</p></body></html>"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(400)
                self.end_headers()
            event.set()

        def log_message(self, *args: Any) -> None:  # type: ignore[override]
            pass

    server = HTTPServer(("localhost", port), _Handler)
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()
    event.wait(timeout=timeout)
    server.server_close()
    return result
