#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

# ═══════════════════════════════════════════
#   日志配置
# ═══════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
#   平台定义
# ═══════════════════════════════════════════


class Platform(Enum):
    """支持的加速平台"""

    GITHUB = "github"
    GITLAB = "gitlab"
    GITEA = "gitea"
    CODEBERG = "codeberg"
    HUGGING_FACE = "huggingface"
    CIVITAI = "civitai"
    NPM = "npm"
    PYPI = "pypi"
    DOCKER = "docker"
    GCR = "gcr"
    QUAY = "quay"
    OTHER = "other"


@dataclass
class PlatformConfig:
    """平台配置"""

    name: str
    domain: str
    xget_prefix: str
    enabled: bool = True
    description: str = ""


# 默认平台配置
PLATFORM_CONFIGS: dict[Platform, PlatformConfig] = {
    Platform.GITHUB: PlatformConfig(
        name="GitHub",
        domain="github.com",
        xget_prefix="https://xget.xi-xu.me/gh/",
        description="GitHub 代码仓库和文件",
    ),
    Platform.GITLAB: PlatformConfig(
        name="GitLab",
        domain="gitlab.com",
        xget_prefix="https://xget.xi-xu.me/gl/",
        description="GitLab 代码仓库",
    ),
    Platform.HUGGING_FACE: PlatformConfig(
        name="Hugging Face",
        domain="huggingface.co",
        xget_prefix="https://xget.xi-xu.me/hf/",
        description="Hugging Face 模型和数据集",
    ),
    Platform.PYPI: PlatformConfig(
        name="PyPI",
        domain="pypi.org",
        xget_prefix="https://xget.xi-xu.me/pypi/",
        description="Python 包索引",
    ),
    Platform.NPM: PlatformConfig(
        name="npm",
        domain="npmjs.com",
        xget_prefix="https://xget.xi-xu.me/npm/",
        description="Node.js 包管理器",
    ),
    Platform.CIVITAI: PlatformConfig(
        name="CivitAI",
        domain="civitai.com",
        xget_prefix="https://xget.xi-xu.me/civitai/",
        description="CivitAI 模型平台",
    ),
}


# ═══════════════════════════════════════════
#   Xget 实例配置
# ═══════════════════════════════════════════


@dataclass
class XgetInstance:
    """Xget 实例配置"""

    url: str
    priority: int = 0  # 优先级，数字越小优先级越高
    weight: int = 1  # 权重，用于负载均衡
    enabled: bool = True
    last_used: float = 0.0
    failure_count: int = 0
    failure_threshold: int = 3  # 失败多少次后暂时禁用
    cooldown_seconds: int = 60  # 冷却时间
    disabled_until: float = 0.0

    def is_available(self) -> bool:
        """检查实例是否可用"""
        if not self.enabled:
            return False
        return not time.time() < self.disabled_until

    def record_success(self):
        """记录成功请求"""
        self.failure_count = 0
        self.last_used = time.time()

    def record_failure(self):
        """记录失败请求"""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.disabled_until = time.time() + self.cooldown_seconds
            logger.warning(f"Xget 实例 {self.url} 已暂时禁用，冷却 {self.cooldown_seconds} 秒")


# ═══════════════════════════════════════════
#   请求结果
# ═══════════════════════════════════════════


@dataclass
class RequestResult:
    """请求结果"""

    success: bool
    url: str
    content: bytes | None = None
    error: str | None = None
    status_code: int | None = None
    response_time: float = 0.0
    instance_used: str | None = None
    fallback_used: bool = False


# ═══════════════════════════════════════════
#   Xget 集成主类
# ═══════════════════════════════════════════


