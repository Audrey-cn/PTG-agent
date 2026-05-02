from __future__ import annotations

"""Browserbase cloud browser provider."""

import contextlib
import logging
import os

from .base import CloudBrowserProvider

logger = logging.getLogger(__name__)


class BrowserbaseProvider(CloudBrowserProvider):
    """Browserbase cloud browser provider.

    Browserbase provides managed browser instances in the cloud.
    See https://browserbase.com
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("BROWSERBASE_API_KEY", "")
        self._project_id = os.environ.get("BROWSERBASE_PROJECT_ID", "")
        self._debug_mode = os.environ.get("BROWSERBASE_DEBUG", "").lower() in ("1", "true", "yes")

    def provider_name(self) -> str:
        return "browserbase"

    def is_configured(self) -> bool:
        return bool(self._api_key and self._project_id)

    def get_error_message(self) -> str | None:
        if not self._api_key:
            return "BROWSERBASE_API_KEY environment variable is not set"
        if not self._project_id:
            return "BROWSERBASE_PROJECT_ID environment variable is not set"
        return None

    def create_session(self, task_id: str) -> dict[str, object]:
        """Create a Browserbase browser session."""
        import uuid

        try:
            import requests
        except ImportError:
            logger.error("requests library is required for Browserbase")
            return self._create_fallback_session(task_id)

        headers = {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "projectId": self._project_id,
            "sessionName": f"prometheus-{task_id}-{uuid.uuid4().hex[:8]}",
            "features": {
                "headless": True,
                "tls": True,
                "trustAllCerts": True,
                "blockAds": True,
            },
        }

        if self._debug_mode:
            payload["features"]["debugMode"] = True

        try:
            response = requests.post(
                "https://api.browserbase.com/v1/sessions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "session_name": data.get("session", {}).get("name", ""),
                "bb_session_id": data.get("session", {}).get("id", ""),
                "cdp_url": data.get("session", {}).get("cdpWebSocketUrl", ""),
                "features": payload["features"],
            }
        except Exception as e:
            logger.error(f"Failed to create Browserbase session: {e}")
            return self._create_fallback_session(task_id)

    def _create_fallback_session(self, task_id: str) -> dict[str, object]:
        """Create a fallback session when Browserbase API is unavailable."""
        import uuid

        fallback_id = f"fallback-{task_id}-{uuid.uuid4().hex[:8]}"
        return {
            "session_name": fallback_id,
            "bb_session_id": fallback_id,
            "cdp_url": "",
            "features": {"headless": True},
        }

    def close_session(self, session_id: str) -> bool:
        """Close a Browserbase session."""
        if not self._api_key:
            return False

        try:
            import requests

            headers = {
                "Authorization": f"Basic {self._api_key}",
            }

            response = requests.delete(
                f"https://api.browserbase.com/v1/sessions/{session_id}",
                headers=headers,
                timeout=10,
            )
            return response.status_code in (200, 204, 404)
        except Exception as e:
            logger.warning(f"Failed to close Browserbase session: {e}")
            return False

    def emergency_cleanup(self, session_id: str) -> None:
        """Best-effort cleanup during process exit."""
        with contextlib.suppress(Exception):
            self.close_session(session_id)
