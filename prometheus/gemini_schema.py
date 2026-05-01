from __future__ import annotations

from typing import Any

GEMINI_SUPPORTED_FEATURES: Dict[str, bool] = {
    "function_calling": True,
    "streaming": True,
    "vision": True,
    "json_mode": True,
    "system_prompt": True,
    "multi_turn": True,
    "code_execution": True,
}


def convert_tools_to_gemini(tools: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    gemini_tools = []
    for tool in tools:
        if tool.get("type") == "function":
            func = tool.get("function", {})
            gemini_tool = {
                "functionDeclarations": [
                    {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "parameters": _convert_schema_to_gemini(func.get("parameters", {})),
                    }
                ]
            }
            gemini_tools.append(gemini_tool)
    return gemini_tools


def _convert_schema_to_gemini(schema: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    if "type" in schema:
        type_map = {
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
        }
        result["type"] = type_map.get(schema["type"], schema["type"])
    if "description" in schema:
        result["description"] = schema["description"]
    if "properties" in schema:
        result["properties"] = {
            k: _convert_schema_to_gemini(v) for k, v in schema["properties"].items()
        }
    if "required" in schema:
        result["required"] = schema["required"]
    if "items" in schema:
        result["items"] = _convert_schema_to_gemini(schema["items"])
    return result


def convert_response_from_gemini(response: Dict[str, Any]) -> Dict[str, Any]:
    candidates = response.get("candidates", [])
    if not candidates:
        return {"role": "assistant", "content": ""}
    candidate = candidates[0]
    content = candidate.get("content", {})
    parts = content.get("parts", [])
    text_parts = []
    for part in parts:
        if "text" in part:
            text_parts.append(part["text"])
    result = {
        "role": content.get("role", "assistant"),
        "content": "".join(text_parts),
    }
    function_call = None
    for part in parts:
        if "functionCall" in part:
            function_call = part["functionCall"]
            break
    if function_call:
        result["tool_calls"] = [
            {
                "id": f"call_{function_call.get('name', '')}",
                "type": "function",
                "function": {
                    "name": function_call.get("name", ""),
                    "arguments": function_call.get("args", {}),
                },
            }
        ]
    return result


def is_gemini_model(model: str) -> bool:
    model_lower = model.lower()
    return any(
        prefix in model_lower for prefix in ["gemini", "gemini-pro", "gemini-ultra", "gemini-1.5"]
    )