class XgetIntegration:
    """Xget 集成主类，提供 URL 转换、路由、fallback 机制。"""

    def __init__(self, config: dict[str, Any] | None = None):
        """
        初始化 Xget 集成。

        Args:
            config: 配置字典，可选。如果不提供，会使用默认配置。
        """
        self.config = config or self._get_default_config()
        self.instances: list[XgetInstance] = self._load_instances()
        self.platform_configs: dict[Platform, PlatformConfig] = PLATFORM_CONFIGS.copy()

        # 从配置中覆盖平台设置
        if "platforms" in self.config:
            for platform_name, platform_cfg in self.config["platforms"].items():
                try:
                    platform = Platform(platform_name)
                    if platform in self.platform_configs:
                        for key, value in platform_cfg.items():
                            if hasattr(self.platform_configs[platform], key):
                                setattr(self.platform_configs[platform], key, value)
                except ValueError:
                    logger.warning(f"未知平台: {platform_name}")

    @staticmethod
    def _get_default_config() -> dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": True,
            "default_instance": "https://xget.xi-xu.me",
            "fallback_enabled": True,
            "fallback_timeout_seconds": 10,
            "request_timeout_seconds": 30,
            "max_retries": 3,
            "retry_delay_seconds": 1.0,
            "load_balancing": "weighted_round_robin",  # 或 "random", "priority"
            "instances": [
                {"url": "https://xget.xi-xu.me", "priority": 0, "weight": 3},
                {"url": "https://xget-mirror1.example.com", "priority": 1, "weight": 2},
                {"url": "https://xget-mirror2.example.com", "priority": 2, "weight": 1},
            ],
            "platforms": {},
        }

    def _load_instances(self) -> list[XgetInstance]:
        """从配置加载 Xget 实例"""
        instances = []
        for instance_cfg in self.config.get("instances", []):
            try:
                instance = XgetInstance(
                    url=instance_cfg.get("url", ""),
                    priority=instance_cfg.get("priority", 0),
                    weight=instance_cfg.get("weight", 1),
                    enabled=instance_cfg.get("enabled", True),
                )
                instances.append(instance)
            except Exception as e:
                logger.error(f"加载 Xget 实例配置失败: {e}")

        # 如果没有配置实例，添加默认实例
        if not instances:
            instances.append(
                XgetInstance(url=self.config.get("default_instance", "https://xget.xi-xu.me"))
            )

        return instances

    def identify_platform(self, url: str) -> tuple[Platform | None, PlatformConfig | None]:
        """
        识别 URL 对应的平台。

        Args:
            url: 要识别的 URL

        Returns:
            (Platform, PlatformConfig) 元组，如果无法识别则为 (None, None)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            for platform, config in self.platform_configs.items():
                if config.enabled and config.domain in domain:
                    return platform, config

            return None, None
        except Exception as e:
            logger.error(f"识别平台失败: {e}")
            return None, None

    def convert_url(self, url: str, instance_url: str | None = None) -> str | None:
        """
        将原始 URL 转换为 Xget 加速 URL。

        Args:
            url: 原始 URL
            instance_url: 指定使用的 Xget 实例 URL，可选

        Returns:
            转换后的 Xget URL，如果不支持该平台则返回 None
        """
        platform, config = self.identify_platform(url)
        if not platform or not config:
            logger.debug(f"不支持的平台: {url}")
            return None

        try:
            parsed = urlparse(url)

            # 构建加速 URL
            if instance_url:
                # 使用指定的实例
                base_url = instance_url.rstrip("/")
                # 从平台配置中提取路径前缀
                path_prefix = config.xget_prefix.split("/", 3)[-1].rstrip("/")
                accelerated_url = f"{base_url}/{path_prefix}/{parsed.netloc}{parsed.path}"
            else:
                # 使用平台配置中的前缀
                accelerated_url = f"{config.xget_prefix.rstrip('/')}{parsed.path}"

            # 保留查询参数
            if parsed.query:
                accelerated_url += f"?{parsed.query}"

            logger.debug(f"URL 转换: {url} -> {accelerated_url}")
            return accelerated_url
        except Exception as e:
            logger.error(f"URL 转换失败: {e}")
            return None

    def select_instance(self) -> XgetInstance | None:
        """
        选择一个可用的 Xget 实例。

        Returns:
            选中的 XgetInstance，或 None
        """
        # 过滤出可用的实例
        available = [inst for inst in self.instances if inst.is_available()]
        if not available:
            logger.warning("没有可用的 Xget 实例")
            return None

        strategy = self.config.get("load_balancing", "weighted_round_robin")

        if strategy == "priority":
            # 按优先级选择
            available.sort(key=lambda x: x.priority)
            return available[0]
        elif strategy == "random":
            # 随机选择
            return random.choice(available)
        else:  # weighted_round_robin
            # 加权轮询（简化版本）
            weighted = []
            for inst in available:
                weighted.extend([inst] * inst.weight)
            return random.choice(weighted)

    async def request(self, url: str, method: str = "GET", **kwargs) -> RequestResult:
        """
        发送请求，自动使用 Xget 加速，包含 fallback 机制。

        Args:
            url: 目标 URL
            method: HTTP 方法
            **kwargs: 其他请求参数

        Returns:
            RequestResult 对象
        """
        start_time = time.time()

        if not self.config.get("enabled", True):
            logger.debug("Xget 未启用，直接请求原始 URL")
            return await self._direct_request(url, method, **kwargs)

        # 识别平台
        platform, config = self.identify_platform(url)
        if not platform or not config:
            logger.debug(f"不支持的平台，直接请求: {url}")
            return await self._direct_request(url, method, **kwargs)

        # 尝试使用 Xget 实例
        max_retries = self.config.get("max_retries", 3)
        last_error = None

        for attempt in range(max_retries):
            instance = self.select_instance()
            if not instance:
                break

            accelerated_url = self.convert_url(url, instance.url)
            if not accelerated_url:
                break

            logger.info(f"尝试使用 Xget 加速 (尝试 {attempt + 1}/{max_retries}): {accelerated_url}")

            try:
                result = await self._make_request(accelerated_url, method, **kwargs)
                result.instance_used = instance.url

                if result.success:
                    instance.record_success()
                    return result
                else:
                    instance.record_failure()
                    last_error = result.error
                    logger.warning(f"Xget 加速请求失败: {result.error}")

            except Exception as e:
                instance.record_failure()
                last_error = str(e)
                logger.error(f"Xget 加速请求异常: {e}")

            # 等待重试
            if attempt < max_retries - 1:
                delay = self.config.get("retry_delay_seconds", 1.0) * (attempt + 1)
                time.sleep(delay)

        # Fallback 到原始 URL
        if self.config.get("fallback_enabled", True):
            logger.info(f"Xget 加速失败，fallback 到原始 URL: {url}")
            result = await self._direct_request(url, method, **kwargs)
            result.fallback_used = True
            return result
        else:
            # 不使用 fallback，返回失败
            return RequestResult(
                success=False,
                url=url,
                error=last_error or "所有 Xget 实例均失败",
                response_time=time.time() - start_time,
            )

    async def _make_request(self, url: str, method: str = "GET", **kwargs) -> RequestResult:
        """
        实际发送 HTTP 请求（需要 httpx 或 requests 库）。

        注意：此方法需要实际的 HTTP 客户端库。
        我们这里提供一个抽象实现，实际使用时需要根据项目依赖调整。
        """
        start_time = time.time()
        timeout = self.config.get("request_timeout_seconds", 30)

        try:
            # 尝试导入 httpx 或 requests
            client = None
            try:
                import httpx

                client = "httpx"
            except ImportError:
                try:
                    import requests

                    client = "requests"
                except ImportError:
                    logger.warning("未找到 HTTP 客户端库，请安装 httpx 或 requests")
                    return RequestResult(
                        success=False,
                        url=url,
                        error="缺少 HTTP 客户端库",
                        response_time=time.time() - start_time,
                    )

            # 发送请求
            if client == "httpx":
                import httpx

                async with httpx.AsyncClient(timeout=timeout) as http_client:
                    response = await http_client.request(method, url, **kwargs)
                    return RequestResult(
                        success=response.status_code < 400,
                        url=url,
                        content=response.content,
                        status_code=response.status_code,
                        response_time=time.time() - start_time,
                    )
            else:  # requests
                import requests

                response = requests.request(method, url, timeout=timeout, **kwargs)
                return RequestResult(
                    success=response.status_code < 400,
                    url=url,
                    content=response.content,
                    status_code=response.status_code,
                    response_time=time.time() - start_time,
                )

        except Exception as e:
            logger.error(f"HTTP 请求失败: {e}")
            return RequestResult(
                success=False,
                url=url,
                error=str(e),
                response_time=time.time() - start_time,
            )

    async def _direct_request(self, url: str, method: str = "GET", **kwargs) -> RequestResult:
        """直接请求原始 URL"""
        result = await self._make_request(url, method, **kwargs)
        result.fallback_used = False
        return result

    def get_status(self) -> dict[str, Any]:
        """获取 Xget 集成的状态信息"""
        available_count = sum(1 for inst in self.instances if inst.is_available())
        return {
            "enabled": self.config.get("enabled", True),
            "instances": {
                "total": len(self.instances),
                "available": available_count,
                "details": [
                    {
                        "url": inst.url,
                        "available": inst.is_available(),
                        "priority": inst.priority,
                        "weight": inst.weight,
                        "failure_count": inst.failure_count,
                        "last_used": inst.last_used,
                    }
                    for inst in self.instances
                ],
            },
            "platforms": {
                platform.value: config.enabled for platform, config in self.platform_configs.items()
            },
            "config": {
                "fallback_enabled": self.config.get("fallback_enabled"),
                "max_retries": self.config.get("max_retries"),
                "timeout": self.config.get("request_timeout_seconds"),
            },
        }


# ═══════════════════════════════════════════
#   便捷函数
# ═══════════════════════════════════════════

# 全局单例
_xget_instance: XgetIntegration | None = None


def get_xget(config: dict[str, Any] | None = None) -> XgetIntegration:
    """
    获取 Xget 集成单例。

    Args:
        config: 配置字典，可选

    Returns:
        XgetIntegration 实例
    """
    global _xget_instance
    if _xget_instance is None:
        _xget_instance = XgetIntegration(config)
    return _xget_instance


async def xget_request(url: str, method: str = "GET", **kwargs) -> RequestResult:
    """
    便捷函数：发送 Xget 加速请求。

    Args:
        url: 目标 URL
        method: HTTP 方法
        **kwargs: 其他请求参数

    Returns:
        RequestResult 对象
    """
    xget = get_xget()
    return await xget.request(url, method, **kwargs)


def xget_convert(url: str, instance_url: str | None = None) -> str | None:
    """
    便捷函数：转换 URL 为 Xget 加速 URL。

    Args:
        url: 原始 URL
        instance_url: 指定实例 URL，可选

    Returns:
        转换后的 URL
    """
    xget = get_xget()
    return xget.convert_url(url, instance_url)


# ═══════════════════════════════════════════
#   CLI 入口（用于测试）
# ═══════════════════════════════════════════


def main():
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("""
🚀 Xget 集成模块测试

