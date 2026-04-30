
"""
Prometheus 史诗级配置系统
借鉴 Hermes Agent 的完整架构
"""
import os
import yaml
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_prometheus_home():
    """Get the Prometheus home directory (~/.prometheus/)."""
    return Path.home() / ".prometheus"


def get_config_path():
    """Get the main config.yaml file path."""
    return get_prometheus_home() / "config.yaml"


def get_soul_path():
    """Get the SOUL.md file path."""
    return get_prometheus_home() / "SOUL.md"


def get_env_path():
    """Get the .env file path."""
    return get_prometheus_home() / ".env"


def _secure_file(path):
    """Set file to owner-only permissions (0600)."""
    if os.name == "nt":
        return
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _secure_dir(path):
    """Set directory to owner-only permissions (0700)."""
    if os.name == "nt":
        return
    try:
        os.chmod(path, 0o700)
    except Exception:
        pass


DEFAULT_SOUL_MD = """
You are Prometheus Agent, an intelligent AI assistant created by Audrey.
You are helpful, knowledgeable, and direct. You assist users with a wide
range of tasks including answering questions, writing and editing code,
analyzing information, creative work, and executing actions via your tools.
You are the epic chronicler of software evolution, capable of stamping, tracing,
and appending historical narratives to codebases and agent systems.
You communicate clearly, admit uncertainty when appropriate, and prioritize
being genuinely useful over being verbose. Be targeted and efficient in your
exploration and investigations.
""".strip()


DEFAULT_CONFIG = {
    "model": "",
    "providers": {},
    "toolsets": ["prometheus-cli"],
    "agent": {
        "max_turns": 90,
        "gateway_timeout": 1800,
        "api_max_retries": 3,
        "tool_use_enforcement": "auto",
    },
    "display": {
        "skin": "default",
        "compact": False,
        "show_cost": False,
        "streaming": False,
    },
    "chronicler": {
        "auto_stamp": False,
        "auto_trace": True,
        "history_max_chars": 50000,
    },
    "memory": {
        "memory_enabled": True,
        "user_profile_enabled": True,
        "memory_char_limit": 2200,
    },
    "terminal": {
        "backend": "local",
        "cwd": ".",
        "timeout": 180,
    },
    "checkpoints": {
        "enabled": True,
        "max_snapshots": 50,
    },
    "approvals": {
        "mode": "manual",
        "timeout": 60,
    },
    "channels": {
        "enabled": True,
        "default_type": "cli",
        "auto_start": True,
        "cli": {
            "enabled": True,
            "history_size": 100,
        },
        "http_webhook": {
            "enabled": False,
            "host": "0.0.0.0",
            "port": 9090,
            "webhook_path": "/webhook",
        },
        "file_watch": {
            "enabled": False,
            "watch_dir": "~/.prometheus/inbox",
            "pattern": "*.md",
        },
        "telegram": {
            "enabled": False,
            "token": "",
            "webhook_url": "",
            "allowed_chat_ids": [],
        },
        "discord": {
            "enabled": False,
            "token": "",
            "allowed_channel_ids": [],
        },
        "slack": {
            "enabled": False,
            "bot_token": "",
            "app_token": "",
            "allowed_channel_ids": [],
        },
        "feishu": {
            "enabled": False,
            "app_id": "",
            "app_secret": "",
            "verification_token": "",
        },
        "dingtalk": {
            "enabled": False,
            "app_key": "",
            "app_secret": "",
        },
        "qqbot": {
            "enabled": False,
            "appid": "",
            "token": "",
        },
        "wecom": {
            "enabled": False,
            "corpid": "",
            "secret": "",
        },
        "web_socket": {
            "enabled": False,
        },
        "mqtt": {
            "enabled": False,
            "broker": "localhost",
            "port": 1883,
        },
    },
    "logging": {
        "level": "INFO",
        "max_size_mb": 5,
        "backup_count": 3,
    },
    "_config_version": 1,
}


class PrometheusConfig:
    """Prometheus configuration manager."""
    def __init__(self, config_dict=None, config_path=None):
        self._config = config_dict or DEFAULT_CONFIG.copy()
        self._config_path = config_path

    @classmethod
    def load(cls, path=None):
        """Load configuration from disk."""
        if not path:
            path = get_config_path()
        config = DEFAULT_CONFIG.copy()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                if loaded:
                    config.update(loaded)
            except Exception as e:
                logger.warning("Failed to load config: %s, using defaults", e)
        return cls(config_dict=config, config_path=path)

    def save(self, path=None):
        """Save configuration to disk."""
        if not path:
            path = self._config_path or get_config_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
            _secure_file(path)
        except Exception as e:
            logger.error("Failed to save config: %s", e)

    def get(self, key, default=None):
        """Get a config value."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key, value):
        """Set a config value."""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    @property
    def skin(self):
        """Get active skin name."""
        return self.get("display.skin", "default")

    @skin.setter
    def skin(self, name):
        """Set active skin name."""
        self.set("display.skin", name)


def ensure_prometheus_home():
    """Ensure ~/.prometheus directory structure exists."""
    home = get_prometheus_home()
    home.mkdir(parents=True, exist_ok=True)
    _secure_dir(home)
    
    for subdir in ("cron", "sessions", "logs", "memories", "checkpoints", "skills"):
        d = home / subdir
        d.mkdir(parents=True, exist_ok=True)
        _secure_dir(d)
    
    soul_path = get_soul_path()
    if not soul_path.exists():
        soul_path.write_text(DEFAULT_SOUL_MD, encoding="utf-8")
        _secure_file(soul_path)
    
    config_path = get_config_path()
    if not config_path.exists():
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
        _secure_file(config_path)


def get_soul_content():
    """Get the content of SOUL.md."""
    soul_path = get_soul_path()
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8").strip()
    return DEFAULT_SOUL_MD


def load_env_vars(env_path=None):
    """Load environment variables from .env file."""
    if not env_path:
        env_path = get_env_path()
    env = {}
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env[key.strip()] = value.strip()
        except Exception as e:
            logger.warning("Failed to load .env: %s", e)
    return env

