#!/usr/bin/env python3
"""Prometheus 消息平台扩展."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("prometheus.platforms")


@dataclass
class PlatformMessage:
    """平台消息"""

    message_id: str
    platform: str
    sender: str
    content: str
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class IRCPlatform:
    """IRC 平台适配器"""

    def __init__(self, server: str = "irc.libera.chat", port: int = 6697, ssl: bool = True):
        self.server = server
        self.port = port
        self.ssl = ssl
        self._connected = False
        self._channels: list[str] = []

    async def connect(self, nickname: str, username: str = None, realname: str = None):
        """连接到 IRC 服务器"""
        self._nickname = nickname
        self._username = username or nickname
        self._realname = realname or nickname

        try:
            import socket
            import ssl as ssl_module

            if self.ssl:
                context = ssl_module.create_default_context()
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket = context.wrap_socket(self._socket)
            else:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            self._socket.connect((self.server, self.port))

            self._send(f"NICK {self._nickname}")
            self._send(f"USER {self._username} 0 * :{self._realname}")

            self._connected = True
            logger.info(f"Connected to IRC server: {self.server}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to connect to IRC: {e}")
            raise

    def _send(self, message: str):
        """发送原始消息"""
        if self._socket:
            self._socket.sendall(f"{message}\r\n".encode())

    async def join_channel(self, channel: str):
        """加入频道"""
        if not channel.startswith("#"):
            channel = f"#{channel}"

        self._send(f"JOIN {channel}")
        self._channels.append(channel)
        logger.info(f"Joined channel: {channel}")

    async def send_message(self, channel: str, content: str):
        """发送消息到频道"""
        if not channel.startswith("#"):
            channel = f"#{channel}"

        self._send(f"PRIVMSG {channel} :{content}")
        logger.info(f"Sent message to {channel}: {content[:50]}")

    async def disconnect(self):
        """断开连接"""
        if self._connected:
            self._send("QUIT :Goodbye")
            self._socket.close()
            self._connected = False
            logger.info("Disconnected from IRC")

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected


class LINEPlatform:
    """LINE 平台适配器"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._connected = True

    async def send_message(self, to: str, content: str):
        """发送消息"""
        try:
            import aiohttp

            url = "https://api.line.me/v2/bot/message/push"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            }

            payload = {
                "to": to,
                "messages": [{"type": "text", "text": content}],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Message sent to LINE user {to}")
                        return True
                    else:
                        logger.error(f"Failed to send LINE message: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"LINE API error: {e}")
            return False

    async def get_profile(self, user_id: str) -> dict[str, Any] | None:
        """获取用户资料"""
        try:
            import aiohttp

            url = f"https://api.line.me/v2/bot/profile/{user_id}"
            headers = {"Authorization": f"Bearer {self.access_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    return None

        except Exception as e:
            logger.error(f"LINE profile error: {e}")
            return None


class ZaloPlatform:
    """Zalo 平台适配器"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._base_url = "https://openapi.zalo.me/v2.0"

    async def send_message(self, to: str, content: str):
        """发送消息"""
        try:
            import aiohttp

            url = f"{self._base_url}/message/text"
            headers = {
                "Content-Type": "application/json",
                "access_token": self.access_token,
            }

            payload = {
                "recipient": {"user_id": to},
                "message": {"text": content},
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("error") == 0:
                            logger.info(f"Message sent to Zalo user {to}")
                            return True
                    logger.error("Failed to send Zalo message")
                    return False

        except Exception as e:
            logger.error(f"Zalo API error: {e}")
            return False

    async def get_user_info(self, user_id: str) -> dict[str, Any] | None:
        """获取用户信息"""
        try:
            import aiohttp

            url = f"{self._base_url}/user/profile"
            headers = {"access_token": self.access_token}
            params = {"user_id": user_id}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    return None

        except Exception as e:
            logger.error(f"Zalo user info error: {e}")
            return None


class PlatformRegistry:
    """平台注册表"""

    _instance = None
    _platforms: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._platforms = {
                "irc": IRCPlatform,
                "line": LINEPlatform,
                "zalo": ZaloPlatform,
            }
        return cls._instance

    def register_platform(self, name: str, platform_class: Any):
        """注册平台"""
        self._platforms[name] = platform_class

    def get_platform(self, name: str) -> Any | None:
        """获取平台类"""
        return self._platforms.get(name)

    def create_platform(self, name: str, **kwargs) -> Any | None:
        """创建平台实例"""
        platform_class = self.get_platform(name)
        if platform_class:
            return platform_class(**kwargs)
        return None

    def list_platforms(self) -> list[str]:
        """列出所有平台"""
        return list(self._platforms.keys())


def register_extended_platforms():
    """注册扩展平台"""
    PlatformRegistry()

    from prometheus.channels.registry import channel_registry

    channel_registry.register("irc", IRCPlatform)
    channel_registry.register("line", LINEPlatform)
    channel_registry.register("zalo", ZaloPlatform)

    logger.info("Extended platforms registered: irc, line, zalo")


if __name__ == "__main__":
    print("📡 Extended Message Platforms")
    print("=" * 50)

    registry = PlatformRegistry()
    print(f"Available platforms: {', '.join(registry.list_platforms())}")

    print("\nIRC Platform:")
    print("  Requires: irc library")
    print("  Usage: IRCPlatform(server='irc.libera.chat', port=6697)")

    print("\nLINE Platform:")
    print("  Requires: LINE Bot API access token")
    print("  Usage: LINEPlatform(access_token='your-token')")

    print("\nZalo Platform:")
    print("  Requires: Zalo OpenAPI access token")
    print("  Usage: ZaloPlatform(access_token='your-token')")
