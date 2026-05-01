from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PlatformEntry:
    name: str
    label: str
    adapter_factory: Callable[[], Any] | None = None
    check_fn: Callable[[], bool] | None = None
    validate_config: Callable[[dict], list[str]] | None = None
    required_env: list[str] = field(default_factory=list)
    install_hint: str = ""


class PlatformRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, PlatformEntry] = {}

    def register(self, entry: PlatformEntry) -> None:
        self._entries[entry.name] = entry

    def get(self, name: str) -> PlatformEntry | None:
        return self._entries.get(name)

    def create_adapter(self, name: str, config: dict | None = None) -> Any:
        entry = self._entries.get(name)
        if not entry:
            raise ValueError(f"Unknown platform: {name}")
        if entry.adapter_factory:
            return entry.adapter_factory()
        return None

    def list_platforms(self) -> list[str]:
        return list(self._entries.keys())

    def is_available(self, name: str) -> bool:
        entry = self._entries.get(name)
        if not entry:
            return False
        if entry.check_fn:
            return entry.check_fn()
        for env_var in entry.required_env:
            import os
            if not os.environ.get(env_var):
                return False
        return True

    def validate_platform(self, name: str, config: dict) -> list[str]:
        entry = self._entries.get(name)
        if not entry:
            return [f"Unknown platform: {name}"]
        errors: list[str] = []
        for env_var in entry.required_env:
            import os
            if not os.environ.get(env_var):
                errors.append(f"Missing environment variable: {env_var}")
        if entry.validate_config:
            errors.extend(entry.validate_config(config))
        return errors


platform_registry = PlatformRegistry()


def _register_builtin_platforms() -> None:
    def _check_cli() -> bool:
        return True

    platform_registry.register(PlatformEntry(
        name="cli",
        label="Command Line Interface",
        check_fn=_check_cli,
        required_env=[],
        install_hint="Built-in platform, always available",
    ))

    def _check_telegram() -> bool:
        import os
        return bool(os.environ.get("TELEGRAM_BOT_TOKEN"))

    platform_registry.register(PlatformEntry(
        name="telegram",
        label="Telegram Bot",
        check_fn=_check_telegram,
        required_env=["TELEGRAM_BOT_TOKEN"],
        install_hint="Set TELEGRAM_BOT_TOKEN environment variable",
    ))

    def _check_discord() -> bool:
        import os
        return bool(os.environ.get("DISCORD_BOT_TOKEN"))

    platform_registry.register(PlatformEntry(
        name="discord",
        label="Discord Bot",
        check_fn=_check_discord,
        required_env=["DISCORD_BOT_TOKEN"],
        install_hint="Set DISCORD_BOT_TOKEN environment variable",
    ))

    def _check_slack() -> bool:
        import os
        return bool(os.environ.get("SLACK_BOT_TOKEN"))

    platform_registry.register(PlatformEntry(
        name="slack",
        label="Slack Bot",
        check_fn=_check_slack,
        required_env=["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"],
        install_hint="Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN environment variables",
    ))

    def _check_webhook() -> bool:
        return True

    platform_registry.register(PlatformEntry(
        name="webhook",
        label="HTTP Webhook",
        check_fn=_check_webhook,
        required_env=[],
        install_hint="Built-in platform for HTTP webhooks",
    ))

    def _check_matrix() -> bool:
        import os
        return bool(os.environ.get("MATRIX_ACCESS_TOKEN"))

    platform_registry.register(PlatformEntry(
        name="matrix",
        label="Matrix",
        check_fn=_check_matrix,
        required_env=["MATRIX_ACCESS_TOKEN", "MATRIX_HOMESERVER"],
        install_hint="Set MATRIX_ACCESS_TOKEN and MATRIX_HOMESERVER environment variables",
    ))

    def _check_wechat() -> bool:
        import os
        return bool(os.environ.get("WECHAT_APP_ID"))

    platform_registry.register(PlatformEntry(
        name="wechat",
        label="WeChat",
        check_fn=_check_wechat,
        required_env=["WECHAT_APP_ID", "WECHAT_APP_SECRET"],
        install_hint="Set WECHAT_APP_ID and WECHAT_APP_SECRET environment variables",
    ))

    def _check_feishu() -> bool:
        import os
        return bool(os.environ.get("FEISHU_APP_ID"))

    platform_registry.register(PlatformEntry(
        name="feishu",
        label="Feishu",
        check_fn=_check_feishu,
        required_env=["FEISHU_APP_ID", "FEISHU_APP_SECRET"],
        install_hint="Set FEISHU_APP_ID and FEISHU_APP_SECRET environment variables",
    ))

    def _check_dingtalk() -> bool:
        import os
        return bool(os.environ.get("DINGTALK_APP_KEY"))

    platform_registry.register(PlatformEntry(
        name="dingtalk",
        label="DingTalk",
        check_fn=_check_dingtalk,
        required_env=["DINGTALK_APP_KEY", "DINGTALK_APP_SECRET"],
        install_hint="Set DINGTALK_APP_KEY and DINGTALK_APP_SECRET environment variables",
    ))


_register_builtin_platforms()
