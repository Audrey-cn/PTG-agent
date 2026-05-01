#!/usr/bin/env python3
"""Prometheus 插件系统."""

import importlib
import importlib.util
import json
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger("prometheus.plugins")

PLUGIN_DIR = Path.home() / ".prometheus" / "plugins"
PLUGIN_CONFIG_DIR = Path.home() / ".prometheus" / "plugin-config"


@dataclass
class PluginMetadata:
    id: str
    name: str
    version: str
    description: str
    author: str = ""
    homepage: str = ""
    dependencies: list[str] = field(default_factory=list)
    load_priority: int = 100


@dataclass
class PluginState:
    loaded: bool = False
    enabled: bool = True
    error: str | None = None
    loaded_at: str | None = None


class PluginInterface:
    """插件接口基类"""

    def on_load(self) -> bool:
        """插件加载时调用"""
        return True

    def on_enable(self) -> bool:
        """插件启用时调用"""
        return True

    def on_disable(self) -> bool:
        """插件禁用时调用"""
        return True

    def on_unload(self) -> bool:
        """插件卸载时调用"""
        return True

    def get_metadata(self) -> PluginMetadata:
        """返回插件元数据"""
        raise NotImplementedError


class PluginRegistry:
    """
    插件注册表

    管理插件的发现、加载、启用/禁用。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: dict[str, type[PluginInterface]] = {}
            cls._instance._instances: dict[str, PluginInterface] = {}
            cls._instance._states: dict[str, PluginState] = {}
            cls._instance._hooks: dict[str, list[Callable]] = {}
            cls._instance._initialized = False
        return cls._instance

    def register_plugin(
        self,
        plugin_class: type[PluginInterface],
        plugin_id: str = None,
    ):
        """注册插件类"""
        try:
            instance = plugin_class()
            metadata = instance.get_metadata()
            pid = plugin_id or metadata.id

            if pid in self._plugins:
                logger.warning(f"Plugin {pid} already registered, skipping")
                return

            self._plugins[pid] = plugin_class
            self._states[pid] = PluginState()

            logger.info(f"Registered plugin: {pid} ({metadata.name})")

        except Exception as e:
            logger.error(f"Failed to register plugin: {e}")

    def discover_plugins(self, plugin_dirs: list[Path] = None):
        """发现并加载插件"""
        if plugin_dirs is None:
            plugin_dirs = [
                PLUGIN_DIR,
                Path(__file__).parent.parent / "plugins"
                if hasattr(Path(__file__).parent.parent, "__file__")
                else None,
            ]
            plugin_dirs = [p for p in plugin_dirs if p]

        for plugin_dir in plugin_dirs:
            if not plugin_dir.exists():
                continue

            for plugin_file in plugin_dir.glob("*.py"):
                if plugin_file.name.startswith("_"):
                    continue
                self._load_plugin_file(plugin_file)

        for plugin_file in (Path(__file__).parent).glob("plugin_*.py"):
            if plugin_file.name.startswith("_"):
                continue
            self._load_plugin_file(plugin_file)

        self._initialized = True

    def _load_plugin_file(self, plugin_file: Path):
        """从文件加载插件"""
        try:
            spec = importlib.util.spec_from_file_location(
                f"prometheus.plugins.{plugin_file.stem}", plugin_file
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

                for name in dir(module):
                    obj = getattr(module, name)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, PluginInterface)
                        and obj != PluginInterface
                    ):
                        self.register_plugin(obj)

        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_file}: {e}")

    def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件"""
        if plugin_id not in self._plugins:
            logger.warning(f"Plugin {plugin_id} not found")
            return False

        state = self._states.get(plugin_id, PluginState())
        if state.enabled:
            return True

        try:
            if plugin_id not in self._instances:
                plugin_class = self._plugins[plugin_id]
                instance = plugin_class()
                if not instance.on_load():
                    raise Exception("on_load returned False")
                self._instances[plugin_id] = instance

            instance = self._instances[plugin_id]
            if not instance.on_enable():
                raise Exception("on_enable returned False")

            state.enabled = True
            state.loaded = True
            state.loaded_at = datetime.now().isoformat()
            state.error = None
            self._states[plugin_id] = state

            logger.info(f"Enabled plugin: {plugin_id}")
            return True

        except Exception as e:
            state.error = str(e)
            self._states[plugin_id] = state
            logger.error(f"Failed to enable plugin {plugin_id}: {e}")
            return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件"""
        if plugin_id not in self._plugins:
            return False

        state = self._states.get(plugin_id)
        if state and not state.enabled:
            return True

        try:
            if plugin_id in self._instances:
                instance = self._instances[plugin_id]
                if not instance.on_disable():
                    raise Exception("on_disable returned False")

            state.enabled = False
            state.error = None
            self._states[plugin_id] = state

            logger.info(f"Disabled plugin: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to disable plugin {plugin_id}: {e}")
            return False

    def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id not in self._plugins:
            return False

        try:
            if plugin_id in self._instances:
                instance = self._instances[plugin_id]
                instance.on_unload()
                del self._instances[plugin_id]

            state = self._states.get(plugin_id, PluginState())
            state.loaded = False
            state.enabled = False
            self._states[plugin_id] = state

            logger.info(f"Unloaded plugin: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {e}")
            return False

    def get_plugin(self, plugin_id: str) -> PluginInterface | None:
        """获取插件实例"""
        if plugin_id in self._instances:
            state = self._states.get(plugin_id)
            if state and state.enabled:
                return self._instances[plugin_id]
        return None

    def list_plugins(self, include_disabled: bool = False) -> list[dict[str, Any]]:
        """列出所有插件"""
        result = []
        for plugin_id, plugin_class in self._plugins.items():
            state = self._states.get(plugin_id, PluginState())
            if not include_disabled and not state.enabled:
                continue

            try:
                instance = plugin_class()
                metadata = instance.get_metadata()
                result.append(
                    {
                        "id": plugin_id,
                        "name": metadata.name,
                        "version": metadata.version,
                        "description": metadata.description,
                        "loaded": state.loaded,
                        "enabled": state.enabled,
                        "error": state.error,
                    }
                )
            except Exception as e:
                result.append(
                    {
                        "id": plugin_id,
                        "name": plugin_id,
                        "error": str(e),
                        "loaded": False,
                        "enabled": False,
                    }
                )
        return result

    def register_hook(self, hook_name: str, callback: Callable):
        """注册钩子回调"""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        if callback not in self._hooks[hook_name]:
            self._hooks[hook_name].append(callback)

    def unregister_hook(self, hook_name: str, callback: Callable):
        """取消注册钩子回调"""
        if hook_name in self._hooks and callback in self._hooks[hook_name]:
            self._hooks[hook_name].remove(callback)

    def trigger_hook(self, hook_name: str, *args, **kwargs) -> list[Any]:
        """触发钩子"""
        results = []
        if hook_name in self._hooks:
            for callback in self._hooks[hook_name]:
                try:
                    result = callback(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Hook {hook_name} failed: {e}")
        return results


_global_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    """获取全局插件注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
    return _global_registry


