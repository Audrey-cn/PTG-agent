from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("prometheus.auth_manager")


@dataclass
class AuthProvider:
    name: str
    token: str
    created_at: float = 0.0
    last_used: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class AuthManager:
    """认证管理器 - 管理多提供商认证状态。

    支持 GitHub、Google、Anthropic 等多种认证提供商。
    """

    _instance: AuthManager | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._providers: dict[str, AuthProvider] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> AuthManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def add_provider(self, name: str, token: str, metadata: dict[str, Any] | None = None) -> bool:
        """添加认证提供商。

        Args:
            name: 提供商名称 (github, google, anthropic)
            token: 认证令牌
            metadata: 可选的元数据

        Returns:
            是否成功
        """
        import time

        with self._lock:
            self._providers[name] = AuthProvider(
                name=name,
                token=token,
                created_at=time.time(),
                metadata=metadata or {},
            )
            logger.info(f"Added auth provider: {name}")
            return True

    def remove_provider(self, name: str) -> bool:
        """移除认证提供商。

        Args:
            name: 提供商名称

        Returns:
            是否成功
        """
        with self._lock:
            if name in self._providers:
                del self._providers[name]
                logger.info(f"Removed auth provider: {name}")
                return True
            return False

    def get_provider(self, name: str) -> AuthProvider | None:
        """获取提供商信息。"""
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """列出所有已认证的提供商。"""
        with self._lock:
            return list(self._providers.keys())

    def get_token(self, name: str) -> str | None:
        """获取提供商的令牌。"""
        import time

        provider = self._providers.get(name)
        if provider:
            provider.last_used = time.time()
            return provider.token
        return None

    def reset_provider(self, name: str) -> bool:
        """重置单个提供商。"""
        return self.remove_provider(name)

    def reset_all(self) -> None:
        """重置所有提供商。"""
        with self._lock:
            self._providers.clear()
            logger.info("Reset all auth providers")

    def get_status(self) -> dict[str, Any]:
        """获取认证状态。"""
        import time

        with self._lock:
            providers = []
            for name, provider in self._providers.items():
                providers.append(
                    {
                        "name": name,
                        "created_at": provider.created_at,
                        "last_used": provider.last_used,
                        "age_seconds": int(time.time() - provider.created_at),
                    }
                )
            return {
                "total_providers": len(providers),
                "providers": providers,
            }


def get_auth_manager() -> AuthManager:
    """获取AuthManager单例。"""
    return AuthManager.get_instance()
