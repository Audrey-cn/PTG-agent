"""Lazy loading utilities for Prometheus."""

from __future__ import annotations

import importlib
import sys
from typing import Any


class LazyModule:
    """A lazily loaded module wrapper.

    Usage:
        from prometheus.lazy_imports import LazyModule
        openai = LazyModule("openai")
        client = openai.OpenAI()  # Imports on first use
    """

    def __init__(self, module_name: str, package: str | None = None):
        self._module_name = module_name
        self._package = package
        self._module = None

    def _ensure_loaded(self):
        if self._module is None:
            self._module = importlib.import_module(self._module_name, self._package)

    def __getattr__(self, name: str) -> Any:
        self._ensure_loaded()
        return getattr(self._module, name)

    def __dir__(self) -> list:
        self._ensure_loaded()
        return dir(self._module)


class LazyClass:
    """A lazily loaded class wrapper.

    Usage:
        from prometheus.lazy_imports import LazyClass
        OpenAI = LazyClass("openai", "OpenAI")
        client = OpenAI()  # Imports on instantiation
    """

    def __init__(self, module_name: str, class_name: str):
        self._module_name = module_name
        self._class_name = class_name
        self._class = None

    def _ensure_loaded(self):
        if self._class is None:
            module = importlib.import_module(self._module_name)
            self._class = getattr(module, self._class_name)

    def __call__(self, *args, **kwargs) -> Any:
        self._ensure_loaded()
        return self._class(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        self._ensure_loaded()
        return getattr(self._class, name)


class LazyLoader:
    """Centralized lazy loading manager.

    Tracks lazy imports and provides utilities for managing them.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._import_cache = {}
            cls._import_timestamps = {}
        return cls._instance

    def import_module(self, module_name: str, package: str | None = None) -> LazyModule:
        """Import a module lazily."""
        key = (module_name, package)
        if key not in self._import_cache:
            self._import_cache[key] = LazyModule(module_name, package)
        return self._import_cache[key]

    def import_class(self, module_name: str, class_name: str) -> LazyClass:
        """Import a class lazily."""
        key = (module_name, class_name)
        if key not in self._import_cache:
            self._import_cache[key] = LazyClass(module_name, class_name)
        return self._import_cache[key]

    def get_stats(self) -> dict:
        """Get statistics about lazy imports."""
        return {
            "cached_modules": len(self._import_cache),
        }


def lazy_import(module_name: str, package: str | None = None) -> LazyModule:
    """Convenience function for lazy module import."""
    return LazyLoader().import_module(module_name, package)


def lazy_class(module_name: str, class_name: str) -> LazyClass:
    """Convenience function for lazy class import."""
    return LazyLoader().import_class(module_name, class_name)


# Pre-defined lazy imports for common heavy dependencies

openai = LazyModule("openai")
anthropic = LazyModule("anthropic")
google = LazyModule("google.generativeai")
aiohttp = LazyModule("aiohttp")
websockets = LazyModule("websockets")
fastapi = LazyModule("fastapi")
uvicorn = LazyModule("uvicorn")
pydantic = LazyModule("pydantic")
tiktoken = LazyModule("tiktoken")
asyncio = LazyModule("asyncio")


# Context manager for temporarily disabling lazy loading
class EagerLoading:
    """Context manager to force eager loading within a block."""

    def __enter__(self):
        self._original_import = __builtins__.__import__
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        __builtins__.__import__ = self._original_import


def measure_import_time(module_name: str) -> float:
    """Measure the time taken to import a module."""
    import time

    start = time.perf_counter()
    importlib.import_module(module_name)
    end = time.perf_counter()
    return end - start


def optimize_imports() -> None:
    """Apply import optimization techniques."""

    def remove_unused_modules(prefixes: list) -> None:
        """Remove modules that won't be used from sys.modules."""
        modules_to_remove = []
        for mod_name in sys.modules:
            for prefix in prefixes:
                if mod_name.startswith(prefix):
                    modules_to_remove.append(mod_name)
                    break

        for mod_name in modules_to_remove:
            del sys.modules[mod_name]

    remove_unused_modules(
        [
            "tkinter",
            "turtle",
            "email",
            "http",
            "xml",
            "html",
            "sqlite3",
            "unittest",
        ]
    )
