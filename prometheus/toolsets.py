#!/usr/bin/env python3
"""Toolsets Module."""

from typing import Any

# Shared tool list for CLI and all messaging platform toolsets.
# Edit this once to update all platforms simultaneously.
_PROMETHEUS_CORE_TOOLS = [
    # Web
    "web_search",
    "web_extract",
    # Terminal + process management
    "terminal",
    "process",
    # File manipulation
    "read_file",
    "write_file",
    "patch",
    "search_files",
    # Vision + image generation
    "vision_analyze",
    "image_generate",
    # Skills
    "skills_list",
    "skill_view",
    "skill_manage",
    # Browser automation
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_back",
    "browser_press",
    "browser_get_images",
    "browser_vision",
    "browser_console",
    "browser_cdp",
    "browser_dialog",
    # Text-to-speech
    "text_to_speech",
    # Planning & memory
    "todo",
    "memory",
    # Session history search
    "session_search",
    # Clarifying questions
    "clarify",
    # Code execution + delegation
    "execute_code",
    "delegate_task",
    # Cronjob management
    "cronjob",
    # Cross-platform messaging (gated on gateway running via check_fn)
    "send_message",
    # Home Assistant smart home control (gated on HASS_TOKEN via check_fn)
    "ha_list_entities",
    "ha_get_state",
    "ha_list_services",
    "ha_call_service",
    # Prometheus-specific
    "genes",
    "snapshot",
    "knowledge",
    "chronicler_tools",
]


# Core toolset definitions
# These can include individual tools or reference other toolsets
TOOLSETS = {
    # Basic toolsets - individual tool categories
    "web": {
        "description": "Web research and content extraction tools",
        "tools": ["web_search", "web_extract"],
        "includes": [],  # No other toolsets included
    },
    "search": {
        "description": "Web search only (no content extraction/scraping)",
        "tools": ["web_search"],
        "includes": [],
    },
    "vision": {
        "description": "Image analysis and vision tools",
        "tools": ["vision_analyze"],
        "includes": [],
    },
    "image_gen": {
        "description": "Creative generation tools (images)",
        "tools": ["image_generate"],
        "includes": [],
    },
    "terminal": {
        "description": "Terminal/command execution and process management tools",
        "tools": ["terminal", "process"],
        "includes": [],
    },
    "moa": {
        "description": "Advanced reasoning and problem-solving tools",
        "tools": ["mixture_of_agents"],
        "includes": [],
    },
    "skills": {
        "description": "Access, create, edit, and manage skill documents with specialized instructions and knowledge",
        "tools": ["skills_list", "skill_view", "skill_manage"],
        "includes": [],
    },
    "browser": {
        "description": "Browser automation for web interaction (navigate, click, type, scroll, iframes, hold-click) with web search for finding URLs",
        "tools": [
            "browser_navigate",
            "browser_snapshot",
            "browser_click",
            "browser_type",
            "browser_scroll",
            "browser_back",
            "browser_press",
            "browser_get_images",
            "browser_vision",
            "browser_console",
            "browser_cdp",
            "browser_dialog",
            "web_search",
        ],
        "includes": [],
    },
    "cronjob": {
        "description": "Cronjob management tool - create, list, update, pause, resume, remove, and trigger scheduled tasks",
        "tools": ["cronjob"],
        "includes": [],
    },
    "messaging": {
        "description": "Cross-platform messaging: send messages to Telegram, Discord, Slack, SMS, etc.",
        "tools": ["send_message"],
        "includes": [],
    },
    "rl": {
        "description": "RL training tools for running reinforcement learning",
        "tools": [
            "rl_list_environments",
            "rl_select_environment",
            "rl_get_current_config",
            "rl_edit_config",
            "rl_start_training",
            "rl_check_status",
            "rl_stop_training",
            "rl_get_results",
            "rl_list_runs",
            "rl_test_inference",
        ],
        "includes": [],
    },
    "file": {
        "description": "File manipulation tools: read, write, patch (with fuzzy matching), and search (content + files)",
        "tools": ["read_file", "write_file", "patch", "search_files"],
        "includes": [],
    },
    "tts": {
        "description": "Text-to-speech: convert text to audio",
        "tools": ["text_to_speech"],
        "includes": [],
    },
    "todo": {
        "description": "Task planning and tracking for multi-step work",
        "tools": ["todo"],
        "includes": [],
    },
    "memory": {
        "description": "Persistent memory across sessions (personal notes + user profile)",
        "tools": ["memory"],
        "includes": [],
    },
    "session_search": {
        "description": "Search and recall past conversations with summarization",
        "tools": ["session_search"],
        "includes": [],
    },
    "clarify": {"description": "Ask clarifying questions", "tools": ["clarify"], "includes": []},
    "code_execution": {
        "description": "Run Python scripts that call tools programmatically",
        "tools": ["execute_code"],
        "includes": [],
    },
    "delegation": {
        "description": "Spawn subagents with isolated context for complex subtasks",
        "tools": ["delegate_task"],
        "includes": [],
    },
    "homeassistant": {
        "description": "Home Assistant smart home control and monitoring",
        "tools": ["ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service"],
        "includes": [],
    },
    "discord": {
        "description": "Discord read and participate tools (fetch messages, search members, create threads)",
        "tools": ["discord"],
        "includes": [],
    },
    "discord_admin": {
        "description": "Discord server management (list channels/roles, pin messages, assign roles)",
        "tools": ["discord_admin"],
        "includes": [],
    },
    # Prometheus-specific
    "prometheus": {
        "description": "Prometheus-specific tools: genes, snapshots, knowledge, chronicler",
        "tools": ["genes", "snapshot", "knowledge", "chronicler_tools"],
        "includes": [],
    },
    # Scenario-specific
    "debugging": {
        "description": "Debugging and troubleshooting toolkit",
        "tools": ["terminal", "process"],
        "includes": ["web", "file"],  # For searching error messages and solutions
    },
    "safe": {
        "description": "Safe toolkit without terminal access",
        "tools": [],
        "includes": ["web", "vision", "image_gen"],
    },
    # Prometheus-specific toolsets
    "prometheus-cli": {
        "description": "Prometheus CLI toolset with all core plus Prometheus-specific",
        "tools": _PROMETHEUS_CORE_TOOLS + ["genes", "snapshot", "knowledge", "chronicler_tools"],
        "includes": [],
    },
    "prometheus-acp": {
        "description": "Prometheus ACP integration (editors)",
        "tools": [
            "web_search",
            "web_extract",
            "terminal",
            "process",
            "read_file",
            "write_file",
            "patch",
            "search_files",
            "vision_analyze",
            "skills_list",
            "skill_view",
            "skill_manage",
            "browser_navigate",
            "browser_snapshot",
            "browser_click",
            "browser_type",
            "browser_scroll",
            "browser_back",
            "browser_press",
            "browser_get_images",
            "browser_vision",
            "browser_console",
            "browser_cdp",
            "browser_dialog",
            "todo",
            "memory",
            "session_search",
            "execute_code",
            "delegate_task",
            "genes",
            "snapshot",
            "knowledge",
            "chronicler_tools",
        ],
        "includes": [],
    },
    "prometheus-api-server": {
        "description": "Prometheus API server (without interactive UI tools)",
        "tools": [
            "web_search",
            "web_extract",
            "terminal",
            "process",
            "read_file",
            "write_file",
            "patch",
            "search_files",
            "vision_analyze",
            "image_generate",
            "skills_list",
            "skill_view",
            "skill_manage",
            "browser_navigate",
            "browser_snapshot",
            "browser_click",
            "browser_type",
            "browser_scroll",
            "browser_back",
            "browser_press",
            "browser_get_images",
            "browser_vision",
            "browser_console",
            "browser_cdp",
            "browser_dialog",
            "todo",
            "memory",
            "session_search",
            "execute_code",
            "delegate_task",
            "cronjob",
            "genes",
            "snapshot",
            "knowledge",
            "chronicler_tools",
        ],
        "includes": [],
    },
    "prometheus-gateway": {
        "description": "Prometheus gateway toolset (union of all platform tools)",
        "tools": [],
        "includes": ["prometheus-cli"],
    },
}


