"""模型路由器."""

import time
from dataclasses import dataclass
from typing import Any

from .providers import ModelProvider, ProviderRegistry, get_provider_registry


@dataclass
class RouteResult:
    success: bool
    provider_id: str
    model: str
    response: Any | None = None
    error: str | None = None
    attempts: int = 0
    latency_ms: float = 0.0


@dataclass
class ProviderStats:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    total_latency_ms: float = 0.0
    last_failure: float = 0.0
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.successful == 0:
            return 0.0
        return self.total_latency_ms / self.successful

    @property
    def is_healthy(self) -> bool:
        return self.consecutive_failures < 3


class ModelRouter:
    def __init__(self, registry: ProviderRegistry = None):
        self._registry = registry or get_provider_registry()
        self._stats: dict[str, ProviderStats] = {}
        self._circuit_breaker: dict[str, float] = {}

    def get_stats(self) -> dict[str, dict]:
        return {
            pid: {
                "success_rate": s.success_rate,
                "avg_latency_ms": s.avg_latency_ms,
                "total_requests": s.total_requests,
                "consecutive_failures": s.consecutive_failures,
                "healthy": s.is_healthy,
            }
            for pid, s in self._stats.items()
        }

    def _get_stats(self, provider_id: str) -> ProviderStats:
        if provider_id not in self._stats:
            self._stats[provider_id] = ProviderStats()
        return self._stats[provider_id]

    def _is_circuit_open(self, provider_id: str) -> bool:
        last_fail = self._circuit_breaker.get(provider_id, 0)
        if last_fail == 0:
            return False
        cooldown = 30
        return (time.time() - last_fail) < cooldown

    def _record_success(self, provider_id: str, latency_ms: float):
        s = self._get_stats(provider_id)
        s.total_requests += 1
        s.successful += 1
        s.total_latency_ms += latency_ms
        s.consecutive_failures = 0

    def _record_failure(self, provider_id: str):
        s = self._get_stats(provider_id)
        s.total_requests += 1
        s.failed += 1
        s.last_failure = time.time()
        s.consecutive_failures += 1
        if s.consecutive_failures >= 3:
            self._circuit_breaker[provider_id] = time.time()

    def select_provider(self, preferred: str = None) -> ModelProvider:
        registry = self._registry
        registry.detect_and_select()

        if preferred:
            provider = registry.get(preferred)
            if provider and provider.is_available() and not self._is_circuit_open(preferred):
                return provider

        fallback_chain = registry.get_fallback_chain()
        for pid in fallback_chain:
            provider = registry.get(pid)
            if provider and provider.is_available() and not self._is_circuit_open(pid):
                stats = self._stats.get(pid)
                if stats and not stats.is_healthy:
                    continue
                return provider

        return registry.get("local")

    def get_available_models(self) -> dict[str, list[str]]:
        result = {}
        for provider in self._registry.available:
            models = [provider.default_model] + provider.fallback_models
            result[provider.id] = models
        return result

    def get_fallback_chain_info(self) -> list[dict]:
        chain = self._registry.get_fallback_chain()
        return [
            {
                "provider_id": pid,
                "name": (
                    self._registry.get(pid)
                    or ModelProvider(id=pid, name=pid, description="", env_key="")
                ).name,
                "available": (
                    self._registry.get(pid)
                    or ModelProvider(id=pid, name=pid, description="", env_key="")
                ).is_available(),
                "circuit_open": self._is_circuit_open(pid),
                "stats": self.get_stats().get(pid, {}),
            }
            for pid in chain
        ]

    def select_model_for_provider(self, provider_id: str) -> str:
        provider = self._registry.get(provider_id)
        if not provider:
            return "default"
        return provider.default_model


_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def route_model_request(preferred_provider: str = None) -> dict:
    router = get_model_router()
    provider = router.select_provider(preferred_provider)
    model = router.select_model_for_provider(provider.id)
    return {
        "provider_id": provider.id,
        "provider_name": provider.name,
        "model": model,
        "api_base": provider.api_base,
        "capabilities": provider.capabilities,
        "fallback_chain": [
            fb["provider_id"]
            for fb in router.get_fallback_chain_info()
            if fb["provider_id"] != provider.id
        ],
    }
