"""
Prometheus 史诗级配置系统
借鉴 Hermes Agent 的完整架构
"""

import contextlib
import json
import logging
import os
from pathlib import Path

import yaml

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
    with contextlib.suppress(Exception):
        os.chmod(path, 0o600)


def _secure_dir(path):
    """Set directory to owner-only permissions (0700)."""
    if os.name == "nt":
        return
    with contextlib.suppress(Exception):
        os.chmod(path, 0o700)


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
    "model": {
        "provider": "",
        "name": "",
        "base_url": "",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "api": {
        "base_url": "https://api.openai.com/v1",
        "key": "",
    },
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
                with open(path, encoding="utf-8") as f:
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

    def to_dict(self):
        """Return the raw config dictionary."""
        return dict(self._config)

    @property
    def skin(self):
        """Get active skin name."""
        return self.get("display.skin", "default")

    @skin.setter
    def skin(self, name):
        """Set active skin name."""
        self.set("display.skin", name)


Config = PrometheusConfig


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
            with open(env_path, encoding="utf-8") as f:
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


def get_env_value(name: str, default=None):
    """Get environment variable value."""
    return os.environ.get(name, default)


def load_config():
    """Load Prometheus configuration."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load config: %s", e)
    return {}


def cfg_get(config: dict, path: str, default=None):
    """Get a nested value from config using dot-separated path."""
    parts = path.split(".")
    value = config
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default
    return value


def save_config(config: dict):
    """Save configuration to file."""
    config_path = get_config_path()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save config: %s", e)


def save_env_value(key: str, value: str):
    """Save environment variable value to .env file."""
    env_path = get_env_path()
    env_vars = {}

    if env_path.exists():
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip()
        except Exception as e:
            logger.warning("Failed to load .env: %s", e)

    env_vars[key] = value

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
    except Exception as e:
        logger.error("Failed to save .env: %s", e)


def remove_env_value(key: str):
    """Remove environment variable from .env file."""
    env_path = get_env_path()
    if not env_path.exists():
        return

    lines = []
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#"):
                    lines.append(line)
                elif "=" in line_stripped:
                    k = line_stripped.split("=", 1)[0].strip()
                    if k != key:
                        lines.append(line)
    except Exception as e:
        logger.warning("Failed to load .env: %s", e)
        return

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        logger.error("Failed to save .env: %s", e)


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.resolve()


def check_config_version(config: dict) -> bool:
    """Check if config version is valid."""
    return True


def migrate_config(config: dict) -> dict:
    """Migrate config to current version."""
    return config


def validate_config_structure(config: dict) -> bool:
    """Validate config structure."""
    return isinstance(config, dict)


def get_compatible_custom_providers() -> list:
    """Get list of compatible custom providers."""
    return []


def recommended_update_command() -> str:
    """Get recommended update command."""
    return "pip install --upgrade prometheus-agent"


def get_managed_update_command() -> str:
    """Get managed update command."""
    return recommended_update_command()


_MANAGED_TRUE_VALUES = {"true", "1", "yes", "on"}
_MANAGED_SYSTEM_NAMES = {
    "nixos": "NixOS",
    "docker": "Docker",
    "homebrew": "Homebrew",
}


def get_managed_system() -> str | None:
    """Return the package manager owning this install, if any."""
    raw = os.getenv("PROMETHEUS_MANAGED", "").strip()
    if raw:
        normalized = raw.lower()
        if normalized in _MANAGED_TRUE_VALUES:
            return "NixOS"
        return _MANAGED_SYSTEM_NAMES.get(normalized, raw)

    managed_marker = get_prometheus_home() / ".managed"
    if managed_marker.exists():
        return "NixOS"
    return None


def is_managed() -> bool:
    """Check if Prometheus is running in package-manager-managed mode.

    Two signals: the PROMETHEUS_MANAGED env var (set by the systemd service),
    or a .managed marker file in PROMETHEUS_HOME (set by the NixOS activation
    script, so interactive shells also see it).
    """
    return get_managed_system() is not None


def read_raw_config() -> dict:
    """Read raw config without validation."""
    return load_config()


def _sanitize_env_lines(lines: list) -> list:
    """Sanitize environment variable lines."""
    return [line for line in lines if line.strip() and not line.strip().startswith("#")]
