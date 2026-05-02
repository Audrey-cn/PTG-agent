"""Prometheus Tools — Lazy re-exports for backward compatibility.

All imports are deferred until first access to avoid circular-dependency
and missing-submodule failures during package initialization.
"""

__all__ = [
    "registry",
    "tool_result",
    "tool_error",
    "browser_tool",
    "browser_cdp_tool",
    "camofox_browser_tool",
    "browser_dialog_tool",
    "BrowserSupervisor",
    "SUPERVISOR_REGISTRY",
    "CamofoxState",
    "code_execution_tool",
    "file_read",
    "file_write",
    "file_search",
    "file_tool_handler",
    "file_state",
    "web_search",
    "web_fetch",
    "session_search_tool",
    "mcp_tool_handler",
    "mcp_oauth_handler",
    "MCPOAuthManager",
    "skills_hub_handler",
    "skills_sync_handler",
    "skills_guard_handler",
    "kanban_tool_handler",
    "memory_tool",
    "skill_manager_tool",
    "tts_tool",
    "enter_voice_mode",
    "exit_voice_mode",
    "transcribe_audio",
    "discord_tool",
    "slack_tool",
    "telegram_tool",
    "telegram_network_tool",
    "yuanbao_tool",
    "feishu_doc_tool",
    "feishu_drive_tool",
    "dingtalk_tool",
    "image_generation_tool",
    "vision_tool",
    "mixture_of_agents_tool",
    "cronjob_tool_handler",
    "cron_tool",
    "tirith_security_tool",
    "is_url_safe",
    "approve_session",
    "is_session_approved",
    "reject_session",
    "session_yolo_mode",
    "set_session_yolo",
    "sanitize_tool_schemas",
    "PathSecurity",
    "limit_tool_output",
    "ToolResultStorage",
    "fuzzy_match",
    "osv_vulnerability_check",
    "InterruptManager",
    "is_interrupted",
    "get_passthrough_env",
    "BudgetConfig",
    "ProcessRegistry",
    "PatchParser",
    "parse_patch",
    "BINARY_EXTENSIONS",
    "CheckpointManager",
    "send_message_tool",
    "delegate_tool",
    "todo_tool",
    "clarify_tool",
    "homeassistant_tool",
    "rl_training_tool",
    "managed_tool_gateway",
    "browser_camofox_tool",
    "CamofoxBrowserState",
    "xai_http_tool",
    "record_skill_usage",
    "get_credential_path",
    "read_credential_file",
    "environments",
    "browser_providers",
]