用法:
  xget_integration.py convert <URL>  # 转换 URL
  xget_integration.py status          # 查看状态
  xget_integration.py test <URL>      # 测试请求
""")
        return

    action = sys.argv[1]
    xget = get_xget()

    if action == "convert" and len(sys.argv) > 2:
        url = sys.argv[2]
        converted = xget.convert_url(url)
        print(f"原始 URL: {url}")
        print(f"加速 URL: {converted or '不支持'}")
        platform, config = xget.identify_platform(url)
        if platform:
            print(f"平台: {platform.value} ({config.name})")

    elif action == "status":
        status = xget.get_status()
        import json

        print(json.dumps(status, indent=2, ensure_ascii=False))

    elif action == "test" and len(sys.argv) > 2:
        url = sys.argv[2]
        print(f"测试请求: {url}")

        async def run_test():
            result = await xget.request(url)
            print(f"\n结果: {'✅ 成功' if result.success else '❌ 失败'}")
            print(f"URL: {result.url}")
            if result.instance_used:
                print(f"使用实例: {result.instance_used}")
            if result.fallback_used:
                print("⚠️ Fallback 到原始 URL")
            if result.status_code:
                print(f"状态码: {result.status_code}")
            print(f"响应时间: {result.response_time:.2f}s")
            if result.error:
                print(f"错误: {result.error}")
            if result.content:
                print(f"内容长度: {len(result.content)} bytes")

        asyncio.run(run_test())

    else:
        print(f"未知命令: {action}")


if __name__ == "__main__":
    main()
