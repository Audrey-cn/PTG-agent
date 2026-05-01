from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

PLATFORM_EMOJIS = {
    "telegram": "📱",
    "discord": "🎮",
    "feishu": "🪽",
    "feishu_comment": "💬",
    "dingtalk": "📌",
    "wecom": "💼",
    "wecom_callback": "🔗",
    "slack": "💬",
    "slack_events": "📨",
    "slack_socket": "🔌",
    "mattermost": "📋",
    "mattermost_slash": "⚡",
    "qq": "🐧",
    "yuanbao": "💎",
    "homeassistant": "🏠",
    "wechat": "💚",
    "whatsapp": "📞",
    "signal": "🔐",
    "email": "📧",
    "sms": "📲",
    "matrix": "🧱",
    "webhook": "🪝",
}


def detect_platform_from_config(config: dict) -> str:
    if "platform" in config:
        return config["platform"]
    if "bot_token" in config:
        if "app_token" in config:
            return "slack_socket"
        if "signing_secret" in config:
            return "slack_events"
        if "allowed_updates" in config:
            return "telegram"
        return "slack"
    if "app_id" in config and "app_secret" in config:
        if "verification_token" in config:
            return "feishu"
        return "feishu"
    if "corp_id" in config and "corp_secret" in config:
        if "wecom_token" in config:
            return "wecom_callback"
        return "wecom"
    if "webhook_url" in config:
        if "webhook_secret" in config:
            return "mattermost_slash"
        return "webhook"
    if "ha_url" in config and "access_token" in config:
        return "homeassistant"
    if "ws_url" in config and "bot_qq" in config:
        return "qq"
    if "api_key" in config and "api_base" in config:
        if "yuanbao" in config.get("api_base", ""):
            return "yuanbao"
    return "unknown"


def validate_platform_config(platform: str, config: dict) -> tuple[bool, str]:
    if not config:
        return False, "配置为空"
    platform_validators = {
        "telegram": _validate_telegram,
        "discord": _validate_discord,
        "feishu": _validate_feishu,
        "feishu_comment": _validate_feishu,
        "dingtalk": _validate_dingtalk,
        "wecom": _validate_wecom,
        "wecom_callback": _validate_wecom_callback,
        "slack": _validate_slack,
        "slack_events": _validate_slack_events,
        "slack_socket": _validate_slack_socket,
        "mattermost_slash": _validate_mattermost_slash,
        "qq": _validate_qq,
        "yuanbao": _validate_yuanbao,
        "homeassistant": _validate_homeassistant,
    }
    validator = platform_validators.get(platform)
    if validator:
        return validator(config)
    return True, f"平台 {platform} 无特定验证规则"


def _validate_telegram(config: dict) -> tuple[bool, str]:
    if not config.get("bot_token"):
        return False, "Telegram 需要 bot_token"
    return True, "配置有效"


def _validate_discord(config: dict) -> tuple[bool, str]:
    if not config.get("bot_token"):
        return False, "Discord 需要 bot_token"
    return True, "配置有效"


def _validate_feishu(config: dict) -> tuple[bool, str]:
    if not config.get("app_id"):
        return False, "飞书需要 app_id"
    if not config.get("app_secret"):
        return False, "飞书需要 app_secret"
    return True, "配置有效"


def _validate_dingtalk(config: dict) -> tuple[bool, str]:
    if not config.get("webhook_url") and not config.get("app_key"):
        return False, "钉钉需要 webhook_url 或 app_key"
    return True, "配置有效"


def _validate_wecom(config: dict) -> tuple[bool, str]:
    if not config.get("corp_id"):
        return False, "企业微信需要 corp_id"
    if not config.get("corp_secret") and not config.get("webhook_url"):
        return False, "企业微信需要 corp_secret 或 webhook_url"
    return True, "配置有效"


def _validate_wecom_callback(config: dict) -> tuple[bool, str]:
    if not config.get("wecom_token"):
        return False, "企业微信回调需要 wecom_token"
    if not config.get("wecom_encoding_aes_key"):
        return False, "企业微信回调需要 wecom_encoding_aes_key"
    return True, "配置有效"


def _validate_slack(config: dict) -> tuple[bool, str]:
    if not config.get("bot_token"):
        return False, "Slack 需要 bot_token"
    return True, "配置有效"


def _validate_slack_events(config: dict) -> tuple[bool, str]:
    if not config.get("bot_token"):
        return False, "Slack Events 需要 bot_token"
    if not config.get("signing_secret"):
        return False, "Slack Events 需要 signing_secret"
    return True, "配置有效"


def _validate_slack_socket(config: dict) -> tuple[bool, str]:
    if not config.get("bot_token"):
        return False, "Slack Socket 需要 bot_token"
    if not config.get("app_token"):
        return False, "Slack Socket 需要 app_token"
    return True, "配置有效"


def _validate_mattermost_slash(config: dict) -> tuple[bool, str]:
    if not config.get("webhook_url"):
        return False, "Mattermost Slash 需要 webhook_url"
    return True, "配置有效"


def _validate_qq(config: dict) -> tuple[bool, str]:
    if not config.get("access_token") and not config.get("ws_url"):
        return False, "QQ Bot 需要 access_token 或 ws_url"
    return True, "配置有效"


def _validate_yuanbao(config: dict) -> tuple[bool, str]:
    if not config.get("api_key"):
        return False, "元宝需要 api_key"
    return True, "配置有效"


def _validate_homeassistant(config: dict) -> tuple[bool, str]:
    if not config.get("ha_url"):
        return False, "Home Assistant 需要 ha_url"
    if not config.get("access_token"):
        return False, "Home Assistant 需要 access_token"
    return True, "配置有效"


def get_platform_emoji(platform: str) -> str:
    return PLATFORM_EMOJIS.get(platform, "❓")


def format_platform_status(platform: str, status: str) -> str:
    emoji = get_platform_emoji(platform)
    status_map = {
        "started": "✅",
        "stopped": "⏹️",
        "error": "❌",
        "pending": "⏳",
    }
    status_icon = status_map.get(status, "❓")
    return f"{emoji} {platform}: {status_icon} {status}"
