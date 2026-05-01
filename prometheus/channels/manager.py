"""Prometheus 频道管理器."""

from dataclasses import dataclass
from enum import Enum

from prometheus.config import PrometheusConfig

from .base import (
    Channel,
    ChannelConfig,
    ChannelType,
    CLIChannel,
    FileWatchChannel,
    HTTPWebhookChannel,
)
from .registry import (
    get_channel_registry,
)


class PlatformType(Enum):
    """支持的平台类型"""

    CLI = "cli"
    HTTP_WEBHOOK = "http_webhook"
    FILE_WATCH = "file_watch"
    # 第三方平台
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    QQBOT = "qqbot"
    WECOM = "wecom"
    WEB_SOCKET = "web_socket"
    MQTT = "mqtt"


@dataclass
class PlatformInfo:
    """平台信息"""

    type: PlatformType
    name: str
    description: str
    config_key: str
    dependencies: list[str]
    enabled: bool = False
    requires_config: list[str] = None

    def __post_init__(self):
        if self.requires_config is None:
            self.requires_config = []


# 平台元数据
PLATFORMS = [
    # 基础平台
    PlatformInfo(
        PlatformType.CLI,
        "命令行",
        "默认的交互式命令行",
        "cli",
        [],
        True,
    ),
    PlatformInfo(
        PlatformType.HTTP_WEBHOOK,
        "HTTP Webhook",
        "HTTP API 接口",
        "http_webhook",
        ["fastapi", "uvicorn"],
    ),
    PlatformInfo(
        PlatformType.FILE_WATCH,
        "文件监听",
        "监听文件变化",
        "file_watch",
        ["watchdog"],
    ),
    # 第三方平台
    PlatformInfo(
        PlatformType.TELEGRAM,
        "Telegram",
        "Telegram 机器人",
        "telegram",
        ["python-telegram-bot"],
    ),
    PlatformInfo(
        PlatformType.DISCORD,
        "Discord",
        "Discord 机器人",
        "discord",
        ["discord.py"],
    ),
    PlatformInfo(
        PlatformType.SLACK,
        "Slack",
        "Slack 机器人",
        "slack",
        ["slack-bolt", "slack-sdk"],
    ),
    PlatformInfo(
        PlatformType.FEISHU,
        "飞书",
        "飞书机器人",
        "feishu",
        ["lark-oapi"],
    ),
    PlatformInfo(
        PlatformType.DINGTALK,
        "钉钉",
        "钉钉机器人",
        "dingtalk",
        ["dingtalk-stream", "dingtalk-sdk"],
    ),
    PlatformInfo(
        PlatformType.QQBOT,
        "QQ",
        "QQ 机器人",
        "qqbot",
        [],
    ),
    PlatformInfo(
        PlatformType.WECOM,
        "企业微信",
        "企业微信机器人",
        "wecom",
        [],
    ),
    PlatformInfo(
        PlatformType.WEB_SOCKET,
        "WebSocket",
        "WebSocket 接口",
        "web_socket",
        [],
    ),
    PlatformInfo(
        PlatformType.MQTT,
        "MQTT",
        "MQTT 订阅",
        "mqtt",
        [],
    ),
]


