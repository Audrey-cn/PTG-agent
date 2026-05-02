"""
Prometheus 史诗级配置系统
借鉴 Prometheus Agent 的完整架构
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def get_prometheus_home():
    """Get the Prometheus home directory, respecting PROMETHEUS_HOME env var."""
    from prometheus._paths import get_prometheus_home as _paths_get_home

    return _paths_get_home()


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

    _change_listeners = []

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
        self._notify_listeners(key, value)

    def update(self, updates: dict):
        """Batch update multiple config values."""
        for key, value in updates.items():
            self.set(key, value)

    def validate(self) -> list[str]:
        """Validate config structure and values.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []

        if not isinstance(self._config, dict):
            errors.append("Config must be a dictionary")
            return errors

        model = self._config.get("model", {})
        if not isinstance(model, dict):
            errors.append("'model' section must be a dictionary")
        else:
            if "name" in model and not isinstance(model["name"], str):
                errors.append("'model.name' must be a string")
            if "max_tokens" in model and not isinstance(model["max_tokens"], int):
                errors.append("'model.max_tokens' must be an integer")
            if "temperature" in model:
                temp = model["temperature"]
                if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                    errors.append("'model.temperature' must be between 0 and 2")

        display = self._config.get("display", {})
        if not isinstance(display, dict):
            errors.append("'display' section must be a dictionary")
        else:
            if "compact" in display and not isinstance(display["compact"], bool):
                errors.append("'display.compact' must be a boolean")
            if "streaming" in display and not isinstance(display["streaming"], bool):
                errors.append("'display.streaming' must be a boolean")

        agent = self._config.get("agent", {})
        if not isinstance(agent, dict):
            errors.append("'agent' section must be a dictionary")
        else:
            if "max_turns" in agent and not isinstance(agent["max_turns"], int):
                errors.append("'agent.max_turns' must be an integer")
            if "gateway_timeout" in agent and not isinstance(agent["gateway_timeout"], int):
                errors.append("'agent.gateway_timeout' must be an integer")

        return errors

    @classmethod
    def add_change_listener(cls, callback):
        """Add a listener for config changes.

        Args:
            callback: Function to call when config changes, receives (key, value)
        """
        cls._change_listeners.append(callback)

    @classmethod
    def remove_change_listener(cls, callback):
        """Remove a config change listener."""
        if callback in cls._change_listeners:
            cls._change_listeners.remove(callback)

    def _notify_listeners(self, key, value):
        """Notify all listeners of a config change."""
        for listener in self._change_listeners:
            try:
                listener(key, value)
            except Exception as e:
                logger.warning("Config change listener failed: %s", e)

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


def load_config() -> dict:
    """Load Prometheus configuration.

    Deprecated: Use PrometheusConfig.load() instead.
    This function is kept for backward compatibility.

    Returns:
        Configuration dictionary with all values.
    """
    logger.debug("load_config() is deprecated. Use PrometheusConfig.load() instead.")
    config = PrometheusConfig.load()
    return config.to_dict()


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


def save_config(config: dict) -> None:
    """Save configuration to file.

    Deprecated: Use PrometheusConfig class instead.
    This function is kept for backward compatibility.

    Args:
        config: Configuration dictionary to save.
    """
    logger.debug("save_config() is deprecated. Use PrometheusConfig.save() instead.")
    if isinstance(config, dict):
        if "_config_version" not in config:
            merged_config = DEFAULT_CONFIG.copy()
            merged_config.update(config)
            config = merged_config

        cfg = PrometheusConfig(config_dict=config)
        cfg.save()
    else:
        logger.error("save_config() expects a dict, got %s", type(config))


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


def migrate_json_to_yaml() -> bool:
    """Migrate existing JSON config to YAML format.

    Returns:
        True if migration was successful or not needed, False if migration failed.
    """
    config_path = get_config_path()
    if not config_path.exists():
        return True

    try:
        with open(config_path, encoding="utf-8") as f:
            content = f.read()

        try:
            config = json.loads(content)
        except json.JSONDecodeError:
            return True

        backup_path = config_path.with_suffix(".json.backup")
        if not backup_path.exists():
            config_path.rename(backup_path)
            logger.info("Backed up JSON config to %s", backup_path)

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        _secure_file(config_path)
        logger.info("Successfully migrated config from JSON to YAML")
        return True

    except Exception as e:
        logger.error("Failed to migrate config: %s", e)
        return False


def _sanitize_env_lines(lines: list) -> list:
    """Sanitize environment variable lines."""
    return [line for line in lines if line.strip() and not line.strip().startswith("#")]
