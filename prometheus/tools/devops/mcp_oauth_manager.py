#!/usr/bin/env python3
"""Central manager for per-server MCP OAuth state."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _ProviderEntry:
    server_url: str
    oauth_config: dict | None
    provider: Any | None = None
    last_mtime_ns: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending_401: Dict[str, asyncio.Future[bool]] = field(default_factory=dict)


def _make_prometheus_provider_class() -> type | None:
    try:
        from mcp.client.auth.oauth2 import OAuthClientProvider
    except ImportError:
        return None

    class PrometheusMCPOAuthProvider(OAuthClientProvider):
        def __init__(self, *args: Any, server_name: str = "", **kwargs: Any):
            super().__init__(*args, **kwargs)
            self._prometheus_server_name = server_name

        async def _initialize(self) -> None:
            await super()._initialize()
            tokens = self.context.current_tokens
            if tokens is not None and tokens.expires_in is not None:
                self.context.update_token_expiry(tokens)

            if tokens is not None and self.context.oauth_metadata is None:
                try:
                    await self._prefetch_oauth_metadata()
                except Exception as exc:
                    logger.debug(
                        "MCP OAuth '%s': pre-flight metadata discovery failed (non-fatal): %s",
                        self._prometheus_server_name,
                        exc,
                    )

        async def _prefetch_oauth_metadata(self) -> None:
            import httpx
            from mcp.client.auth.utils import (
                build_oauth_authorization_server_metadata_discovery_urls,
                build_protected_resource_metadata_discovery_urls,
                create_oauth_metadata_request,
                handle_auth_metadata_response,
                handle_protected_resource_response,
            )

            server_url = self.context.server_url
            async with httpx.AsyncClient(timeout=10.0) as client:
                for url in build_protected_resource_metadata_discovery_urls(None, server_url):
                    req = create_oauth_metadata_request(url)
                    try:
                        resp = await client.send(req)
                    except httpx.HTTPError as exc:
                        logger.debug(
                            "MCP OAuth '%s': PRM discovery to %s failed: %s",
                            self._prometheus_server_name,
                            url,
                            exc,
                        )
                        continue
                    prm = await handle_protected_resource_response(resp)
                    if prm:
                        self.context.protected_resource_metadata = prm
                        if prm.authorization_servers:
                            self.context.auth_server_url = str(prm.authorization_servers[0])
                        break

                for url in build_oauth_authorization_server_metadata_discovery_urls(
                    self.context.auth_server_url, server_url
                ):
                    req = create_oauth_metadata_request(url)
                    try:
                        resp = await client.send(req)
                    except httpx.HTTPError as exc:
                        logger.debug(
                            "MCP OAuth '%s': ASM discovery to %s failed: %s",
                            self._prometheus_server_name,
                            url,
                            exc,
                        )
                        continue
                    ok, asm = await handle_auth_metadata_response(resp)
                    if not ok:
                        break
                    if asm:
                        self.context.oauth_metadata = asm
                        logger.debug(
                            "MCP OAuth '%s': pre-flight ASM discovered token_endpoint=%s",
                            self._prometheus_server_name,
                            asm.token_endpoint,
                        )
                        break

        async def async_auth_flow(self, request):
            try:
                await get_manager().invalidate_if_disk_changed(self._prometheus_server_name)
            except Exception as exc:
                logger.debug(
                    "MCP OAuth '%s': pre-flow disk-watch failed (non-fatal): %s",
                    self._prometheus_server_name,
                    exc,
                )

            inner = super().async_auth_flow(request)
            try:
                outgoing = await inner.__anext__()
                while True:
                    incoming = yield outgoing
                    outgoing = await inner.asend(incoming)
            except StopAsyncIteration:
                return

    return PrometheusMCPOAuthProvider


_PROMETHEUS_PROVIDER_CLS: type | None = _make_prometheus_provider_class()


class MCPOAuthManager:
    def __init__(self) -> None:
        self._entries: Dict[str, _ProviderEntry] = {}
        self._entries_lock = threading.Lock()

    def get_or_build_provider(
        self,
        server_name: str,
        server_url: str,
        oauth_config: dict | None,
    ) -> Any | None:
        with self._entries_lock:
            entry = self._entries.get(server_name)
            if entry is not None and entry.server_url != server_url:
                logger.info(
                    "MCP OAuth '%s': URL changed from %s to %s, discarding cache",
                    server_name,
                    entry.server_url,
                    server_url,
                )
                entry = None

            if entry is None:
                entry = _ProviderEntry(
                    server_url=server_url,
                    oauth_config=oauth_config,
                )
                self._entries[server_name] = entry

            if entry.provider is None:
                entry.provider = self._build_provider(server_name, entry)

            return entry.provider

    def _build_provider(
        self,
        server_name: str,
        entry: _ProviderEntry,
    ) -> Any | None:
        if _PROMETHEUS_PROVIDER_CLS is None:
            logger.warning(
                "MCP OAuth '%s': SDK auth module unavailable",
                server_name,
            )
            return None

        from prometheus.tools.mcp_oauth import (
            _OAUTH_AVAILABLE,
            PrometheusTokenStorage,
            _build_client_metadata,
            _configure_callback_port,
            _is_interactive,
            _maybe_preregister_client,
            _redirect_handler,
            _wait_for_callback,
        )

        if not _OAUTH_AVAILABLE:
            return None

        cfg = dict(entry.oauth_config or {})
        storage = PrometheusTokenStorage(server_name)

        if not _is_interactive() and not storage.has_cached_tokens():
            logger.warning(
                "MCP OAuth for '%s': non-interactive environment and no "
                "cached tokens found. Run interactively first to complete "
                "initial authorization.",
                server_name,
            )

        _configure_callback_port(cfg)
        client_metadata = _build_client_metadata(cfg)
        _maybe_preregister_client(storage, cfg, client_metadata)

        return _PROMETHEUS_PROVIDER_CLS(
            server_name=server_name,
            server_url=entry.server_url,
            client_metadata=client_metadata,
            storage=storage,
            redirect_handler=_redirect_handler,
            callback_handler=_wait_for_callback,
            timeout=float(cfg.get("timeout", 300)),
        )

    def remove(self, server_name: str) -> None:
        with self._entries_lock:
            self._entries.pop(server_name, None)

        from prometheus.tools.mcp_oauth import remove_oauth_tokens

        remove_oauth_tokens(server_name)
        logger.info(
            "MCP OAuth '%s': evicted from cache and removed from disk",
            server_name,
        )

    async def invalidate_if_disk_changed(self, server_name: str) -> bool:
        from prometheus.tools.mcp_oauth import _get_token_dir, _safe_filename

        entry = self._entries.get(server_name)
        if entry is None or entry.provider is None:
            return False

        async with entry.lock:
            tokens_path = _get_token_dir() / f"{_safe_filename(server_name)}.json"
            try:
                mtime_ns = tokens_path.stat().st_mtime_ns
            except (FileNotFoundError, OSError):
                return False

            if mtime_ns != entry.last_mtime_ns:
                old = entry.last_mtime_ns
                entry.last_mtime_ns = mtime_ns
                if hasattr(entry.provider, "_initialized"):
                    entry.provider._initialized = False
                logger.info(
                    "MCP OAuth '%s': tokens file changed (mtime %d -> %d), forcing reload",
                    server_name,
                    old,
                    mtime_ns,
                )
                return True
            return False

    async def handle_401(
        self,
        server_name: str,
        failed_access_token: str | None = None,
    ) -> bool:
        entry = self._entries.get(server_name)
        if entry is None or entry.provider is None:
            return False

        key = failed_access_token or "<unknown>"
        loop = asyncio.get_running_loop()

        async with entry.lock:
            pending = entry.pending_401.get(key)
            if pending is None:
                pending = loop.create_future()
                entry.pending_401[key] = pending

                async def _do_handle() -> None:
                    try:
                        disk_changed = await self.invalidate_if_disk_changed(server_name)
                        if disk_changed:
                            if not pending.done():
                                pending.set_result(True)
                            return

                        provider = entry.provider
                        ctx = getattr(provider, "context", None)
                        can_refresh = False
                        if ctx is not None:
                            can_refresh_fn = getattr(ctx, "can_refresh_token", None)
                            if callable(can_refresh_fn):
                                try:
                                    can_refresh = bool(can_refresh_fn())
                                except Exception:
                                    can_refresh = False
                        if not pending.done():
                            pending.set_result(can_refresh)
                    except Exception as exc:
                        logger.warning(
                            "MCP OAuth '%s': 401 handler failed: %s",
                            server_name,
                            exc,
                        )
                        if not pending.done():
                            pending.set_result(False)
                    finally:
                        entry.pending_401.pop(key, None)

                asyncio.create_task(_do_handle())

        try:
            return await pending
        except Exception as exc:
            logger.warning(
                "MCP OAuth '%s': awaiting 401 handler failed: %s",
                server_name,
                exc,
            )
            return False


_MANAGER: MCPOAuthManager | None = None
_MANAGER_LOCK = threading.Lock()


def get_manager() -> MCPOAuthManager:
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            _MANAGER = MCPOAuthManager()
        return _MANAGER


def reset_manager_for_tests() -> None:
    global _MANAGER
    with _MANAGER_LOCK:
        _MANAGER = None
