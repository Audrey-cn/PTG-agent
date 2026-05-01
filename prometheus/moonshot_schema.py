from __future__ import annotations

from typing import Any

MOONSHOT_SUPPORTED_FEATURES: Dict[str, bool] = {
    "function_calling": True,
    "streaming": True,
    "vision": False,
    "json_mode": True,
    "system_prompt": True,
    "multi_turn": True,
}


def convert_tools_to_moonshot(tools: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    moonshot_tools = []
    for tool in tools:
        if tool.get("type") == "function":
            func = tool.get("function", {})
            moonshot_tool = {
                "type": "function",
                "function": {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                },
            }
            moonshot_tools.append(moonshot_tool)
    return moonshot_tools


def convert_response_from_moonshot(response: Dict[str, Any]) -> Dict[str, Any]:
    choices = response.get("choices", [])
    if not choices:
        return {"role": "assistant", "content": ""}
    choice = choices[0]
    message = choice.get("message", {})
    result = {
        "role": message.get("role", "assistant"),
        "content": message.get("content", ""),
    }
    tool_calls = message.get("tool_calls")
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


def is_moonshot_model(model: str) -> bool:
    model_lower = model.lower()
    return any(
        prefix in model_lower for prefix in ["moonshot", "kimi", "moonshot-v1", "moonshot-v2"]
    )