def get_toolset(name: str) -> dict[str, Any] | None:
    """
    Get a toolset definition by name.

    Args:
        name (str): Name of the toolset

    Returns:
        Dict: Toolset definition with description, tools, and includes
        None: If toolset not found
    """
    toolset = TOOLSETS.get(name)
    if toolset:
        return toolset

    try:
        from prometheus.tools.registry import registry
    except Exception:
        return None

    registry_toolset = name
    description = f"Plugin toolset: {name}"
    alias_target = registry.get_toolset_alias_target(name)

    if name not in _get_plugin_toolset_names():
        registry_toolset = alias_target
        if not registry_toolset:
            return None
        description = f"MCP server '{name}' tools"
    else:
        reverse_aliases = {
            canonical: alias
            for alias, canonical in _get_registry_toolset_aliases().items()
            if alias not in TOOLSETS
        }
        alias = reverse_aliases.get(name)
        if alias:
            description = f"MCP server '{alias}' tools"

    return {
        "description": description,
        "tools": registry.get_tool_names_for_toolset(registry_toolset),
        "includes": [],
    }


def resolve_toolset(name: str, visited: set[str] = None) -> list[str]:
    """
    Recursively resolve a toolset to get all tool names.

    This function handles toolset composition by recursively resolving
    included toolsets and combining all tools.

    Args:
        name (str): Name of the toolset to resolve
        visited (Set[str]): Set of already visited toolsets (cycle detection)

    Returns:
        List[str]: List of all tool names in the toolset
    """
    if visited is None:
        visited = set()

    # Special aliases that represent all tools across every toolset
    if name in {"all", "*"}:
        all_tools: set[str] = set()
        for toolset_name in get_toolset_names():
            resolved = resolve_toolset(toolset_name, visited.copy())
            all_tools.update(resolved)
        return sorted(all_tools)

    if name in visited:
        return []

    visited.add(name)

    toolset = get_toolset(name)
    if not toolset:
        return []

    tools = set(toolset.get("tools", []))

    for included_name in toolset.get("includes", []):
        included_tools = resolve_toolset(included_name, visited)
        tools.update(included_tools)

    return sorted(tools)


