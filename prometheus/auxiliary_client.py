from __future__ import annotations

import os
import logging
from typing import Any

from openai import OpenAI

from prometheus.config import PrometheusConfig

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15
_DEFAULT_MODEL = "gpt-4o-mini"


class AuxiliaryClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url or ""
        self._timeout = timeout
        self._client: OpenAI | None = None

    def _ensure_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        api_key = self._api_key
        base_url = self._base_url
        if not api_key or not base_url:
            try:
                cfg = PrometheusConfig.load()
                cfg_dict = cfg.to_dict()
                api_cfg = cfg_dict.get("api", {})
                if not api_key:
                    api_key = api_cfg.get("key", "") or os.getenv("OPENAI_API_KEY", "")
                if not base_url:
                    base_url = api_cfg.get("base_url", "https://api.openai.com/v1")
            except Exception:
                if not api_key:
                    api_key = os.getenv("OPENAI_API_KEY", "")
                if not base_url:
                    base_url = "https://api.openai.com/v1"
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=self._timeout,
        )
        return self._client

    def generate_title(self, messages: list[dict[str, str]]) -> str:
        client = self._ensure_client()
        prompt_parts: list[str] = []
        for msg in messages[:6]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                prompt_parts.append(f"{role}: {content[:200]}")
        conversation_text = "\n".join(prompt_parts)
        try:
            response = client.chat.completions.create(
                model=_DEFAULT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Generate a concise 3-6 word title for this conversation. Return ONLY the title, nothing else.",
                    },
                    {"role": "user", "content": conversation_text},
                ],
                max_tokens=30,
                temperature=0.5,
            )
            title = response.choices[0].message.content or ""
            return title.strip().strip('"').strip("'")
        except Exception as e:
            logger.warning("AuxiliaryClient.generate_title failed: %s", e)
            return ""

    def check_moderation(self, text: str) -> dict[str, Any]:
        client = self._ensure_client()
        try:
            response = client.moderations.create(input=text)
            result = response.results[0]
            return {
                "flagged": result.flagged,
                "categories": {
                    cat: getattr(result.categories, cat, False)
                    for cat in (
                        "harassment",
                        "harassment_threatening",
                        "hate",
                        "hate_threatening",
                        "self_harm",
                        "self_harm_instructions",
                        "self_harm_intent",
                        "sexual",
                        "sexual_minors",
                        "violence",
                        "violence_graphic",
                    )
                },
                "category_scores": {
                    cat: float(getattr(result.category_scores, cat, 0.0))
                    for cat in (
                        "harassment",
                        "harassment_threatening",
                        "hate",
                        "hate_threatening",
                        "self_harm",
                        "self_harm_instructions",
                        "self_harm_intent",
                        "sexual",
                        "sexual_minors",
                        "violence",
                        "violence_graphic",
                    )
                },
            }
        except Exception as e:
            logger.warning("AuxiliaryClient.check_moderation failed: %s", e)
            return {"flagged": False, "categories": {}, "category_scores": {}, "error": str(e)}

    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        chars_per_token = 4.0
        cjk_chars = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        non_cjk_len = len(text) - cjk_chars
        estimated = int(non_cjk_len / chars_per_token + cjk_chars / 1.5) + 1
        return estimated
