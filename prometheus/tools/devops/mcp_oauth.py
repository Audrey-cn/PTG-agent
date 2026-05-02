from __future__ import annotations

#!/usr/bin/env python3
"""MCP OAuth 2.1 Client Support."""

import asyncio
import contextlib
import json
import logging
import os
import re
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

_OAUTH_AVAILABLE = False
try:
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import (
        OAuthClientInformationFull,
        OAuthClientMetadata,
        OAuthToken,
    )
    from pydantic import AnyUrl

    _OAUTH_AVAILABLE = True
except ImportError:
    logger.debug("MCP OAuth types not available -- OAuth MCP auth disabled")


class OAuthNonInteractiveError(RuntimeError):
    """Raised when OAuth requires browser interaction in a non-interactive env."""


_oauth_port: Optional[int] = None


def _get_token_dir() -> Path:
    """Return the directory for MCP OAuth token files.

    Uses PROMETHEUS_HOME so each profile gets its own OAuth tokens.
    Layout: ``PROMETHEUS_HOME/mcp-tokens/``
    """
    try:
        from prometheus.constants_core import get_prometheus_home

        base = Path(get_prometheus_home())
    except ImportError:
        base = Path(os.environ.get("PROMETHEUS_HOME", str(Path.home() / ".prometheus")))
    return base / "mcp-tokens"


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name).strip("_")[:128] or "default"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _is_interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _can_open_browser() -> bool:
    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
        return False
    if os.name == "nt":
        return True
    try:
        if os.uname().sysname == "Darwin":
            return True
    except AttributeError:
        pass
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.rename(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


class PrometheusTokenStorage:
    """Persist OAuth tokens and client registration to JSON files.

    File layout::

        PROMETHEUS_HOME/mcp-tokens/<server_name>.json         -- tokens
        PROMETHEUS_HOME/mcp-tokens/<server_name>.client.json   -- client info
    """

    def __init__(self, server_name: str):
        self._server_name = _safe_filename(server_name)

    def _tokens_path(self) -> Path:
        return _get_token_dir() / f"{self._server_name}.json"

    def _client_info_path(self) -> Path:
        return _get_token_dir() / f"{self._server_name}.client.json"

    async def get_tokens(self) -> OAuthToken | None:
        data = _read_json(self._tokens_path())
        if data is None:
            return None
        absolute_expiry = data.pop("expires_at", None)
        if absolute_expiry is not None:
            data["expires_in"] = int(max(absolute_expiry - time.time(), 0))
        elif data.get("expires_in") is not None:
            try:
                file_mtime = self._tokens_path().stat().st_mtime
            except OSError:
                file_mtime = None
            if file_mtime is not None:
                try:
                    implied_expiry = file_mtime + int(data["expires_in"])
                    data["expires_in"] = int(max(implied_expiry - time.time(), 0))
                except (TypeError, ValueError):
                    pass
        try:
            return OAuthToken.model_validate(data)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("Corrupt tokens at %s -- ignoring: %s", self._tokens_path(), exc)
            return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        payload = tokens.model_dump(mode="json", exclude_none=True)
        expires_in = payload.get("expires_in")
        if expires_in is not None:
            with contextlib.suppress(TypeError, ValueError):
                payload["expires_at"] = time.time() + int(expires_in)
        _write_json(self._tokens_path(), payload)
        logger.debug("OAuth tokens saved for %s", self._server_name)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        data = _read_json(self._client_info_path())
        if data is None:
            return None
        try:
            return OAuthClientInformationFull.model_validate(data)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "Corrupt client info at %s -- ignoring: %s", self._client_info_path(), exc
            )
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        _write_json(
            self._client_info_path(), client_info.model_dump(mode="json", exclude_none=True)
        )
        logger.debug("OAuth client info saved for %s", self._server_name)

    def remove(self) -> None:
        for p in (self._tokens_path(), self._client_info_path()):
            p.unlink(missing_ok=True)

    def has_cached_tokens(self) -> bool:
        return self._tokens_path().exists()


