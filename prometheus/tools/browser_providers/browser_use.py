"""Browser-use cloud browser provider."""

import contextlib
import logging
import os

from .base import CloudBrowserProvider

logger = logging.getLogger(__name__)


class BrowserUseProvider(CloudBrowserProvider):
    """Browser-use cloud browser provider.

    Browser-use provides AI-powered web browsing capabilities.
    See https://browser-use.com
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("BROWSERUSE_API_KEY", "")
        self._endpoint = os.environ.get("BROWSERUSE_ENDPOINT", "https://api.browser-use.com")
        self._debug_mode = os.environ.get("BROWSERUSE_DEBUG", "").lower() in ("1", "true", "yes")

    def provider_name(self) -> str:
        return "browser-use"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_error_message(self) -> str | None:
        if not self._api_key:
            return "BROWSERUSE_API_KEY environment variable is not set"
        return None

    def create_session(self, task_id: str) -> dict[str, object]:
        """Create a Browser-use browser session."""
        import uuid

        try:
            import requests
        except ImportError:
            logger.error("requests library is required for Browser-use")
            return self._create_fallback_session(task_id)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "session_id": f"prometheus-{task_id}-{uuid.uuid4().hex[:8]}",
            "headless": True,
            "debug": self._debug_mode,
        }

        try:
            response = requests.post(
                f"{self._endpoint}/v1/sessions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "session_name": data.get("session_id", ""),
                "bb_session_id": data.get("session_id", ""),
                "cdp_url": data.get("cdp_url", ""),
                "features": {"headless": True, "debug": self._debug_mode},
            }
        except Exception as e:
            logger.error(f"Failed to create Browser-use session: {e}")
            return self._create_fallback_session(task_id)

    def _create_fallback_session(self, task_id: str) -> dict[str, object]:
        """Create a fallback session when Browser-use API is unavailable."""
        import uuid

        fallback_id = f"fallback-{task_id}-{uuid.uuid4().hex[:8]}"
        return {
            "session_name": fallback_id,
            "bb_session_id": fallback_id,
            "cdp_url": "",
            "features": {"headless": True},
        }

    def close_session(self, session_id: str) -> bool:
        """Close a Browser-use session."""
        if not self._api_key:
            return False

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self._api_key}",
            }

            response = requests.delete(
                f"{self._endpoint}/v1/sessions/{session_id}",
                headers=headers,
                timeout=10,
            )
            return response.status_code in (200, 204, 404)
        except Exception as e:
            logger.warning(f"Failed to close Browser-use session: {e}")
            return False

    def emergency_cleanup(self, session_id: str) -> None:
        """Best-effort cleanup during process exit."""
        with contextlib.suppress(Exception):
            self.close_session(session_id)
