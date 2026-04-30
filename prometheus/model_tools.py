#!/usr/bin/env python3
import json
from typing import Any, Optional

_TOOL_DEFINITIONS: list[dict] = []
_TOOL_HANDLERS: dict[str, callable] = {}


def register_tool(name: str, description: str, parameters: dict, handler: callable):
    definition = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }
    _TOOL_DEFINITIONS.append(definition)
    _TOOL_HANDLERS[name] = handler


def get_tool_definitions() -> list[dict]:
    try:
        from .tools.registry import registry
    except ImportError:
        from tools.registry import registry

    dynamic = []
    if hasattr(registry, '_tools'):
        for name, entry in registry._tools.items():
            dynamic.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": getattr(entry, 'description', ''),
                    "parameters": getattr(entry.schema, 'parameters', {}) if hasattr(entry, 'schema') else {},
                },
            })

    return _TOOL_DEFINITIONS + dynamic


def handle_tool_call(tool_name: str, tool_args: dict) -> str:
    if tool_name in _TOOL_HANDLERS:
        try:
            result = _TOOL_HANDLERS[tool_name](tool_args)
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    try:
        from .tools.registry import registry
    except ImportError:
        from tools.registry import registry

    entry = registry.get(tool_name) if hasattr(registry, 'get') else None
    if entry is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = entry.handler(tool_args)
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False)
        return str(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def has_tool(tool_name: str) -> bool:
    if tool_name in _TOOL_HANDLERS:
        return True
    try:
        from .tools.registry import registry
    except ImportError:
        from tools.registry import registry
    return bool(registry.get(tool_name)) if hasattr(registry, 'get') else False


def get_tool_count() -> int:
    return len(get_tool_definitions())


def clear_registered_tools():
    _TOOL_DEFINITIONS.clear()
    _TOOL_HANDLERS.clear()