def resolve_multiple_toolsets(toolset_names: list[str]) -> list[str]:
    """
    Resolve multiple toolsets and combine their tools.

    Args:
        toolset_names (List[str]): List of toolset names to resolve

    Returns:
        List[str]: Combined list of all tool names (deduplicated)
    """
    all_tools = set()

    for name in toolset_names:
        tools = resolve_toolset(name)
        all_tools.update(tools)

    return sorted(all_tools)


def _get_plugin_toolset_names() -> set[str]:
    """Return toolset names registered by plugins."""
    try:
        from prometheus.tools.registry import registry

        return {
            toolset_name
            for toolset_name in registry.get_registered_toolset_names()
            if toolset_name not in TOOLSETS
        }
    except Exception:
        return set()


def _get_registry_toolset_aliases() -> dict[str, str]:
    """Return explicit toolset aliases registered in the live registry."""
    try:
        from prometheus.tools.registry import registry

        return registry.get_registered_toolset_aliases()
    except Exception:
        return {}


def get_all_toolsets() -> dict[str, dict[str, Any]]:
    """
    Get all available toolsets with their definitions.

    Includes both statically-defined toolsets and plugin-registered ones.

    Returns:
        Dict: All toolset definitions
    """
    result = dict(TOOLSETS)
    aliases = _get_registry_toolset_aliases()
    for ts_name in _get_plugin_toolset_names():
        display_name = ts_name
        for alias, canonical in aliases.items():
            if canonical == ts_name and alias not in TOOLSETS:
                display_name = alias
                break
        if display_name in result:
            continue
        toolset = get_toolset(display_name)
        if toolset:
            result[display_name] = toolset
    return result


def get_toolset_names() -> list[str]:
    """
    Get names of all available toolsets.

    Includes plugin-registered toolset names.

    Returns:
        List[str]: List of toolset names
    """
    names = set(TOOLSETS.keys())
    aliases = _get_registry_toolset_aliases()
    for ts_name in _get_plugin_toolset_names():
        for alias, canonical in aliases.items():
            if canonical == ts_name and alias not in TOOLSETS:
                names.add(alias)
                break
        else:
            names.add(ts_name)
    return sorted(names)


def validate_toolset(name: str) -> bool:
    """
    Check if a toolset name is valid.

    Args:
        name (str): Toolset name to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if name in {"all", "*"}:
        return True
    if name in TOOLSETS:
        return True
    if name in _get_plugin_toolset_names():
        return True
    return name in _get_registry_toolset_aliases()


def create_custom_toolset(
    name: str, description: str, tools: list[str] = None, includes: list[str] = None
) -> None:
    """
    Create a custom toolset at runtime.

    Args:
        name (str): Name for the new toolset
        description (str): Description of the toolset
        tools (List[str]): Direct tools to include
        includes (List[str]): Other toolsets to include
    """
    TOOLSETS[name] = {"description": description, "tools": tools or [], "includes": includes or []}


def get_toolset_info(name: str) -> dict[str, Any]:
    """
    Get detailed information about a toolset.

    Args:
        name (str): Toolset name

    Returns:
        Dict: Detailed toolset information
    """
    toolset = get_toolset(name)
    if not toolset:
        return None

    resolved_tools = resolve_toolset(name)

    return {
        "name": name,
        "description": toolSet["description"],
        "direct_tools": toolSet["tools"],
        "includes": toolSet["includes"],
        "resolved_tools": resolved_tools,
        "tool_count": len(resolved_tools),
        "is_composite": bool(toolSet["includes"]),
    }


if __name__ == "__main__":
    print("Prometheus Toolsets System Demo")
    print("=" * 60)

    print("\nAvailable Toolsets:")
    print("-" * 40)
    for name, _toolset in get_all_toolsets().items():
        info = get_toolset_info(name)
        composite = "[composite]" if info["is_composite"] else "[leaf]"
        print(f"  {composite} {name:20} - {toolSet['description']}")
        print(f"     Tools: {len(info['resolved_tools'])} total")

    print("\nToolset Resolution Examples:")
    print("-" * 40)
    for name in ["web", "terminal", "safe", "prometheus-cli"]:
        tools = resolve_toolset(name)
        print(f"\n  {name}:")
        print(f"    Resolved to {len(tools)} tools: {', '.join(sorted(tools))}")

    print("\nMultiple Toolset Resolution:")
    print("-" * 40)
    combined = resolve_multiple_toolsets(["web", "vision", "terminal", "prometheus"])
    print("  Combining ['web', 'vision', 'terminal', 'prometheus']:")
    print(f"    Result: {', '.join(sorted(combined))}")
