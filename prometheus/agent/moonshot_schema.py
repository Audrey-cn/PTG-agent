"""Helpers for translating OpenAI-style tool schemas to Moonshot's schema subset."""

from __future__ import annotations

import copy
from typing import Any

_SCHEMA_MAP_KEYS = frozenset({"properties", "patternProperties", "$defs", "definitions"})

_SCHEMA_LIST_KEYS = frozenset({"anyOf", "oneOf", "allOf", "prefixItems"})

_SCHEMA_NODE_KEYS = frozenset({"items", "contains", "not", "additionalProperties", "propertyNames"})


def _repair_schema(node: Any, is_schema: bool = True) -> Any:
    """Recursively apply Moonshot repairs to a schema node.

    ``is_schema=True`` means this dict is a JSON Schema node and gets the
    missing-type + anyOf-parent repairs applied.  ``is_schema=False`` means
    it's a container map (e.g. the value of ``properties``) and we only
    recurse into its values.
    """
    if isinstance(node, list):
        return [_repair_schema(item, is_schema=True) for item in node]
    if not isinstance(node, dict):
        return node

    repaired: dict[str, Any] = {}
    for key, value in node.items():
        if key in _SCHEMA_MAP_KEYS and isinstance(value, dict):
            repaired[key] = {
                sub_key: _repair_schema(sub_val, is_schema=True)
                for sub_key, sub_val in value.items()
            }
        elif key in _SCHEMA_LIST_KEYS and isinstance(value, list):
            repaired[key] = [_repair_schema(v, is_schema=True) for v in value]
        elif key in _SCHEMA_NODE_KEYS:
            if isinstance(value, dict):
                repaired[key] = _repair_schema(value, is_schema=True)
            else:
                repaired[key] = value
        else:
            repaired[key] = value

    if not is_schema:
        return repaired

    if "anyOf" in repaired and isinstance(repaired["anyOf"], list):
        repaired.pop("type", None)
        return repaired

    if "$ref" in repaired:
        return repaired
    return _fill_missing_type(repaired)


def _fill_missing_type(node: dict[str, Any]) -> dict[str, Any]:
    """Infer a reasonable ``type`` if this schema node has none."""
    if "type" in node and node["type"] not in (None, ""):
        return node

    if "properties" in node or "required" in node or "additionalProperties" in node:
        inferred = "object"
    elif "items" in node or "prefixItems" in node:
        inferred = "array"
    elif "enum" in node and isinstance(node["enum"], list) and node["enum"]:
        sample = node["enum"][0]
        if isinstance(sample, bool):
            inferred = "boolean"
        elif isinstance(sample, int):
            inferred = "integer"
        elif isinstance(sample, float):
            inferred = "number"
        else:
            inferred = "string"
    else:
        inferred = "string"

    return {**node, "type": inferred}


def sanitize_moonshot_tool_parameters(parameters: Any) -> dict[str, Any]:
    """Normalize tool parameters to a Moonshot-compatible object schema.

    Returns a deep-copied schema with the two flavored-JSON-Schema repairs
    applied.  Input is not mutated.
    """
    if not isinstance(parameters, dict):
        return {"type": "object", "properties": {}}

    repaired = _repair_schema(copy.deepcopy(parameters), is_schema=True)
    if not isinstance(repaired, dict):
        return {"type": "object", "properties": {}}

    if repaired.get("type") != "object":
        repaired["type"] = "object"
    if "properties" not in repaired:
        repaired["properties"] = {}

    return repaired


def sanitize_moonshot_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply ``sanitize_moonshot_tool_parameters`` to every tool's parameters."""
    if not tools:
        return tools

    sanitized: list[dict[str, Any]] = []
    any_change = False
    for tool in tools:
        if not isinstance(tool, dict):
            sanitized.append(tool)
            continue
        fn = tool.get("function")
        if not isinstance(fn, dict):
            sanitized.append(tool)
            continue
        params = fn.get("parameters")
        repaired = sanitize_moonshot_tool_parameters(params)
        if repaired is not params:
            any_change = True
            new_fn = {**fn, "parameters": repaired}
            sanitized.append({**tool, "function": new_fn})
        else:
            sanitized.append(tool)

    return sanitized if any_change else tools


def is_moonshot_model(model: Optional[str]) -> bool:
    """True for any Kimi / Moonshot model slug, regardless of aggregator prefix.

    Matches bare names (``kimi-k2.6``, ``moonshotai/Kimi-K2.6``) and aggregator-
    prefixed slugs (``nous/moonshotai/kimi-k2.6``, ``openrouter/moonshotai/...``).
    Detection by model name covers Nous / OpenRouter / other aggregators that
    route to Moonshot's inference, where the base URL is the aggregator's, not
    ``api.moonshot.ai``.
    """
    if not model:
        return False
    bare = model.strip().lower()
    tail = bare.rsplit("/", 1)[-1]
    if tail.startswith("kimi-") or tail == "kimi":
        return True
    return bool("moonshot" in bare or "/kimi" in bare or bare.startswith("kimi"))
