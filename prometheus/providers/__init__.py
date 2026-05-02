from __future__ import annotations

#!/usr/bin/env python3
"""Prometheus 模型 Provider 扩展."""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    from openai import AsyncOpenAI, OpenAI
except ImportError:
    OpenAI = None
    AsyncOpenAI = None

logger = logging.getLogger("prometheus.providers")


class GroqProvider:
    """Groq AI Provider"""

    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str | None = None):
        if OpenAI is None:
            raise ImportError("openai library is required for GroqProvider")

        self.client = OpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
        )
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
        )

    def create_completion(self, messages: list[dict], model: str, **kwargs) -> dict:
        """创建完成"""
        response = self.client.chat.completions.create(model=model, messages=messages, **kwargs)
        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
        }

    async def create_completion_async(self, messages: list[dict], model: str, **kwargs) -> dict:
        """异步创建完成"""
        response = await self.async_client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
        }

    def get_models(self) -> list[str]:
        """获取可用模型列表"""
        return [
            "mixtral-8x7b-32768",
            "llama-3.1-8b-instant",
            "llama-3.1-70b-versatile",
            "gemma2-9b-it",
            "llama-3-8b-8192",
            "llama-3-70b-8192",
            "mixtral-8x22b-65536",
        ]


class VLLMProvider:
    """VLLM 本地部署 Provider"""

    def __init__(self, base_url: str = "http://localhost:8000/v1", api_key: str = "EMPTY"):
        if OpenAI is None:
            raise ImportError("openai library is required for VLLMProvider")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def create_completion(self, messages: list[dict], model: str, **kwargs) -> dict:
        """创建完成"""
        response = self.client.chat.completions.create(model=model, messages=messages, **kwargs)
        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
        }

    async def create_completion_async(self, messages: list[dict], model: str, **kwargs) -> dict:
        """异步创建完成"""
        response = await self.async_client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
        }

    def get_models(self) -> list[str]:
        """获取可用模型列表"""
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception:
            return ["local-model"]


class XAIProvider:
    """XAI Provider"""

    BASE_URL = "https://api.x.ai/v1"

    def __init__(self, api_key: str | None = None):
        if OpenAI is None:
            raise ImportError("openai library is required for XAIProvider")

        self.client = OpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
        )
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
        )

    def create_completion(self, messages: list[dict], model: str, **kwargs) -> dict:
        """创建完成"""
        response = self.client.chat.completions.create(model=model, messages=messages, **kwargs)
        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
        }

    async def create_completion_async(self, messages: list[dict], model: str, **kwargs) -> dict:
        """异步创建完成"""
        response = await self.async_client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
        }

    def get_models(self) -> list[str]:
        """获取可用模型列表"""
        return [
            "grok-beta",
            "grok-vision-beta",
        ]


class ZAIProvider:
    """ZAI (智谱) Provider"""

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(self, api_key: str | None = None):
        if OpenAI is None:
            raise ImportError("openai library is required for ZAIProvider")

        self.client = OpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
        )
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
        )

    def create_completion(self, messages: list[dict], model: str, **kwargs) -> dict:
        """创建完成"""
        response = self.client.chat.completions.create(model=model, messages=messages, **kwargs)
        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
        }

    async def create_completion_async(self, messages: list[dict], model: str, **kwargs) -> dict:
        """异步创建完成"""
        response = await self.async_client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
        }

    def get_models(self) -> list[str]:
        """获取可用模型列表"""
        return [
            "glm-4",
            "glm-4v",
            "glm-3-turbo",
            "chatglm_lite",
        ]


class ProviderRegistry:
    """Provider 注册表"""

    _instance = None
    _providers: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {
                "groq": GroqProvider,
                "vllm": VLLMProvider,
                "xai": XAIProvider,
                "zai": ZAIProvider,
            }
        return cls._instance

    def register_provider(self, name: str, provider_class: Any):
        """注册 Provider"""
        self._providers[name] = provider_class

    def get_provider(self, name: str) -> Any | None:
        """获取 Provider 类"""
        return self._providers.get(name)

    def create_provider(self, name: str, **kwargs) -> Any | None:
        """创建 Provider 实例"""
        provider_class = self.get_provider(name)
        if provider_class:
            return provider_class(**kwargs)
        return None

    def list_providers(self) -> list[str]:
        """列出所有 Provider"""
        return list(self._providers.keys())


def register_extended_providers():
    """注册扩展 Provider"""
    ProviderRegistry()

    from prometheus.agent_loop import TransportFactory

    @TransportFactory.register("groq")
    def create_groq_transport(api_key: str = None, **kwargs):
        return GroqProvider(api_key=api_key)

    @TransportFactory.register("vllm")
    def create_vllm_transport(api_key: str = None, base_url: str = None, **kwargs):
        return VLLMProvider(
            api_key=api_key or "EMPTY", base_url=base_url or "http://localhost:8000/v1"
        )

    @TransportFactory.register("xai")
    def create_xai_transport(api_key: str = None, **kwargs):
        return XAIProvider(api_key=api_key)

    @TransportFactory.register("zai")
    def create_zai_transport(api_key: str = None, **kwargs):
        return ZAIProvider(api_key=api_key)

    logger.info("Extended providers registered: groq, vllm, xai, zai")


if __name__ == "__main__":
    print("🤖 Extended AI Providers")
    print("=" * 50)

    registry = ProviderRegistry()
    print(f"Available providers: {', '.join(registry.list_providers())}")

    print("\nGroq models:")
    try:
        groq = GroqProvider()
        print(f"  {groq.get_models()}")
    except Exception as e:
        print(f"  ❌ Not configured: {e}")

    print("\nVLLM models (requires local server):")
    try:
        vllm = VLLMProvider()
        print(f"  {vllm.get_models()}")
    except Exception as e:
        print(f"  ❌ Not available: {e}")

    print("\nXAI models:")
    try:
        xai = XAIProvider()
        print(f"  {xai.get_models()}")
    except Exception as e:
        print(f"  ❌ Not configured: {e}")

    print("\nZAI (智谱) models:")
    try:
        zai = ZAIProvider()
        print(f"  {zai.get_models()}")
    except Exception as e:
        print(f"  ❌ Not configured: {e}")
