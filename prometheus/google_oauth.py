from __future__ import annotations

import http.server
import logging
import threading
import urllib.parse
import webbrowser
from typing import Any

logger = logging.getLogger("prometheus.google_oauth")

HTTPX_AVAILABLE = False
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    pass

GOOGLE_AUTH_AVAILABLE = False
try:
    from google.auth.transport.requests import Request as GoogleRequest

    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    pass


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    auth_code: str | None = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful! You can close this tab.</h1>")
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization failed.</h1>")

    def log_message(self, format: str, *args: Any) -> None:
        pass


class GoogleOAuth:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_port: int = 8089,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_port = redirect_port
        self._redirect_uri = f"http://localhost:{redirect_port}"

    def start_flow(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        scopes: list[str] | None = None,
    ) -> str:
        cid = client_id or self._client_id
        if cid is None:
            raise ValueError("client_id is required")

        if client_secret:
            self._client_secret = client_secret
        self._client_id = cid

        if scopes is None:
            scopes = ["openid", "email", "profile"]

        params = {
            "client_id": cid,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
        }

        auth_url = f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"
        webbrowser.open(auth_url)
        return auth_url

    def complete_flow(self, code: str | None = None) -> dict[str, Any]:
        if code is None:
            code = self._wait_for_callback()
            if code is None:
                raise RuntimeError("Failed to receive authorization code from callback")

        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx is required for GoogleOAuth token exchange")

        payload = {
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_uri,
            "grant_type": "authorization_code",
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(self.TOKEN_URL, data=payload)
            resp.raise_for_status()
            return resp.json()

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx is required for GoogleOAuth token refresh")

        payload = {
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(self.TOKEN_URL, data=payload)
            resp.raise_for_status()
            return resp.json()

    def _wait_for_callback(self, timeout: int = 120) -> str | None:
        _OAuthCallbackHandler.auth_code = None
        server = http.server.HTTPServer(("localhost", self._redirect_port), _OAuthCallbackHandler)
        server.timeout = timeout

        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        server.server_close()

        return _OAuthCallbackHandler.auth_code
