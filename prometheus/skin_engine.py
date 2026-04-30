
"""
Prometheus 史诗级皮肤引擎

主题配置系统，管理配色、emoji、品牌标识和旋转动画
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


@dataclass
class SkinConfig:
    """Prometheus 皮肤配置"""
    name: str
    description: str = ""
    colors: Dict[str, str] = field(default_factory=dict)
    spinner: Dict[str, Any] = field(default_factory=dict)
    branding: Dict[str, str] = field(default_factory=dict)
    tool_prefix: str = "┊"
    tool_emojis: Dict[str, str] = field(default_factory=dict)

    def get_color(self, key, fallback=""):
        """获取颜色配置，带默认值"""
        return self.colors.get(key, fallback)

    def get_spinner_wings(self):
        """获取旋转器的装饰"""
        raw = self.spinner.get("wings", [])
        result = []
        for pair in raw:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                result.append((str(pair[0]), str(pair[1])))
        return result

    def get_branding(self, key, fallback=""):
        """获取品牌配置，带默认值"""
        return self.branding.get(key, fallback)


# 内置皮肤定义
_BUILTIN_SKINS = {
    "default": {
        "name": "default",
        "description": "Prometheus 经典金焰主题",
        "colors": {
            "banner_border": "#CD7F32",
            "banner_title": "#FFD700",
            "banner_accent": "#FF8C00",
            "banner_dim": "#B8860B",
            "banner_text": "#FFF8DC",
            "ui_accent": "#FFD700",
            "ui_label": "#DAA520",
            "ui_ok": "#4caf50",
            "ui_error": "#ef5350",
            "ui_warn": "#ffa726",
        },
        "spinner": {
            "waiting_faces": ["(🔥)", "(✦)", "(⚡)", "(✧)", "(★)"],
            "thinking_faces": ["(🔥)", "(⚡)", "(✦)", "(⌁)", "(✧)"],
            "thinking_verbs": [
                "forging wisdom", "tending the flame", "reading the omens",
                "carrying the torch", "shaping the future", "stoking the fire",
                "weaving destiny", "illuminating the path",
            ],
        },
        "branding": {
            "agent_name": "Prometheus Agent",
            "welcome": "Welcome to Prometheus! 🔥 Type your message or /help for commands.",
            "goodbye": "The fire burns eternal! 🔥",
            "response_label": " 🔥 Prometheus ",
            "prompt_symbol": "❯ ",
            "help_header": "(🔥) Epic Commands",
        },
        "tool_prefix": "┊",
        "tool_emojis": {
            "stamp_seed": "🔥",
            "trace_seed": "🔍",
            "append_historical_note": "📜",
            "inspect_seed": "🔬",
            "list_stamps": "📋",
        },
    },
    "zeus": {
        "name": "zeus",
        "description": "宙斯雷霆主题",
        "colors": {
            "banner_border": "#4169E1",
            "banner_title": "#87CEEB",
            "banner_accent": "#00BFFF",
            "banner_dim": "#1E90FF",
            "banner_text": "#F0F8FF",
            "ui_accent": "#87CEEB",
            "ui_label": "#4169E1",
            "ui_ok": "#32CD32",
            "ui_error": "#FF4500",
            "ui_warn": "#FFD700",
        },
        "spinner": {
            "waiting_faces": ["(⚡)", "(☁)", "(⛈)", "(✦)", "(△)"],
            "thinking_faces": ["(⚡)", "(⛈)", "(☁)", "(⌁)", "(△)"],
            "thinking_verbs": [
                "summoning lightning", "commanding the skies", "reading the clouds",
                "hurling thunder", "ruling Olympus", "directing storms",
                "weighing fates", "shaking the heavens",
            ],
            "wings": [
                ["⟪⚡", "⚡⟫"],
                ["⟪☁", "☁⟫"],
                ["⟪⛈", "⛈⟫"],
                ["⟪✦", "✦⟫"],
            ],
        },
        "branding": {
            "agent_name": "Zeus Agent",
            "welcome": "Welcome to Olympus! ⚡ Type your message or /help for commands.",
            "goodbye": "May lightning strike true! ⚡",
            "response_label": " ⚡ Zeus ",
            "prompt_symbol": "⚡ ❯ ",
            "help_header": "(⚡) Thunder Commands",
        },
        "tool_prefix": "│",
        "tool_emojis": {
            "stamp_seed": "⚡",
            "trace_seed": "🔍",
            "append_historical_note": "📜",
            "inspect_seed": "🔬",
            "list_stamps": "📋",
        },
    },
    "athena": {
        "name": "athena",
        "description": "雅典娜智慧主题",
        "colors": {
            "banner_border": "#6B8E23",
            "banner_title": "#90EE90",
            "banner_accent": "#32CD32",
            "banner_dim": "#556B2F",
            "banner_text": "#F5FFFA",
            "ui_accent": "#90EE90",
            "ui_label": "#6B8E23",
            "ui_ok": "#228B22",
            "ui_error": "#B22222",
            "ui_warn": "#DAA520",
        },
        "spinner": {
            "waiting_faces": ["(♀)", "(✿)", "(📚)", "(✦)", "(◎)"],
            "thinking_faces": ["(♀)", "(📚)", "(✿)", "(⌁)", "(◎)"],
            "thinking_verbs": [
                "contemplating strategy", "weaving wisdom", "shaping reason",
                "charting victory", "guiding the mind", "aligning thought",
                "fostering insight", "clarifying vision",
            ],
        },
        "branding": {
            "agent_name": "Athena Agent",
            "welcome": "Welcome to wisdom! ♀ Type your message or /help for commands.",
            "goodbye": "Wisdom goes with you! ♀",
            "response_label": " ♀ Athena ",
            "prompt_symbol": "♀ ❯ ",
            "help_header": "(♀) Wise Commands",
        },
        "tool_prefix": "│",
        "tool_emojis": {
            "stamp_seed": "♀",
            "trace_seed": "🔍",
            "append_historical_note": "📜",
            "inspect_seed": "🔬",
            "list_stamps": "📋",
        },
    },
    "hades": {
        "name": "hades",
        "description": "冥界暗黑主题",
        "colors": {
            "banner_border": "#4B0082",
            "banner_title": "#9370DB",
            "banner_accent": "#8A2BE2",
            "banner_dim": "#2F0047",
            "banner_text": "#E6E6FA",
            "ui_accent": "#9370DB",
            "ui_label": "#4B0082",
            "ui_ok": "#32CD32",
            "ui_error": "#DC143C",
            "ui_warn": "#FFD700",
        },
        "spinner": {
            "waiting_faces": ["(💀)", "(🖤)", "(✦)", "(◇)", "(⋄)"],
            "thinking_faces": ["(💀)", "(✦)", "(🖤)", "(⌁)", "(◇)"],
            "thinking_verbs": [
                "guiding departed souls", "weighing in shadow", "unveiling the under",
                "forging in darkness", "ruling the underworld", "commanding shades",
                "binding the Styx", "deepening silence",
            ],
            "wings": [
                ["⟪💀", "💀⟫"],
                ["⟪🖤", "🖤⟫"],
                ["⟪✦", "✦⟫"],
                ["⟪◇", "◇⟫"],
            ],
        },
        "branding": {
            "agent_name": "Hades Agent",
            "welcome": "Welcome to the Underworld! 💀 Type your message or /help for commands.",
            "goodbye": "May your soul find peace! 💀",
            "response_label": " 💀 Hades ",
            "prompt_symbol": "💀 ❯ ",
            "help_header": "(💀) Underworld Commands",
        },
        "tool_prefix": "╎",
        "tool_emojis": {
            "stamp_seed": "💀",
            "trace_seed": "🔍",
            "append_historical_note": "📜",
            "inspect_seed": "🔬",
            "list_stamps": "📋",
        },
    },
}


# 全局皮肤状态
_active_skin = None
_active_skin_name = "default"


def _build_skin_config(data):
    """从原始数据构建皮肤配置"""
    default = _BUILTIN_SKINS["default"]
    colors = dict(default.get("colors", {}))
    colors.update(data.get("colors", {}))
    spinner = dict(default.get("spinner", {}))
    spinner.update(data.get("spinner", {}))
    branding = dict(default.get("branding", {}))
    branding.update(data.get("branding", {}))

    tool_emojis = dict(default.get("tool_emojis", {}))
    tool_emojis.update(data.get("tool_emojis", {}))

    return SkinConfig(
        name=data.get("name", "unknown"),
        description=data.get("description", ""),
        colors=colors,
        spinner=spinner,
        branding=branding,
        tool_prefix=data.get("tool_prefix", default.get("tool_prefix", "┊")),
        tool_emojis=tool_emojis,
    )


def list_skins():
    """列出所有可用皮肤"""
    return [
        {
            "name": name,
            "description": data.get("description", ""),
            "source": "builtin"
        }
        for name, data in _BUILTIN_SKINS.items()
    ]


def load_skin(name):
    """加载指定名称的皮肤"""
    if name in _BUILTIN_SKINS:
        return _build_skin_config(_BUILTIN_SKINS[name])
    logger.warning("Skin '%s' not found, using default", name)
    return _build_skin_config(_BUILTIN_SKINS["default"])


def get_active_skin():
    """获取当前激活的皮肤"""
    global _active_skin
    if _active_skin is None:
        _active_skin = load_skin(_active_skin_name)
    return _active_skin


def set_active_skin(name):
    """切换激活的皮肤"""
    global _active_skin, _active_skin_name
    _active_skin_name = name
    _active_skin = load_skin(name)
    return _active_skin


def get_active_skin_name():
    """获取当前皮肤名称"""
    return _active_skin_name


def init_skin_from_config(config):
    """从配置初始化皮肤"""
    display = config.get("display") or {}
    if not isinstance(display, dict):
        display = {}
    skin_name = display.get("skin", "default")
    if isinstance(skin_name, str) and skin_name.strip():
        set_active_skin(skin_name.strip())
    else:
        set_active_skin("default")


# 便捷函数
def get_active_prompt_symbol(fallback="❯ "):
    """获取提示符"""
    try:
        return get_active_skin().get_branding("prompt_symbol", fallback)
    except Exception:
        return fallback


def get_active_help_header(fallback="(🔥) Epic Commands"):
    """获取帮助头"""
    try:
        return get_active_skin().get_branding("help_header", fallback)
    except Exception:
        return fallback


def get_active_goodbye(fallback="The fire burns eternal! 🔥"):
    """获取告别语"""
    try:
        return get_active_skin().get_branding("goodbye", fallback)
    except Exception:
        return fallback


def get_active_response_label(fallback=" 🔥 Prometheus "):
    """获取回复标签"""
    try:
        return get_active_skin().get_branding("response_label", fallback)
    except Exception:
        return fallback


def get_active_welcome(fallback="Welcome to Prometheus! 🔥"):
    """获取欢迎语"""
    try:
        return get_active_skin().get_branding("welcome", fallback)
    except Exception:
        return fallback


def get_tool_prefix():
    """获取工具前缀"""
    try:
        return get_active_skin().tool_prefix
    except Exception:
        return "┊"