class ChannelManager:
    """频道管理器"""

    def __init__(self, config: PrometheusConfig = None):
        self.config = config or PrometheusConfig.load()
        self.registry = get_channel_registry()
        self.platforms = {p.type: p for p in PLATFORMS}

    def get_platform_info(self, platform_type: PlatformType) -> PlatformInfo | None:
        """获取平台信息"""
        return self.platforms.get(platform_type)

    def get_enabled_platforms(self) -> list[PlatformInfo]:
        """获取所有启用的平台"""
        enabled = []
        for p in PLATFORMS:
            cfg = self.config.get(f"channels.{p.config_key}", {})
            if cfg.get("enabled", False):
                p.enabled = True
                enabled.append(p)
            elif p.type == PlatformType.CLI:
                # CLI 总是默认启用
                p.enabled = True
                enabled.append(p)
        return enabled

    def get_available_platforms(self) -> list[PlatformInfo]:
        """获取所有可用平台"""
        return list(PLATFORMS)

    def create_channel(self, platform_type: PlatformType, name: str = None) -> Channel | None:
        """创建频道"""
        platform = self.get_platform_info(platform_type)
        if not platform:
            return None

        cfg = self.config.get(f"channels.{platform.config_key}", {})

        if not cfg.get("enabled", False) and platform_type != PlatformType.CLI:
            print(f"⚠️ 平台 {platform.name} 未启用，需要在 config.yaml 中启用")
            return None

        # 检查依赖
        if platform.dependencies:
            missing = []
            for dep in platform.dependencies:
                try:
                    __import__(dep)
                except ImportError:
                    missing.append(dep)
            if missing:
                print(f"⚠️ 平台 {platform.name} 需要依赖: {', '.join(missing)}")
                print(f"   请运行: pip install {' '.join(missing)}")
                return None

        # 创建频道
        try:
            if platform_type == PlatformType.CLI:
                config = ChannelConfig(
                    ChannelType.CLI,
                    name or "cli",
                    True,
                    cfg,
                )
                return CLIChannel(config)
            elif platform_type == PlatformType.HTTP_WEBHOOK:
                config = ChannelConfig(
                    ChannelType.HTTP_WEBHOOK,
                    name or "webhook",
                    cfg.get("enabled", True),
                    cfg,
                )
                return HTTPWebhookChannel(config)
            elif platform_type == PlatformType.FILE_WATCH:
                config = ChannelConfig(
                    ChannelType.FILE_WATCH,
                    name or "file_watch",
                    cfg.get("enabled", False),
                    cfg,
                )
                return FileWatchChannel(config)
            else:
                # 平台 Adapter
                from .platforms import (
                    DingtalkAdapter,
                    DiscordAdapter,
                    FeishuAdapter,
                    TelegramAdapter,
                )

                channel_config = ChannelConfig(
                    ChannelType.HTTP_WEBHOOK,  # 通用类型
                    name or platform.config_key,
                    cfg.get("enabled", False),
                    cfg,
                )
                if platform_type == PlatformType.TELEGRAM:
                    return TelegramAdapter(channel_config)
                elif platform_type == PlatformType.DISCORD:
                    return DiscordAdapter(channel_config)
                elif platform_type == PlatformType.FEISHU:
                    return FeishuAdapter(channel_config)
                elif platform_type == PlatformType.DINGTALK:
                    return DingtalkAdapter(channel_config)
                else:
                    # 其他平台返回占位提示
                    print(f"ℹ️ 平台 {platform.name} 适配器待实现，配置已启用")
                    return None
        except Exception as e:
            print(f"❌ 创建 {platform.name} 失败: {e}")
            import traceback

            traceback.print_exc()
            return None

    def select_platform_menu(self) -> PlatformType | None:
        """显示平台选择菜单"""
        print("\n" + "=" * 60)
        print("🔥 Prometheus 频道选择")
        print("=" * 60)
        print("\n可用平台:")

        enabled = self.get_enabled_platforms()
        available = self.get_available_platforms()

        print(f"\n📋 已启用平台: {len(enabled)} 个")
        for i, p in enumerate(enabled, 1):
            status = "✅" if p.enabled else "⬜"
            print(f"  {i}. {status} {p.name} - {p.description}")

        print(f"\n📋 全部平台: {len(available)} 个")
        for i, p in enumerate(available, 1):
            status = "✅" if p in enabled else "⬜"
            print(f"  {i}. {status} {p.name} - {p.description}")

        print("\n0. 退出")
        print("=" * 60)
        choice = input("\n请选择平台编号: ").strip()

        if choice == "0":
            return None
        try:
            idx = int(choice)
            if 1 <= idx <= len(available):
                return available[idx - 1].type
            elif 1 <= idx <= len(enabled):
                return enabled[idx - 1].type
            else:
                print("⚠️ 无效的选择")
                return None
        except ValueError:
            print("⚠️ 无效的输入")
            return None


# 全局单例
_channel_manager: ChannelManager | None = None


def get_channel_manager() -> ChannelManager:
    """获取频道管理器"""
    global _channel_manager
    if _channel_manager is None:
        _channel_manager = ChannelManager()
    return _channel_manager
