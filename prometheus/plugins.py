from __future__ import annotations

import os
import sys
import json
import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("prometheus.plugins")


@dataclass
class PluginManifest:
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)
    provides_tools: list[str] = field(default_factory=list)
    provides_commands: list[dict] = field(default_factory=list)
    provides_platforms: list[str] = field(default_factory=list)
    enabled: bool = True


class PluginContext:
    def __init__(self, manifest: PluginManifest, plugin_dir: Path):
        self.manifest = manifest
        self.plugin_dir = plugin_dir
        self._registered_tools: list[str] = []
        self._registered_commands: list[dict] = []

    def register_tool(self, name: str, handler: Callable, schema: dict, description: str = "", emoji: str = "🔌"):
        from prometheus.tools.registry import registry
        registry.register(
            name=name,
            toolset=f"plugin:{self.manifest.name}",
            schema=schema,
            handler=handler,
            description=description or f"Plugin: {self.manifest.name}",
            emoji=emoji,
        )
        self._registered_tools.append(name)
        logger.info("Plugin %s registered tool: %s", self.manifest.name, name)

    def register_command(self, name: str, description: str, args_hint: str = "", handler: Callable | None = None):
        entry = {"name": name, "description": description, "args_hint": args_hint, "handler": handler}
        self._registered_commands.append(entry)
        logger.info("Plugin %s registered command: /%s", self.manifest.name, name)


class Plugin:
    def __init__(self, manifest: PluginManifest, plugin_dir: Path, module=None):
        self.manifest = manifest
        self.plugin_dir = plugin_dir
        self.module = module
        self.context: PluginContext | None = None
        self.loaded = False

    def load(self) -> bool:
        if self.loaded:
            return True
        try:
            self.context = PluginContext(self.manifest, self.plugin_dir)
            if self.module and hasattr(self.module, "on_load"):
                self.module.on_load(self.context)
            self.loaded = True
            logger.info("Plugin loaded: %s v%s", self.manifest.name, self.manifest.version)
            return True
        except Exception as e:
            logger.error("Plugin %s load failed: %s", self.manifest.name, e)
            return False

    def unload(self) -> bool:
        if not self.loaded:
            return True
        try:
            if self.module and hasattr(self.module, "on_unload"):
                self.module.on_unload()
            if self.context:
                for tool_name in self.context._registered_tools:
                    try:
                        from prometheus.tools.registry import registry
                        if tool_name in registry._tools:
                            del registry._tools[tool_name]
                    except Exception:
                        pass
            self.loaded = False
            logger.info("Plugin unloaded: %s", self.manifest.name)
            return True
        except Exception as e:
            logger.error("Plugin %s unload failed: %s", self.manifest.name, e)
            return False


class PluginManager:
    def __init__(self, plugins_dir: Path | None = None):
        if plugins_dir is None:
            from prometheus.config import get_prometheus_home
            plugins_dir = get_prometheus_home() / "plugins"
        self.plugins_dir = plugins_dir
        self._plugins: dict[str, Plugin] = {}

    def discover(self) -> list[PluginManifest]:
        manifests = []
        if not self.plugins_dir.exists():
            return manifests
        for entry in sorted(self.plugins_dir.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "plugin.yaml"
            if not manifest_path.exists():
                manifest_path = entry / "plugin.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = self._load_manifest(manifest_path)
                if manifest:
                    manifests.append(manifest)
            except Exception as e:
                logger.warning("Failed to load manifest from %s: %s", entry, e)
        return manifests

    def _load_manifest(self, path: Path) -> PluginManifest | None:
        try:
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                import yaml
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return PluginManifest(
                name=data.get("name", path.parent.name),
                version=data.get("version", "0.1.0"),
                description=data.get("description", ""),
                author=data.get("author", ""),
                dependencies=data.get("dependencies", []),
                provides_tools=data.get("provides_tools", []),
                provides_commands=data.get("provides_commands", []),
                provides_platforms=data.get("provides_platforms", []),
                enabled=data.get("enabled", True),
            )
        except Exception as e:
            logger.error("Manifest parse error %s: %s", path, e)
            return None

    def load_plugin(self, name: str) -> bool:
        plugin_dir = self.plugins_dir / name
        if not plugin_dir.exists():
            logger.error("Plugin not found: %s", name)
            return False

        manifest_path = plugin_dir / "plugin.yaml"
        if not manifest_path.exists():
            manifest_path = plugin_dir / "plugin.json"
        if not manifest_path.exists():
            logger.error("Plugin manifest not found: %s", name)
            return False

        manifest = self._load_manifest(manifest_path)
        if not manifest:
            return False

        module = None
        init_path = plugin_dir / "__init__.py"
        if init_path.exists():
            try:
                spec = importlib.util.spec_from_file_location(
                    f"prometheus.plugins.{name}", str(init_path)
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
            except Exception as e:
                logger.error("Plugin %s module load failed: %s", name, e)

        plugin = Plugin(manifest, plugin_dir, module)
        if plugin.load():
            self._plugins[name] = plugin
            return True
        return False

    def unload_plugin(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if not plugin:
            return False
        result = plugin.unload()
        if result:
            del self._plugins[name]
        return result

    def get_plugin(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict]:
        result = []
        for name, plugin in self._plugins.items():
            result.append({
                "name": name,
                "version": plugin.manifest.version,
                "description": plugin.manifest.description,
                "loaded": plugin.loaded,
                "tools": plugin.context._registered_tools if plugin.context else [],
                "commands": plugin.context._registered_commands if plugin.context else [],
            })
        return result

    def load_all(self) -> int:
        manifests = self.discover()
        loaded = 0
        for m in manifests:
            if m.enabled and self.load_plugin(m.name):
                loaded += 1
        return loaded

    def get_plugin_commands(self) -> dict[str, dict]:
        commands = {}
        for name, plugin in self._plugins.items():
            if plugin.context:
                for cmd in plugin.context._registered_commands:
                    commands[cmd["name"]] = {
                        "description": cmd.get("description", ""),
                        "args_hint": cmd.get("args_hint", ""),
                    }
        return commands


_global_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = PluginManager()
    return _global_manager


def get_plugin_commands() -> dict[str, dict]:
    return get_plugin_manager().get_plugin_commands()
