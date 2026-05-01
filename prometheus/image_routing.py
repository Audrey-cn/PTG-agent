from __future__ import annotations

from typing import Any, Callable


class ImageRouter:
    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Any]] = {}
        self._default_provider: str | None = None

    def route_request(self, prompt: str, size: str = "1024x1024", style: str = "default") -> str:
        provider_name = self.get_provider_for_request(prompt)
        if not provider_name:
            raise RuntimeError("No image provider available")
        provider_info = self._providers.get(provider_name, {})
        provider = provider_info.get("provider")
        if provider and callable(provider):
            return provider(prompt, size, style)
        return f"{provider_name}:{prompt[:50]}"

    def add_provider(
        self,
        name: str,
        provider: Callable[[str, str, str], str] | Any,
        priority: int = 0,
    ) -> None:
        self._providers[name] = {
            "provider": provider,
            "priority": priority,
            "enabled": True,
        }
        if self._default_provider is None:
            self._default_provider = name

    def remove_provider(self, name: str) -> bool:
        if name in self._providers:
            del self._providers[name]
            if self._default_provider == name:
                self._default_provider = None
            return True
        return False

    def get_provider_for_request(self, prompt: str) -> str | None:
        enabled_providers = [
            (name, info)
            for name, info in self._providers.items()
            if info.get("enabled", True)
        ]
        if not enabled_providers:
            return self._default_provider
        sorted_providers = sorted(
            enabled_providers,
            key=lambda x: x[1].get("priority", 0),
            reverse=True,
        )
        return sorted_providers[0][0]

    def enable_provider(self, name: str) -> None:
        if name in self._providers:
            self._providers[name]["enabled"] = True

    def disable_provider(self, name: str) -> None:
        if name in self._providers:
            self._providers[name]["enabled"] = False

    def set_default_provider(self, name: str) -> None:
        if name in self._providers:
            self._default_provider = name

    def get_providers(self) -> list[str]:
        return list(self._providers.keys())

    def get_provider_info(self, name: str) -> dict[str, Any] | None:
        return self._providers.get(name)
