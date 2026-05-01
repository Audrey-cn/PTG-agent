from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("prometheus.image_gen_provider")

OPENAI_AVAILABLE = False
try:
    import httpx

    OPENAI_AVAILABLE = True
except ImportError:
    pass


class ImageGenProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, size: str = "1024x1024", **kwargs: Any) -> str: ...


class OpenAIImageProvider(ImageGenProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def generate(self, prompt: str, size: str = "1024x1024", **kwargs: Any) -> str:
        if not OPENAI_AVAILABLE:
            raise RuntimeError("httpx is required for OpenAIImageProvider")

        model = kwargs.get("model", "gpt-image-1")
        quality = kwargs.get("quality", "standard")
        n = kwargs.get("n", 1)
        response_format = kwargs.get("response_format", "url")

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": n,
            "response_format": response_format,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/images/generations",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        images = data.get("data", [])
        if not images:
            raise ValueError("No images returned from OpenAI API")

        first = images[0]
        if "url" in first:
            return first["url"]
        if "b64_json" in first:
            return first["b64_json"]

        raise ValueError("Unexpected response format from OpenAI API")


class XAIImageProvider(ImageGenProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.x.ai/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def generate(self, prompt: str, size: str = "1024x1024", **kwargs: Any) -> str:
        if not OPENAI_AVAILABLE:
            raise RuntimeError("httpx is required for XAIImageProvider")

        model = kwargs.get("model", "grok-2-image")
        n = kwargs.get("n", 1)
        response_format = kwargs.get("response_format", "url")

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": n,
            "response_format": response_format,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/images/generations",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        images = data.get("data", [])
        if not images:
            raise ValueError("No images returned from xAI API")

        first = images[0]
        if "url" in first:
            return first["url"]
        if "b64_json" in first:
            return first["b64_json"]

        raise ValueError("Unexpected response format from xAI API")


class DeepSeekImageProvider(ImageGenProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def generate(self, prompt: str, size: str = "1024x1024", **kwargs: Any) -> str:
        raise NotImplementedError("DeepSeek image generation is not yet available")


def create_image_provider(
    provider: str,
    api_key: str,
    base_url: str | None = None,
) -> ImageGenProvider:
    providers: Dict[str, type[ImageGenProvider]] = {
        "openai": OpenAIImageProvider,
        "xai": XAIImageProvider,
        "deepseek": DeepSeekImageProvider,
    }

    cls = providers.get(provider)
    if cls is None:
        raise ValueError(f"Unknown image provider: {provider}. Available: {list(providers.keys())}")

    if base_url:
        return cls(api_key=api_key, base_url=base_url)
    return cls(api_key=api_key)
