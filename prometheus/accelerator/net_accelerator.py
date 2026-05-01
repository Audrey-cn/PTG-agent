#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Platform(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    HUGGING_FACE = "huggingface"
    PYPI = "pypi"
    NPM = "npm"
    OTHER = "other"


@dataclass
class PlatformConfig:
    name: str
    domain: str
    accelerator_prefix: str
    enabled: bool = True


@dataclass
class AcceleratorNode:
    url: str
    priority: int = 0
    weight: int = 1
    enabled: bool = True
    last_used: float = 0.0
    failure_count: int = 0
    failure_threshold: int = 3
    cooldown_seconds: int = 60
    disabled_until: float = 0.0

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        return not time.time() < self.disabled_until

    def record_success(self):
        self.failure_count = 0
        self.last_used = time.time()

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.disabled_until = time.time() + self.cooldown_seconds
            logger.warning(f"Node {self.url} disabled for {self.cooldown_seconds}s")


@dataclass
class AccelerateResult:
    success: bool
    original_url: str
    accelerated_url: str | None = None
    content: bytes | None = None
    error: str | None = None
    status_code: int | None = None
    response_time: float = 0.0
    node_used: str | None = None
    fallback_used: bool = False


PLATFORM_CONFIGS: dict[Platform, PlatformConfig] = {
    Platform.GITHUB: PlatformConfig(
        name="GitHub",
        domain="github.com",
        accelerator_prefix="https://xget.xi-xu.me/gh/",
    ),
    Platform.GITLAB: PlatformConfig(
        name="GitLab",
        domain="gitlab.com",
        accelerator_prefix="https://xget.xi-xu.me/gl/",
    ),
    Platform.HUGGING_FACE: PlatformConfig(
        name="Hugging Face",
        domain="huggingface.co",
        accelerator_prefix="https://xget.xi-xu.me/hf/",
    ),
    Platform.PYPI: PlatformConfig(
        name="PyPI",
        domain="pypi.org",
        accelerator_prefix="https://xget.xi-xu.me/pypi/",
    ),
    Platform.NPM: PlatformConfig(
        name="npm",
        domain="npmjs.com",
        accelerator_prefix="https://xget.xi-xu.me/npm/",
    ),
}