def _make_callback_handler() -> Tuple[type, dict]:
    result: Dict[str, Any] = {"auth_code": None, "state": None, "error": None}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            params = parse_qs(urlparse(self.path).query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]

            result["auth_code"] = code
            result["state"] = state
            result["error"] = error

            body = (
                (
                    "<html><body><h2>Authorization Successful</h2>"
                    "<p>You can close this tab and return to Prometheus.</p></body></html>"
                )
                if code
                else (
                    "<html><body><h2>Authorization Failed</h2>"
                    f"<p>Error: {error or 'unknown'}</p></body></html>"
                )
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("OAuth callback: %s", fmt % args)

    return _Handler, result


async def _redirect_handler(authorization_url: str) -> None:
    msg = (
        f"\n  MCP OAuth: authorization required.\n"
        f"  Open this URL in your browser:\n\n"
        f"    {authorization_url}\n"
    )
    print(msg, file=sys.stderr)

    if _can_open_browser():
        try:
            opened = webbrowser.open(authorization_url)
            if opened:
                print("  (Browser opened automatically.)\n", file=sys.stderr)
            else:
                print(
                    "  (Could not open browser — please open the URL manually.)\n", file=sys.stderr
                )
        except Exception:
            print("  (Could not open browser — please open the URL manually.)\n", file=sys.stderr)
    else:
        print("  (Headless environment detected — open the URL manually.)\n", file=sys.stderr)


async def _wait_for_callback() -> Tuple[str, str | None]:
    if _oauth_port is None:
        raise RuntimeError(
            "OAuth callback port not set — build_oauth_auth must be called "
            "before _wait_for_oauth_callback"
        )

    handler_cls, result = _make_callback_handler()

    try:
        server = HTTPServer(("127.0.0.1", _oauth_port), handler_cls)
    except OSError:
        raise OAuthNonInteractiveError(
            "OAuth callback timed out — could not bind callback port. "
            "Complete the authorization in a browser first, then retry."
        )

    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    timeout = 300.0
    poll_interval = 0.5
    elapsed = 0.0
    try:
        while elapsed < timeout:
            if result["auth_code"] is not None or result["error"] is not None:
                break
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
    finally:
        server.server_close()

    if result["error"]:
        raise RuntimeError(f"OAuth authorization failed: {result['error']}")
    if result["auth_code"] is None:
        raise OAuthNonInteractiveError(
            "OAuth callback timed out — no authorization code received. "
            "Ensure you completed the browser authorization flow."
        )

    return result["auth_code"], result["state"]


def remove_oauth_tokens(server_name: str) -> None:
    storage = PrometheusTokenStorage(server_name)
    storage.remove()
    logger.info("OAuth tokens removed for '%s'", server_name)


def _configure_callback_port(cfg: dict) -> int:
    global _oauth_port
    requested = int(cfg.get("redirect_port", 0))
    port = _find_free_port() if requested == 0 else requested
    cfg["_resolved_port"] = port
    _oauth_port = port
    return port


def _build_client_metadata(cfg: dict) -> OAuthClientMetadata:
    port = cfg.get("_resolved_port")
    if port is None:
        raise ValueError(
            "_configure_callback_port() must be called before _build_client_metadata()"
        )
    client_name = cfg.get("client_name", "Prometheus Agent")
    scope = cfg.get("scope")
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    metadata_kwargs: Dict[str, Any] = {
        "client_name": client_name,
        "redirect_uris": [AnyUrl(redirect_uri)],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    if scope:
        metadata_kwargs["scope"] = scope
    if cfg.get("client_secret"):
        metadata_kwargs["token_endpoint_auth_method"] = "client_secret_post"

    return OAuthClientMetadata.model_validate(metadata_kwargs)


def _maybe_preregister_client(
    storage: PrometheusTokenStorage,
    cfg: dict,
    client_metadata: OAuthClientMetadata,
) -> None:
    client_id = cfg.get("client_id")
    if not client_id:
        return
    port = cfg["_resolved_port"]
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    info_dict: Dict[str, Any] = {
        "client_id": client_id,
        "redirect_uris": [redirect_uri],
        "grant_types": client_metadata.grant_types,
        "response_types": client_metadata.response_types,
        "token_endpoint_auth_method": client_metadata.token_endpoint_auth_method,
    }
    if cfg.get("client_secret"):
        info_dict["client_secret"] = cfg["client_secret"]
    if cfg.get("client_name"):
        info_dict["client_name"] = cfg["client_name"]
    if cfg.get("scope"):
        info_dict["scope"] = cfg["scope"]

    client_info = OAuthClientInformationFull.model_validate(info_dict)
    _write_json(storage._client_info_path(), client_info.model_dump(mode="json", exclude_none=True))
    logger.debug("Pre-registered client_id=%s for '%s'", client_id, storage._server_name)


def build_oauth_auth(
    server_name: str,
    server_url: str,
    oauth_config: Optional[Dict] = None,
) -> OAuthClientProvider | None:
    if not _OAUTH_AVAILABLE:
        logger.warning(
            "MCP OAuth requested for '%s' but SDK auth types are not available. "
            "Install with: pip install 'mcp>=1.26.0'",
            server_name,
        )
        return None

    cfg = dict(oauth_config or {})
    storage = PrometheusTokenStorage(server_name)

    if not _is_interactive() and not storage.has_cached_tokens():
        logger.warning(
            "MCP OAuth for '%s': non-interactive environment and no cached tokens "
            "found. The OAuth flow requires browser authorization. Run "
            "interactively first to complete the initial authorization, then "
            "cached tokens will be reused.",
            server_name,
        )

    _configure_callback_port(cfg)
    client_metadata = _build_client_metadata(cfg)
    _maybe_preregister_client(storage, cfg, client_metadata)

    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=_redirect_handler,
        callback_handler=_wait_for_callback,
        timeout=float(cfg.get("timeout", 300)),
    )
