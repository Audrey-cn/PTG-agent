"""🔮 动态模型发现 — DynamicModelDiscoverer."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODELS_DEV_URL = "https://models.dev/api.json"
MODELS_DEV_CACHE_FILE = Path(os.path.expanduser("~/.prometheus/models_dev_cache.json"))
MODELS_DEV_CACHE_TTL = 3600


@dataclass
class DiscoveredModel:
    """发现的模型"""

    id: str
    provider: str
    description: str | None = None
    context_window: int | None = None


class DynamicModelDiscoverer:
    """动态模型发现器"""

    def __init__(self, cache_ttl: int = MODELS_DEV_CACHE_TTL):
        self.cache_ttl = cache_ttl
        self._cache: dict[str, Any] | None = None
        self._cache_time: float = 0
        self._preferred_providers = {
            "openai",
            "anthropic",
            "google",
            "deepseek",
            "meta-llama",
            "mistralai",
            "qwen",
        }

    def discover_from_models_dev(self) -> dict[str, list[DiscoveredModel]]:
        """从 models.dev API 获取所有模型

        Returns:
            按提供商分组的模型字典
        """
        if self._is_cache_valid():
            return self._parse_models_dev(self._cache)

        try:
            import urllib.request

            req = urllib.request.Request(MODELS_DEV_URL, headers={"User-Agent": "Prometheus/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                self._cache = data
                self._cache_time = time.time()
                self._save_cache(data)
                return self._parse_models_dev(data)
        except Exception as e:
            print(f"Failed to fetch models.dev: {e}")
            return self._load_cache() or {}

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._cache is None:
            self._load_cache()
        if self._cache is None:
            return False
        return (time.time() - self._cache_time) < self.cache_ttl

    def _save_cache(self, data: dict[str, Any]) -> None:
        """保存缓存到磁盘"""
        try:
            MODELS_DEV_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MODELS_DEV_CACHE_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _load_cache(self) -> dict[str, Any] | None:
        """从磁盘加载缓存"""
        if not MODELS_DEV_CACHE_FILE.exists():
            return None
        try:
            with open(MODELS_DEV_CACHE_FILE) as f:
                self._cache = json.load(f)
                self._cache_time = os.path.getmtime(MODELS_DEV_CACHE_FILE)
                return self._cache
        except Exception:
            return None

    def _parse_models_dev(self, data: dict[str, Any]) -> dict[str, list[DiscoveredModel]]:
        """解析 models.dev 数据"""
        result: dict[str, list[DiscoveredModel]] = {}

        if not isinstance(data, dict):
            return result

        for provider, models in data.items():
            if not isinstance(models, list):
                continue
            if provider not in self._preferred_providers:
                continue

            model_list = []
            for model in models:
                if isinstance(model, dict):
                    model_list.append(
                        DiscoveredModel(
                            id=model.get("id", ""),
                            provider=provider,
                            description=model.get("description"),
                            context_window=model.get("context_length"),
                        )
                    )
                elif isinstance(model, str):
                    model_list.append(DiscoveredModel(id=model, provider=provider))

            if model_list:
                result[provider] = model_list

        return result

    def discover_from_openai(self) -> list[DiscoveredModel]:
        """从 OpenAI API 发现模型

        需要 OPENAI_API_KEY 环境变量
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return []

        try:
            import urllib.request

            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Prometheus/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                models = []
                for model in data.get("data", []):
                    models.append(
                        DiscoveredModel(
                            id=model.get("id", ""),
                            provider="openai",
                            description=model.get("description"),
                        )
                    )
                return models
        except Exception:
            return []

    def discover_from_anthropic(self) -> list[DiscoveredModel]:
        """从 Anthropic 发现模型（基于已知列表）"""
        return [
            DiscoveredModel(id="claude-3-5-sonnet-4", provider="anthropic"),
            DiscoveredModel(id="claude-3-5-haiku-3", provider="anthropic"),
            DiscoveredModel(id="claude-sonnet-4", provider="anthropic"),
            DiscoveredModel(id="claude-opus-4", provider="anthropic"),
            DiscoveredModel(id="claude-3-opus", provider="anthropic"),
            DiscoveredModel(id="claude-3-sonnet", provider="anthropic"),
            DiscoveredModel(id="claude-3-haiku", provider="anthropic"),
        ]

    def discover_from_provider(self, provider: str) -> list[DiscoveredModel]:
        """从特定提供商发现模型

        Args:
            provider: 提供商名称

        Returns:
            模型列表
        """
        if provider == "openai":
            return self.discover_from_openai()
        elif provider == "anthropic":
            return self.discover_from_anthropic()
        elif provider in self._preferred_providers:
            models_dev = self.discover_from_models_dev()
            return models_dev.get(provider, [])
        else:
            return []

    def refresh(self) -> dict[str, list[DiscoveredModel]]:
        """强制刷新模型列表"""
        self._cache = None
        self._cache_time = 0
        return self.discover_from_models_dev()

    def get_all_models(self) -> list[DiscoveredModel]:
        """获取所有发现的模型"""
        all_models = []
        models_dev = self.discover_from_models_dev()
        for models in models_dev.values():
            all_models.extend(models)
        return all_models


_discoverer_instance: DynamicModelDiscoverer | None = None


def get_discoverer() -> DynamicModelDiscoverer:
    """获取全局发现器实例"""
    global _discoverer_instance
    if _discoverer_instance is None:
        _discoverer_instance = DynamicModelDiscoverer()
    return _discoverer_instance
