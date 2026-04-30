"""
模型提供者注册系统

参照 Hermes (ElizaOS) buildCharacterPlugins() 的自动探测模式,
支持从环境变量自动发现可用模型提供者。

提供者优先级: Anthropic → OpenRouter → OpenAI → Google GenAI → 本地兼容
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModelProvider:
    id: str
    name: str
    description: str
    env_key: str
    api_base: str = ""
    default_model: str = ""
    fallback_models: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    config_section: str = "model"
    priority: int = 99

    def is_available(self) -> bool:
        return bool(os.environ.get(self.env_key))


PROVIDER_SPECS: Dict[str, ModelProvider] = {
    "anthropic": ModelProvider(
        id="anthropic",
        name="Anthropic Claude",
        description="Claude 系列模型，安全与深度推理见长",
        env_key="ANTHROPIC_API_KEY",
        api_base="https://api.anthropic.com",
        default_model="claude-sonnet-4-20250514",
        fallback_models=["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        capabilities=["reasoning", "coding", "analysis", "long_context"],
        priority=1,
    ),
    "openrouter": ModelProvider(
        id="openrouter",
        name="OpenRouter",
        description="多模型聚合网关，统一API访问主流模型",
        env_key="OPENROUTER_API_KEY",
        api_base="https://openrouter.ai/api/v1",
        default_model="anthropic/claude-sonnet-4",
        fallback_models=["google/gemini-2.5-pro-preview", "openai/gpt-4o", "meta-llama/llama-4-maverick"],
        capabilities=["multi_provider", "routing", "fallback", "cost_optimization"],
        priority=2,
    ),
    "openai": ModelProvider(
        id="openai",
        name="OpenAI",
        description="GPT 系列模型，通用能力均衡",
        env_key="OPENAI_API_KEY",
        api_base="https://api.openai.com/v1",
        default_model="gpt-4o",
        fallback_models=["gpt-4o-mini", "gpt-4-turbo"],
        capabilities=["coding", "analysis", "creative"],
        priority=3,
    ),
    "google": ModelProvider(
        id="google",
        name="Google GenAI",
        description="Gemini 系列模型，长上下文与多模态见长",
        env_key="GOOGLE_API_KEY",
        api_base="",
        default_model="gemini-2.5-pro-preview",
        fallback_models=["gemini-2.0-flash", "gemini-1.5-pro"],
        capabilities=["long_context", "multimodal", "reasoning"],
        priority=4,
    ),
    "deepseek": ModelProvider(
        id="deepseek",
        name="DeepSeek",
        description="高性价比推理模型，编程与数学见长",
        env_key="DEEPSEEK_API_KEY",
        api_base="https://api.deepseek.com",
        default_model="deepseek-chat",
        fallback_models=["deepseek-coder"],
        capabilities=["coding", "math", "reasoning"],
        priority=5,
    ),
    "local": ModelProvider(
        id="local",
        name="本地模型 (Ollama/LM Studio)",
        description="完全离线运行，隐私优先",
        env_key="OLLAMA_HOST",
        api_base="http://localhost:11434",
        default_model="llama3.2",
        fallback_models=["mistral", "phi3"],
        capabilities=["offline", "privacy", "low_cost"],
        priority=6,
    ),
}


class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, ModelProvider] = dict(PROVIDER_SPECS)
        self._active: Optional[str] = None
        self._available: List[str] = []
        self._refresh()

    def _refresh(self):
        self._available = [pid for pid, p in self._providers.items() if p.is_available()]
        if not self._active or self._active not in self._available:
            self._active = self._available[0] if self._available else "local"

    def register(self, provider: ModelProvider):
        self._providers[provider.id] = provider
        self._refresh()

    def unregister(self, provider_id: str):
        if provider_id in self._providers:
            del self._providers[provider_id]
        self._refresh()

    def get(self, provider_id: str) -> Optional[ModelProvider]:
        return self._providers.get(provider_id)

    @property
    def active(self) -> Optional[ModelProvider]:
        return self._providers.get(self._active) if self._active else None

    @property
    def active_id(self) -> Optional[str]:
        return self._active

    @active_id.setter
    def active_id(self, provider_id: str):
        if provider_id not in self._providers:
            raise ValueError(f"未知提供者: {provider_id}")
        self._active = provider_id

    @property
    def available(self) -> List[ModelProvider]:
        return [self._providers[pid] for pid in self._available]

    def list_all(self) -> Dict[str, dict]:
        return {
            pid: {
                "name": p.name,
                "available": p.is_available(),
                "default_model": p.default_model,
                "priority": p.priority,
                "capabilities": p.capabilities,
            }
            for pid, p in self._providers.items()
        }

    def detect_and_select(self) -> ModelProvider:
        self._refresh()
        available = self.available
        if available:
            selected = available[0]
            self._active = selected.id
            return selected
        self._active = "local"
        return self._providers["local"]

    def get_fallback_chain(self) -> List[str]:
        """返回可用提供者的ID回退链，按优先级排序"""
        chain = [p.id for p in sorted(self.available, key=lambda p: p.priority)]
        if "local" not in chain:
            chain.append("local")
        return chain


_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def detect_available_providers() -> List[ModelProvider]:
    return get_provider_registry().available
