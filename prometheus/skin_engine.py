
"""
Prometheus 史诗级皮肤引擎
主题配置系统，管理配色、emoji、品牌标识和旋转动画
"""
import logging

logger = logging.getLogger(__name__)


class SkinConfig:
    """Prometheus 皮肤配置"""
    def __init__(self):
        self.name = ""
        self.description = ""
        self.colors = {}
        self.spinner = {}
        self.branding = {}
        self.tool_prefix = "┊"
        self.tool_emojis = {}

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
        "tool_prefix": "│",
        "tool_emojis": {
            "stamp_seed": "⚡",
        },
    },
    "athena": {
        "name": "athena",
        "description": "雅典娜智慧主题",
        "tool_prefix": "│",
        "tool_emojis": {
            "stamp_seed": "♀",
        },
    },
    "hades": {
        "name": "hades",
        "description": "冥界暗黑主题",
        "tool_prefix": "╎",
        "tool_emojis": {
            "stamp_seed": "💀",
        },
    },
}


_active_skin = None
_active_skin_name = "default"


def _build_skin_config(data):
    """从原始数据构建皮肤配置"""
    default = _BUILTIN_SKINS["default"]
    skin = SkinConfig()
    skin.name = data.get("name", default["name"])
    skin.description = data.get("description", default["description"])
    skin.tool_prefix = data.get("tool_prefix", default["tool_prefix"])
    skin.tool_emojis = dict(default.get("tool_emojis", {}))
    if data.get("tool_emojis"):
        skin.tool_emojis.update(data.get("tool_emojis", {}))
    return skin


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


def get_active_prompt_symbol(fallback="❯ "):
    """获取提示符"""
    try:
        return get_active_skin().get_branding("prompt_symbol", fallback)
    except Exception:
        return fallback


def get_active_tool_prefix():
    """获取工具前缀"""
    try:
        return get_active_skin().tool_prefix
    except Exception:
        return "┊"

