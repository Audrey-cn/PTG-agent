from __future__ import annotations

"""Firecrawl web scraping provider."""

import contextlib
import logging
import os

from .base import CloudBrowserProvider

logger = logging.getLogger(__name__)


class FirecrawlProvider(CloudBrowserProvider):
    """Firecrawl web scraping and crawling provider.

    Firecrawl provides web scraping and content extraction services.
    See https://firecrawl.dev
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        self._endpoint = os.environ.get("FIRECRAWL_ENDPOINT", "https://api.firecrawl.dev")
        self._debug_mode = os.environ.get("FIRECRAWL_DEBUG", "").lower() in ("1", "true", "yes")

    def provider_name(self) -> str:
        return "firecrawl"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_error_message(self) -> str | None:
        if not self._api_key:
            return "FIRECRAWL_API_KEY environment variable is not set"
        return None

    def create_session(self, task_id: str) -> dict[str, object]:
        """Create a Firecrawl scraping session.

        Note: Firecrawl is primarily a scraping service, not a full browser.
        This implementation creates a lightweight scraping context.
        """
        import uuid

        session_id = f"prometheus-{task_id}-{uuid.uuid4().hex[:8]}"

        try:
            import requests
        except ImportError:
            logger.error("requests library is required for Firecrawl")
            return self._create_fallback_session(task_id)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "id": session_id,
            "headless": True,
            "debug": self._debug_mode,
        }

        try:
            response = requests.post(
                f"{self._endpoint}/v0/sessions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "session_name": data.get("id", session_id),
                "bb_session_id": data.get("id", session_id),
                "cdp_url": data.get("cdp_url", ""),
                "features": {"headless": True, "debug": self._debug_mode},
            }
        except Exception as e:
            logger.error(f"Failed to create Firecrawl session: {e}")
            return self._create_fallback_session(task_id)

    def _create_fallback_session(self, task_id: str) -> dict[str, object]:
        """Create a fallback session when Firecrawl API is unavailable."""
        import uuid

        fallback_id = f"fallback-{task_id}-{uuid.uuid4().hex[:8]}"
        return {
            "session_name": fallback_id,
            "bb_session_id": fallback_id,
            "cdp_url": "",
            "features": {"headless": True},
        }

    def close_session(self, session_id: str) -> bool:
        """Close a Firecrawl session."""
        if not self._api_key:
            return False

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self._api_key}",
            }

            response = requests.delete(
                f"{self._endpoint}/v0/sessions/{session_id}",
                headers=headers,
                timeout=10,
            )
            return response.status_code in (200, 204, 404)
        except Exception as e:
            logger.warning(f"Failed to close Firecrawl session: {e}")
            return False

    def emergency_cleanup(self, session_id: str) -> None:
        """Best-effort cleanup during process exit."""
        with contextlib.suppress(Exception):
            self.close_session(session_id)
