from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("prometheus.acp_adapter.tools")


class ACPTools:
    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}
        self._schemas: dict[str, dict[str, Any]] = {}

    def register_tool(
        self, name: str, handler: Callable, schema: dict[str, Any] | None = None
    ) -> None:
        self._tools[name] = handler
        self._schemas[name] = schema or {
            "name": name,
            "description": f"ACP tool: {name}",
            "parameters": {"type": "object", "properties": {}},
        }
        logger.debug(f"Registered ACP tool: {name}")

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": name, "schema": self._schemas[name]} for name in self._tools]

    def invoke_tool(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            return {"error": f"Tool not found: {name}", "success": False}

        try:
            result = self._tools[name](params)
            if isinstance(result, dict):
                return result
            return {"result": result, "success": True}
        except Exception as e:
            logger.error(f"Tool invocation failed: {name} - {e}")
            return {"error": str(e), "success": False}

    def convert_to_openai_schema(self) -> list[dict[str, Any]]:
        schemas = []
        for name, schema in self._schemas.items():
            openai_schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": schema.get("description", ""),
                    "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            schemas.append(openai_schema)
        return schemas

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        return name in self._tools
