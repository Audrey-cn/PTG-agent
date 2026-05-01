from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger("prometheus.credential_pool")


@dataclass
class CredentialEntry:
    key: str
    provider: str = ""
    base_url: str = ""
    weight: int = 1
    enabled: bool = True
    last_used: float = 0.0
    request_count: int = 0
    error_count: int = 0
    last_error: str = ""
    rate_limited_until: float = 0.0

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        return not self.rate_limited_until > time.time()

    def mark_used(self):
        self.last_used = time.time()
        self.request_count += 1

    def mark_error(self, error: str = ""):
        self.error_count += 1
        self.last_error = error

    def mark_rate_limited(self, cooldown_seconds: float = 60.0):
        self.rate_limited_until = time.time() + cooldown_seconds
        logger.info("Key %s... rate limited for %.0fs", self.key[:8], cooldown_seconds)

    def mark_success(self):
        self.error_count = max(0, self.error_count - 1)


class CredentialPool:
    def __init__(self):
        self._credentials: list[CredentialEntry] = []
        self._lock = threading.Lock()
        self._index = 0

    def add(self, key: str, provider: str = "", base_url: str = "", weight: int = 1):
        with self._lock:
            for c in self._credentials:
                if c.key == key:
                    c.provider = provider or c.provider
                    c.base_url = base_url or c.base_url
                    c.weight = weight
                    return
            self._credentials.append(
                CredentialEntry(
                    key=key,
                    provider=provider,
                    base_url=base_url,
                    weight=weight,
                )
            )

    def remove(self, key: str):
        with self._lock:
            self._credentials = [c for c in self._credentials if c.key != key]

    def get_next(self, provider: str | None = None) -> CredentialEntry | None:
        with self._lock:
            available = [c for c in self._credentials if c.is_available()]
            if provider:
                available = [c for c in available if c.provider == provider or not c.provider]
            if not available:
                return None

            total_weight = sum(c.weight for c in available)
            if total_weight == 0:
                return None

            available.sort(key=lambda c: (c.last_used, c.request_count))
            selected = available[0]
            selected.mark_used()
            return selected

    def report_success(self, key: str):
        with self._lock:
            for c in self._credentials:
                if c.key == key:
                    c.mark_success()
                    break

    def report_error(self, key: str, error: str = ""):
        with self._lock:
            for c in self._credentials:
                if c.key == key:
                    c.mark_error(error)
                    break

    def report_rate_limit(self, key: str, cooldown: float = 60.0):
        with self._lock:
            for c in self._credentials:
                if c.key == key:
                    c.mark_rate_limited(cooldown)
                    break

    def load_from_env(self):
        env_keys = {
            "OPENAI_API_KEY": ("openai", "https://api.openai.com/v1"),
            "ANTHROPIC_API_KEY": ("anthropic", "https://api.anthropic.com"),
            "OPENROUTER_API_KEY": ("openrouter", "https://openrouter.ai/api/v1"),
            "DEEPSEEK_API_KEY": ("deepseek", "https://api.deepseek.com/v1"),
            "GOOGLE_API_KEY": ("gemini", ""),
            "GEMINI_API_KEY": ("gemini", ""),
            "XAI_API_KEY": ("xai", "https://api.x.ai/v1"),
        }
        for env_var, (provider, base_url) in env_keys.items():
            val = os.environ.get(env_var, "").strip()
            if val:
                self.add(key=val, provider=provider, base_url=base_url)

    def load_from_config(self, config_dict: dict):
        api = config_dict.get("api", {})
        key = api.get("key", "")
        if key:
            provider = config_dict.get("model", {}).get("provider", "")
            base_url = api.get("base_url", "")
            self.add(key=key, provider=provider, base_url=base_url, weight=2)

        pool = api.get("credential_pool", [])
        for entry in pool:
            if isinstance(entry, dict) and entry.get("key"):
                self.add(
                    key=entry["key"],
                    provider=entry.get("provider", ""),
                    base_url=entry.get("base_url", ""),
                    weight=entry.get("weight", 1),
                )

    @property
    def size(self) -> int:
        return len(self._credentials)

    @property
    def available_count(self) -> int:
        return sum(1 for c in self._credentials if c.is_available())

    def status(self) -> list[dict]:
        with self._lock:
            result = []
            for c in self._credentials:
                result.append(
                    {
                        "key": c.key[:8] + "..." if len(c.key) > 8 else c.key,
                        "provider": c.provider,
                        "available": c.is_available(),
                        "requests": c.request_count,
                        "errors": c.error_count,
                        "rate_limited": c.rate_limited_until > time.time(),
                    }
                )
            return result


_global_pool: CredentialPool | None = None


def get_credential_pool() -> CredentialPool:
    global _global_pool
    if _global_pool is None:
        _global_pool = CredentialPool()
        _global_pool.load_from_env()
    return _global_pool