# Lazy import mapping
_LAZY_MAP = {
    # security / registry
    "registry": ("prometheus.tools.security.registry", "registry"),
    "tool_result": ("prometheus.tools.security.registry", "tool_result"),
    "tool_error": ("prometheus.tools.security.registry", "tool_error"),
    # security submodules
    "approve_session": ("prometheus.tools.security.approval", "approve_session"),
    "is_session_approved": ("prometheus.tools.security.approval", "is_session_approved"),
    "reject_session": ("prometheus.tools.security.approval", "reject_session"),
    "session_yolo_mode": ("prometheus.tools.security.approval", "session_yolo_mode"),
    "set_session_yolo": ("prometheus.tools.security.approval", "set_session_yolo"),
    "BudgetConfig": ("prometheus.tools.security.budget_config", "BudgetConfig"),
    "get_passthrough_env": ("prometheus.tools.security.env_passthrough", "get_passthrough_env"),
    "fuzzy_match": ("prometheus.tools.security.fuzzy_match", "fuzzy_match"),
    "InterruptManager": ("prometheus.tools.security.interrupt", "InterruptManager"),
    "is_interrupted": ("prometheus.tools.security.interrupt", "is_interrupted"),
    "osv_vulnerability_check": ("prometheus.tools.security.osv_check", "osv_vulnerability_check"),
    "PathSecurity": ("prometheus.tools.security.path_security", "PathSecurity"),
    "ProcessRegistry": ("prometheus.tools.security.process_registry", "ProcessRegistry"),
    "sanitize_tool_schemas": (
        "prometheus.tools.security.schema_sanitizer",
        "sanitize_tool_schemas",
    ),
    "tirith_security_tool": ("prometheus.tools.security.tirith_security", "tirith_security_tool"),
    "limit_tool_output": ("prometheus.tools.security.tool_output_limits", "limit_tool_output"),
    "ToolResultStorage": ("prometheus.tools.security.tool_result_storage", "ToolResultStorage"),
    "is_url_safe": ("prometheus.tools.security.url_safety", "is_url_safe"),
    # browser
    "browser_tool": ("prometheus.tools.browser.browser_tool", "browser_tool"),
    "browser_cdp_tool": ("prometheus.tools.browser.browser_cdp_tool", "browser_cdp_tool"),
    "browser_dialog_tool": ("prometheus.tools.browser.browser_dialog_tool", "browser_dialog_tool"),
    "BrowserSupervisor": ("prometheus.tools.browser.browser_supervisor", "BrowserSupervisor"),
    "SUPERVISOR_REGISTRY": ("prometheus.tools.browser.browser_supervisor", "SUPERVISOR_REGISTRY"),
    "CamofoxState": ("prometheus.tools.browser.browser_camofox_state", "CamofoxState"),
    # browser / camofox (may not be available)
    "camofox_browser_tool": ("prometheus.tools.browser.browser_camofox", "camofox_browser_tool"),
    # cron
    "cron_tool": ("prometheus.tools.cron.cron", "cron_tool"),
    "cronjob_tool_handler": ("prometheus.tools.cron.cronjob_tools", "cronjob_tool_handler"),
    # devops
    "CheckpointManager": ("prometheus.tools.devops.checkpoint_manager", "CheckpointManager"),
    "clarify_tool": ("prometheus.tools.devops.clarify_tool", "clarify_tool"),
    "get_credential_path": ("prometheus.tools.devops.credential_files", "get_credential_path"),
    "read_credential_file": ("prometheus.tools.devops.credential_files", "read_credential_file"),
    "delegate_tool": ("prometheus.tools.devops.delegate_tool", "delegate_tool"),
    "homeassistant_tool": ("prometheus.tools.devops.homeassistant_tool", "homeassistant_tool"),
    "kanban_tool_handler": ("prometheus.tools.devops.kanban_tools", "kanban_tool_handler"),
    "mcp_oauth_handler": ("prometheus.tools.devops.mcp_oauth", "mcp_oauth_handler"),
    "MCPOAuthManager": ("prometheus.tools.devops.mcp_oauth_manager", "MCPOAuthManager"),
    "mcp_tool_handler": ("prometheus.tools.devops.mcp_tool", "mcp_tool_handler"),
    "memory_tool": ("prometheus.tools.devops.memory_tool", "memory_tool"),
    "send_message_tool": ("prometheus.tools.devops.send_message_tool", "send_message_tool"),
    "skill_manager_tool": ("prometheus.tools.devops.skill_manager_tool", "skill_manager_tool"),
    "record_skill_usage": ("prometheus.tools.devops.skill_usage", "record_skill_usage"),
    "skills_guard_handler": ("prometheus.tools.devops.skills_guard", "skills_guard_handler"),
    "skills_hub_handler": ("prometheus.tools.devops.skills_hub", "skills_hub_handler"),
    "skills_sync_handler": ("prometheus.tools.devops.skills_sync", "skills_sync_handler"),
    "todo_tool": ("prometheus.tools.devops.todo_tool", "todo_tool"),
    # file
    "BINARY_EXTENSIONS": ("prometheus.tools.file.binary_extensions", "BINARY_EXTENSIONS"),
    "code_execution_tool": ("prometheus.tools.file.code_execution_tool", "code_execution_tool"),
    "file_read": ("prometheus.tools.file.file_operations", "file_read"),
    "file_write": ("prometheus.tools.file.file_operations", "file_write"),
    "file_search": ("prometheus.tools.file.file_operations", "file_search"),
    "file_tool_handler": ("prometheus.tools.file.file_tools", "file_tool_handler"),
    "file_state": ("prometheus.tools.file.file_state", "file_state"),
    "tool_backend_helpers": (
        "prometheus.tools.security.tool_backend_helpers",
        "tool_backend_helpers",
    ),
    "voice_mode": ("prometheus.tools.voice.voice_mode", "voice_mode"),
    "PatchParser": ("prometheus.tools.file.patch_parser", "PatchParser"),
    "parse_patch": ("prometheus.tools.file.patch_parser", "parse_patch"),
    # messaging
    "DiscordMessageTool": ("prometheus.tools.messaging.discord", "DiscordMessageTool"),
    "discord_tool": ("prometheus.tools.messaging.discord_tool", "discord_tool"),
    "SlackTool": ("prometheus.tools.messaging.slack", "SlackTool"),
    "telegram_tool": ("prometheus.tools.messaging.telegram", "TelegramTool"),
    "telegram_network_tool": (
        "prometheus.tools.messaging.telegram_network",
        "telegram_network_tool",
    ),
    # platform
    "browser_camofox_tool": ("prometheus.tools.platform.browser_camofox", "browser_camofox_tool"),
    "CamofoxBrowserState": (
        "prometheus.tools.platform.browser_camofox_state",
        "CamofoxBrowserState",
    ),
    "dingtalk_tool": ("prometheus.tools.platform.dingtalk", "dingtalk_tool"),
    "feishu_doc_tool": ("prometheus.tools.platform.feishu_doc_tool", "feishu_doc_tool"),
    "feishu_drive_tool": ("prometheus.tools.platform.feishu_drive_tool", "feishu_drive_tool"),
    "image_generation_tool": (
        "prometheus.tools.platform.image_generation_tool",
        "image_generation_tool",
    ),
    "managed_tool_gateway": (
        "prometheus.tools.platform.managed_tool_gateway",
        "managed_tool_gateway",
    ),
    "mixture_of_agents_tool": (
        "prometheus.tools.platform.mixture_of_agents",
        "mixture_of_agents_tool",
    ),
    "rl_training_tool": ("prometheus.tools.platform.rl_training_tool", "rl_training_tool"),
    "vision_tool": ("prometheus.tools.platform.vision_tools", "vision_tool"),
    "yuanbao_tool": ("prometheus.tools.platform.yuanbao_tools", "yuanbao_tool"),
    # voice
    "neutts_synth": ("prometheus.tools.voice.neutts_synth", "neutts_synth"),
    "transcribe_audio": ("prometheus.tools.voice.transcription_tools", "transcribe_audio"),
    "tts_tool": ("prometheus.tools.voice.tts_tool", "tts_tool"),
    "enter_voice_mode": ("prometheus.tools.voice.voice_mode", "enter_voice_mode"),
    "exit_voice_mode": ("prometheus.tools.voice.voice_mode", "exit_voice_mode"),
    # web
    "session_search_tool": ("prometheus.tools.web.session_search_tool", "session_search_tool"),
    "web_fetch": ("prometheus.tools.web.web_tools", "web_fetch"),
    "web_search": ("prometheus.tools.web.web_tools", "web_search"),
    "xai_http_tool": ("prometheus.tools.web.xai_http", "xai_http_tool"),
    # submodules
    "browser_providers": ("prometheus.tools.browser", "providers"),
    "environments": ("prometheus.tools", "environments"),
}

