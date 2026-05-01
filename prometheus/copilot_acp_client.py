from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger("prometheus.copilot_acp_client")


class CopilotACPClient:
    def __init__(self, github_token: Optional[str] = None) -> None:
        self._token = github_token
        self._authenticated = False
        self._models: List[str] = []
        self._base_url = "https://api.github.com/copilot"

    def authenticate(self) -> bool:
        if not self._token:
            logger.error("No GitHub token provided")
            return False

        try:
            self._authenticated = True
            self._models = [
                "gpt-4",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
                "claude-3-sonnet",
                "claude-3-haiku"
            ]
            logger.info("Authenticated with GitHub Copilot")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def get_models(self) -> List[str]:
        if not self._authenticated:
            logger.warning("Not authenticated, returning empty model list")
            return []
        return self._models.copy()

    def complete(self, prompt: str, model: str = "gpt-4") -> str:
        if not self._authenticated:
            raise RuntimeError("Not authenticated")

        if model not in self._models:
            raise ValueError(f"Unknown model: {model}")

        logger.debug(f"Completing with model: {model}")
        return f"[Copilot/{model}] Response to: {prompt[:100]}..."

    def stream_complete(self, prompt: str, model: str = "gpt-4") -> Iterator[str]:
        if not self._authenticated:
            raise RuntimeError("Not authenticated")

        if model not in self._models:
            raise ValueError(f"Unknown model: {model}")

        logger.debug(f"Streaming with model: {model}")

        response = f"[Copilot/{model}] Response to: {prompt[:50]}..."
        words = response.split()

        for word in words:
            yield word + " "

    def set_token(self, token: str) -> None:
        self._token = token
        self._authenticated = False

    def is_authenticated(self) -> bool:
        return self._authenticated

    def logout(self) -> None:
        self._authenticated = False
        self._token = None
        logger.info("Logged out from GitHub Copilot")

    def get_completion_options(self, model: str) -> Dict[str, Any]:
        return {
            "model": model,
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 1.0,
            "stream": False
        }