def discover_and_load_plugins():
    """发现并加载所有插件"""
    registry = get_plugin_registry()
    registry.discover_plugins()
    for plugin_info in registry.list_plugins():
        if plugin_info.get("enabled", True):
            registry.enable_plugin(plugin_info["id"])


@dataclass
class ToolPlugin(PluginInterface):
    """工具插件基类"""

    def get_tools(self) -> list[dict[str, Any]]:
        """返回插件提供的工具列表"""
        return []

    def register_tools(self):
        """注册工具到注册表"""
        from .registry import registry

        for tool in self.get_tools():
            registry.register(**tool)


class MemoryProviderPlugin(ToolPlugin):
    """记忆提供者插件"""

    def get_memory_provider(self) -> Any:
        """返回记忆提供者实例"""
        raise NotImplementedError


class ContextEnginePlugin(ToolPlugin):
    """上下文引擎插件"""

    def get_context_engine(self) -> Any:
        """返回上下文引擎实例"""
        raise NotImplementedError


class ImageGenPlugin(ToolPlugin):
    """图像生成插件"""

    def get_image_generator(self) -> Any:
        """返回图像生成器实例"""
        raise NotImplementedError


def create_plugin_metadata(
    plugin_id: str,
    name: str,
    version: str,
    description: str,
    author: str = "",
    dependencies: list[str] = None,
) -> PluginMetadata:
    """创建插件元数据的便捷函数"""
    return PluginMetadata(
        id=plugin_id,
        name=name,
        version=version,
        description=description,
        author=author,
        dependencies=dependencies or [],
    )