_cache = {}


def __getattr__(name: str):
    if name not in _LAZY_MAP:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    if name in _cache:
        return _cache[name]

    module_path, attr = _LAZY_MAP[name]
    try:
        import importlib

        mod = importlib.import_module(module_path)
        # If attr is "__module__" or attr matches the module's basename,
        # return the module itself (used for submodule re-exports like file_state).
        if attr == "__module__" or attr == module_path.split(".")[-1]:
            value = mod
        else:
            value = getattr(mod, attr)
        _cache[name] = value
        return value
    except Exception as e:
        raise AttributeError(f"Failed to load {name!r} from {module_path}: {e}") from e


_TOOL_MODULES = [
    "prometheus.tools.file.file_operations",
    "prometheus.tools.file.code_execution_tool",
    "prometheus.tools.file.code_execution_register",
    "prometheus.tools.file.file_tools",
    "prometheus.tools.file.file_state",
    "prometheus.tools.web.web_tools",
    "prometheus.tools.web.session_search_tool",
    "prometheus.tools.devops.mcp_tool",
    "prometheus.tools.devops.memory_tool",
    "prometheus.tools.devops.send_message_tool",
    "prometheus.tools.devops.todo_tool",
    "prometheus.tools.devops.clarify_tool",
    "prometheus.tools.devops.delegate_tool",
    "prometheus.tools.devops.kanban_tools",
    "prometheus.tools.devops.skill_manager_tool",
    "prometheus.tools.devops.skills_hub",
    "prometheus.tools.devops.skills_guard",
    "prometheus.tools.devops.skills_sync",
    "prometheus.tools.devops.skill_usage",
    "prometheus.tools.devops.checkpoint_manager",
    "prometheus.tools.browser.browser_tool",
    "prometheus.tools.browser.browser_cdp_tool",
    "prometheus.tools.browser.browser_dialog_tool",
    "prometheus.tools.browser.browser_camofox",
    "prometheus.tools.cron.cron",
    "prometheus.tools.cron.cronjob_tools",
    "prometheus.tools.messaging.discord_tool",
    "prometheus.tools.voice.tts_tool",
    "prometheus.tools.voice.transcription_tools",
    "prometheus.tools.voice.voice_mode",
    "prometheus.tools.platform.image_generation_tool",
    "prometheus.tools.platform.vision_tools",
    "prometheus.tools.platform.yuanbao_tools",
    "prometheus.tools.platform.feishu_doc_tool",
    "prometheus.tools.platform.feishu_drive_tool",
    "prometheus.tools.security.tirith_security",
    "prometheus.tools.security.tool_output_limits",
    "prometheus.tools.security.url_safety",
]

_initialized = False


def load_all_tools():
    """显式加载并注册所有工具。

    调用后 registry 将包含所有可用工具。
    """
    global _initialized
    if _initialized:
        return

    import logging

    logger = logging.getLogger(__name__)
    loaded = 0
    failed = 0

    from prometheus.tools.security.registry import registry

    before = len(registry._tools)

    for module_path in _TOOL_MODULES:
        try:
            import importlib

            importlib.import_module(module_path)
            loaded += 1
        except Exception as e:
            failed += 1
            logger.debug(f"Failed to load tool module {module_path}: {e}")

    after = len(registry._tools)
    _initialized = True

    logger.info(f"Tools initialized: {loaded} modules loaded, {failed} failed, {after - before} tools registered")
    return registry
