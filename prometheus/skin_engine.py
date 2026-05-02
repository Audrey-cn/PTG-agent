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
                "forging wisdom",
                "tending the flame",
                "reading the omens",
                "carrying the torch",
                "shaping the future",
                "stoking the fire",
                "weaving destiny",
                "illuminating the path",
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
            "banner_title": "#00BFFF",
            "banner_accent": "#1E90FF",
            "banner_dim": "#6495ED",
            "banner_text": "#E6F3FF",
            "ui_accent": "#00BFFF",
            "ui_label": "#4169E1",
            "ui_ok": "#4caf50",
            "ui_error": "#ef5350",
            "ui_warn": "#ffa726",
        },
        "spinner": {
            "waiting_faces": ["(⚡)", "(🌩️)", "(☁️)", "(🌩️)", "(⚡)"],
            "thinking_faces": ["(⚡)", "(🌩️)", "(☁️)", "(⌁)", "(🌩️)"],
            "thinking_verbs": [
                "summoning lightning",
                "ruling Olympus",
                "casting thunder",
                "commanding the sky",
                "striking with power",
            ],
        },
        "branding": {
            "agent_name": "Zeus Agent",
            "welcome": "By Olympus! ⚡ Type your message or /help for commands.",
            "goodbye": "The thunder echoes! ⚡",
            "response_label": " ⚡ Zeus ",
            "prompt_symbol": "⚡ ❯ ",
            "help_header": "(⚡) Divine Commands",
        },
        "tool_prefix": "│",
        "tool_emojis": {
            "stamp_seed": "⚡",
            "trace_seed": "🌩️",
            "terminal": "⚡",
            "web_search": "🌩️",
        },
    },
    "athena": {
        "name": "athena",
        "description": "雅典娜智慧主题",
        "colors": {
            "banner_border": "#9370DB",
            "banner_title": "#BA55D3",
            "banner_accent": "#8A2BE2",
            "banner_dim": "#9932CC",
            "banner_text": "#F3E5F5",
            "ui_accent": "#BA55D3",
            "ui_label": "#9370DB",
            "ui_ok": "#4caf50",
            "ui_error": "#ef5350",
            "ui_warn": "#ffa726",
        },
        "spinner": {
            "waiting_faces": ["(♀)", "(🦉)", "(📚)", "(🎓)", "(✨)"],
            "thinking_faces": ["(♀)", "(🦉)", "(📚)", "(⌁)", "(🎓)"],
            "thinking_verbs": [
                "pondering wisdom",
                "seeking knowledge",
                "contemplating truth",
                "studying deeply",
                "analyzing wisely",
            ],
        },
        "branding": {
            "agent_name": "Athena Agent",
            "welcome": "Wisdom guides you ♀ Type your message or /help for commands.",
            "goodbye": "Wisdom endures! ♀",
            "response_label": " ♀ Athena ",
            "prompt_symbol": "♀ ❯ ",
            "help_header": "(♀) Wisdom Commands",
        },
        "tool_prefix": "│",
        "tool_emojis": {
            "stamp_seed": "♀",
            "trace_seed": "📚",
            "web_search": "🦉",
            "memory": "📖",
        },
    },
    "hades": {
        "name": "hades",
        "description": "冥界暗黑主题",
        "colors": {
            "banner_border": "#4B0082",
            "banner_title": "#8B008B",
            "banner_accent": "#6A0DAD",
            "banner_dim": "#483D8B",
            "banner_text": "#E6E6FA",
            "ui_accent": "#8B008B",
            "ui_label": "#4B0082",
            "ui_ok": "#4caf50",
            "ui_error": "#ef5350",
            "ui_warn": "#ffa726",
        },
        "spinner": {
            "waiting_faces": ["(💀)", "(🌑)", "(🔥)", "(⚰️)", "(🦇)"],
            "thinking_faces": ["(💀)", "(🌑)", "(🔥)", "(⚰️)", "(🦇)"],
            "thinking_verbs": [
                "summoning souls",
                "ruling the underworld",
                "gathering shadows",
                "commanding the dead",
                "weaving darkness",
            ],
        },
        "branding": {
            "agent_name": "Hades Agent",
            "welcome": "Welcome to the Underworld 💀 Type your message or /help for commands.",
            "goodbye": "The shadows endure! 💀",
            "response_label": " 💀 Hades ",
            "prompt_symbol": "💀 ❯ ",
            "help_header": "(💀) Underworld Commands",
        },
        "tool_prefix": "╎",
        "tool_emojis": {
            "stamp_seed": "💀",
            "trace_seed": "🌑",
            "terminal": "⚰️",
            "web_search": "🦇",
        },
    },
    "poseidon": {
        "name": "poseidon",
        "description": "波塞冬海洋主题",
        "colors": {
            "banner_border": "#006994",
            "banner_title": "#00BFFF",
            "banner_accent": "#1E90FF",
            "banner_dim": "#4682B4",
            "banner_text": "#E0F7FA",
            "ui_accent": "#00BFFF",
            "ui_label": "#006994",
            "ui_ok": "#4caf50",
            "ui_error": "#ef5350",
            "ui_warn": "#ffa726",
        },
        "spinner": {
            "waiting_faces": ["(🌊)", "(🐚)", "(🐠)", "(⚓)", "(🌊)"],
            "thinking_faces": ["(🌊)", "(🐚)", "(🐠)", "(⌁)", "(⚓)"],
            "thinking_verbs": [
                "riding the waves",
                "commanding the sea",
                "diving deep",
                "navigating currents",
                "summoning tides",
            ],
        },
        "branding": {
            "agent_name": "Poseidon Agent",
            "welcome": "The seas obey! 🌊 Type your message or /help for commands.",
            "goodbye": "The tide recedes! 🌊",
            "response_label": " 🌊 Poseidon ",
            "prompt_symbol": "🌊 ❯ ",
            "help_header": "(🌊) Ocean Commands",
        },
        "tool_prefix": "┆",
        "tool_emojis": {
            "stamp_seed": "🌊",
            "trace_seed": "🐚",
            "web_search": "🐠",
            "terminal": "⚓",
        },
    },
    "apollo": {
        "name": "apollo",
        "description": "阿波罗光明主题",
        "colors": {
            "banner_border": "#FFD700",
            "banner_title": "#FFA500",
            "banner_accent": "#FF8C00",
            "banner_dim": "#DAA520",
            "banner_text": "#FFF8DC",
            "ui_accent": "#FFA500",
            "ui_label": "#FFD700",
            "ui_ok": "#4caf50",
            "ui_error": "#ef5350",
            "ui_warn": "#ffa726",
        },
        "spinner": {
            "waiting_faces": ["(☀️)", "(🎵)", "(🏹)", "(✨)", "(☀️)"],
            "thinking_faces": ["(☀️)", "(🎵)", "(🏹)", "(⌁)", "(✨)"],
            "thinking_verbs": [
                "shining light",
                "playing melodies",
                "aiming true",
                "illuminating truth",
                "radiating warmth",
            ],
        },
        "branding": {
            "agent_name": "Apollo Agent",
            "welcome": "Light and music! ☀️ Type your message or /help for commands.",
            "goodbye": "The sun sets! ☀️",
            "response_label": " ☀️ Apollo ",
            "prompt_symbol": "☀️ ❯ ",
            "help_header": "(☀️) Light Commands",
        },
        "tool_prefix": "┊",
        "tool_emojis": {
            "stamp_seed": "☀️",
            "trace_seed": "🎵",
            "web_search": "🏹",
            "terminal": "✨",
        },
    },
    "artemis": {
        "name": "artemis",
        "description": "阿尔忒弥斯月光主题",
        "colors": {
            "banner_border": "#C0C0C0",
            "banner_title": "#E8E8E8",
            "banner_accent": "#B0C4DE",
            "banner_dim": "#A9A9A9",
            "banner_text": "#F5F5F5",
            "ui_accent": "#C0C0C0",
            "ui_label": "#B0C4DE",
            "ui_ok": "#4caf50",
            "ui_error": "#ef5350",
            "ui_warn": "#ffa726",
        },
        "spinner": {
            "waiting_faces": ["(🌙)", "(🏹)", "(🦌)", "(✨)", "(🌙)"],
            "thinking_faces": ["(🌙)", "(🏹)", "(🦌)", "(⌁)", "(✨)"],
            "thinking_verbs": [
                "hunting truth",
                "guarding the wild",
                "moonlit wisdom",
                "tracking answers",
                "protecting knowledge",
            ],
        },
        "branding": {
            "agent_name": "Artemis Agent",
            "welcome": "The moon watches over you 🌙 Type your message or /help for commands.",
            "goodbye": "The hunt continues! 🌙",
            "response_label": " 🌙 Artemis ",
            "prompt_symbol": "🌙 ❯ ",
            "help_header": "(🌙) Moon Commands",
        },
        "tool_prefix": "┊",
        "tool_emojis": {
            "stamp_seed": "🌙",
            "trace_seed": "🏹",
            "web_search": "🦌",
            "terminal": "✨",
        },
    },
    "prometheus": {
        "name": "prometheus",
        "description": "赫尔墨斯信使主题",
        "colors": {
            "banner_border": "#00CED1",
            "banner_title": "#20B2AA",
            "banner_accent": "#008B8B",
            "banner_dim": "#5F9EA0",
            "banner_text": "#E0FFFF",
            "ui_accent": "#20B2AA",
            "ui_label": "#00CED1",
            "ui_ok": "#4caf50",
            "ui_error": "#ef5350",
            "ui_warn": "#ffa726",
        },
        "spinner": {
            "waiting_faces": ["(⚡)", "(👟)", "(📬)", "(✨)", "(⚡)"],
            "thinking_faces": ["(⚡)", "(👟)", "(📬)", "(⌁)", "(✨)"],
            "thinking_verbs": [
                "delivering messages",
                "speeding between worlds",
                "carrying wisdom",
                "rushing answers",
                "connecting minds",
            ],
        },
        "branding": {
            "agent_name": "Prometheus Agent",
            "welcome": "Swift as the wind! ⚡ Type your message or /help for commands.",
            "goodbye": "Message delivered! ⚡",
            "response_label": " 🔥 Prometheus ",
            "prompt_symbol": "⚡ ❯ ",
            "help_header": "(⚡) Messenger Commands",
        },
        "tool_prefix": "│",
        "tool_emojis": {
            "stamp_seed": "⚡",
            "trace_seed": "👟",
            "web_search": "📬",
            "terminal": "✨",
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
        {"name": name, "description": data.get("description", ""), "source": "builtin"}
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
