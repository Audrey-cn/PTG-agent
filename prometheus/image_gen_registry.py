from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from prometheus.image_gen_provider import ImageGenProvider

logger = logging.getLogger("prometheus.image_gen_registry")


class ImageGenRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, ImageGenProvider] = {}

    def register(self, name: str, provider: ImageGenProvider) -> None:
        self._providers[name] = provider
        logger.info("Registered image provider: %s", name)

    def get(self, name: str) -> Optional[ImageGenProvider]:
        return self._providers.get(name)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())

    def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        if provider is not None:
            p = self._providers.get(provider)
            if p is None:
                raise ValueError(f"Image provider not found: {provider}")
            return p.generate(prompt, **kwargs)

        if not self._providers:
            raise RuntimeError("No image providers registered")

        last_error: Optional[Exception] = None
        for name, p in self._providers.items():
            try:
                return p.generate(prompt, **kwargs)
            except Exception as exc:
                logger.warning("Provider %s failed: %s", name, exc)
                last_error = exc

        raise RuntimeError(f"All image providers failed. Last error: {last_error}")


registry = ImageGenRegistry()