class NetAccelerator:
    """网络加速器"""

    DEFAULT_CONFIG = {
        "enabled": True,
        "default_node": "https://xget.xi-xu.me",
        "fallback_enabled": True,
        "timeout_seconds": 30,
        "max_retries": 3,
        "retry_delay_seconds": 1.0,
        "routing_strategy": "weighted_round_robin",
    }

    def __init__(self, config: dict = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.nodes: list[AcceleratorNode] = self._load_nodes()
        self.platform_configs = PLATFORM_CONFIGS.copy()

    def _load_nodes(self) -> list[AcceleratorNode]:
        nodes = []
        for node_cfg in self.config.get("nodes", []):
            nodes.append(
                AcceleratorNode(
                    url=node_cfg.get("url", ""),
                    priority=node_cfg.get("priority", 0),
                    weight=node_cfg.get("weight", 1),
                    enabled=node_cfg.get("enabled", True),
                )
            )

        if not nodes:
            nodes.append(
                AcceleratorNode(url=self.config.get("default_node", "https://xget.xi-xu.me"))
            )

        return nodes

    def identify_platform(self, url: str) -> tuple[Platform | None, PlatformConfig | None]:
        """识别 URL 对应的平台"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            for platform, config in self.platform_configs.items():
                if config.enabled and config.domain in domain:
                    return platform, config

            return None, None
        except Exception:
            return None, None

    def accelerate_url(self, url: str, node_url: str | None = None) -> str | None:
        """转换 URL 为加速 URL"""
        platform, config = self.identify_platform(url)
        if not platform or not config:
            return None

        try:
            parsed = urlparse(url)

            if node_url:
                base = node_url.rstrip("/")
                path_prefix = config.accelerator_prefix.split("/", 3)[-1].rstrip("/")
                accelerated = f"{base}/{path_prefix}/{parsed.netloc}{parsed.path}"
            else:
                accelerated = f"{config.accelerator_prefix.rstrip('/')}{parsed.path}"

            if parsed.query:
                accelerated += f"?{parsed.query}"

            return accelerated
        except Exception as e:
            logger.error(f"URL acceleration failed: {e}")
            return None

    def select_node(self) -> AcceleratorNode | None:
        """选择可用节点"""
        available = [n for n in self.nodes if n.is_available()]
        if not available:
            logger.warning("No available accelerator nodes")
            return None

        strategy = self.config.get("routing_strategy", "weighted_round_robin")

        if strategy == "priority":
            available.sort(key=lambda x: x.priority)
            return available[0]
        elif strategy == "random":
            return random.choice(available)
        else:
            weighted = []
            for node in available:
                weighted.extend([node] * node.weight)
            return random.choice(weighted)

    async def fetch(self, url: str, **kwargs) -> AccelerateResult:
        """加速获取资源"""
        start_time = time.time()

        if not self.config.get("enabled", True):
            logger.debug("Accelerator disabled, direct fetch")
            return await self._direct_fetch(url, **kwargs)

        platform, config = self.identify_platform(url)
        if not platform or not config:
            logger.debug(f"Platform not supported: {url}")
            return await self._direct_fetch(url, **kwargs)

        max_retries = self.config.get("max_retries", 3)
        last_error = None

        for attempt in range(max_retries):
            node = self.select_node()
            if not node:
                break

            accelerated_url = self.accelerate_url(url, node.url)
            if not accelerated_url:
                break

            logger.info(f"Attempt {attempt + 1}/{max_retries}: {accelerated_url}")

            try:
                result = await self._make_request(accelerated_url, **kwargs)
                result.node_used = node.url
                result.original_url = url
                result.accelerated_url = accelerated_url

                if result.success:
                    node.record_success()
                    return result
                else:
                    node.record_failure()
                    last_error = result.error

            except Exception as e:
                node.record_failure()
                last_error = str(e)
                logger.error(f"Request failed: {e}")

            if attempt < max_retries - 1:
                delay = self.config.get("retry_delay_seconds", 1.0) * (attempt + 1)
                await asyncio.sleep(delay)

        if self.config.get("fallback_enabled", True):
            logger.info(f"All nodes failed, fallback to direct: {url}")
            result = await self._direct_fetch(url, **kwargs)
            result.fallback_used = True
            return result

        return AccelerateResult(
            success=False,
            original_url=url,
            error=last_error or "All accelerator nodes failed",
            response_time=time.time() - start_time,
        )

    async def _make_request(self, url: str, **kwargs) -> AccelerateResult:
        """发送 HTTP 请求"""
        start_time = time.time()
        timeout = self.config.get("timeout_seconds", 30)

        try:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(url, **kwargs)
                    return AccelerateResult(
                        success=response.status_code < 400,
                        original_url=url,
                        content=response.content,
                        status_code=response.status_code,
                        response_time=time.time() - start_time,
                    )
            except ImportError:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=timeout, **kwargs) as response:
                        content = await response.read()
                        return AccelerateResult(
                            success=response.status < 400,
                            original_url=url,
                            content=content,
                            status_code=response.status,
                            response_time=time.time() - start_time,
                        )
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            return AccelerateResult(
                success=False,
                original_url=url,
                error=str(e),
                response_time=time.time() - start_time,
            )

    async def _direct_fetch(self, url: str, **kwargs) -> AccelerateResult:
        """直接获取（不加速）"""
        result = await self._make_request(url, **kwargs)
        result.fallback_used = False
        return result

    def get_status(self) -> dict:
        """获取状态"""
        available = sum(1 for n in self.nodes if n.is_available())
        return {
            "enabled": self.config.get("enabled", True),
            "nodes": {
                "total": len(self.nodes),
                "available": available,
                "details": [
                    {
                        "url": n.url,
                        "available": n.is_available(),
                        "priority": n.priority,
                        "weight": n.weight,
                        "failure_count": n.failure_count,
                    }
                    for n in self.nodes
                ],
            },
            "platforms": {p.value: c.enabled for p, c in self.platform_configs.items()},
        }


_accelerator: NetAccelerator | None = None


def get_accelerator(config: dict = None) -> NetAccelerator:
    """获取全局加速器实例"""
    global _accelerator
    if _accelerator is None:
        _accelerator = NetAccelerator(config)
    return _accelerator


async def accelerate_fetch(url: str, **kwargs) -> AccelerateResult:
    """便捷函数：加速获取"""
    accelerator = get_accelerator()
    return await accelerator.fetch(url, **kwargs)
