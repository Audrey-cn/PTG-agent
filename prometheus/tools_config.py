from __future__ import annotations

import logging

import yaml

from prometheus.config import get_config_path

logger = logging.getLogger(__name__)


class ToolsConfig:
    def __init__(self) -> None:
        self._config_path = get_config_path()
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self._config_path.exists():
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                self._data = cfg.get("tools", {})
            except Exception as e:
                logger.warning("Failed to load tools config: %s", e)
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        try:
            full_cfg: dict = {}
            if self._config_path.exists():
                with open(self._config_path, encoding="utf-8") as f:
                    full_cfg = yaml.safe_load(f) or {}
            full_cfg["tools"] = self._data
            with open(self._config_path, "w", encoding="utf-8") as f:
                yaml.dump(full_cfg, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            logger.error("Failed to save tools config: %s", e)

    def _ensure_entry(self, name: str) -> dict:
        if "enabled" not in self._data:
            self._data["enabled"] = {}
        if "configs" not in self._data:
            self._data["configs"] = {}
        if name not in self._data["enabled"]:
            self._data["enabled"][name] = True
        if name not in self._data["configs"]:
            self._data["configs"][name] = {}
        return self._data

    def get_enabled_tools(self) -> List[str]:
        enabled = self._data.get("enabled", {})
        return [name for name, is_on in enabled.items() if is_on]

    def enable_tool(self, name: str) -> bool:
        self._ensure_entry(name)
        self._data["enabled"][name] = True
        self._save()
        return True

    def disable_tool(self, name: str) -> bool:
        self._ensure_entry(name)
        self._data["enabled"][name] = False
        self._save()
        return True

    def is_enabled(self, name: str) -> bool:
        enabled = self._data.get("enabled", {})
        return enabled.get(name, True)

    def get_tool_config(self, name: str) -> dict:
        configs = self._data.get("configs", {})
        return configs.get(name, {})

    def set_tool_config(self, name: str, config: dict) -> None:
        self._ensure_entry(name)
        self._data["configs"][name] = config
        self._save()
