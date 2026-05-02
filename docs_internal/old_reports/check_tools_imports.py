"""Quick check for all tools/__init__.py imports."""
import importlib

imports_to_check = [
    ("prometheus.tools.browser", "browser_camofox", "camofox_browser_tool"),
    ("prometheus.tools.browser", "browser_camofox_state", "CamofoxState"),
    ("prometheus.tools.browser", "browser_cdp_tool", "browser_cdp_tool"),
    ("prometheus.tools.browser", "browser_dialog_tool", "browser_dialog_tool"),
    ("prometheus.tools.browser", "browser_supervisor", "SUPERVISOR_REGISTRY"),
    ("prometheus.tools.browser", "browser_tool", "browser_tool"),
    ("prometheus.tools.cron", "cron", "cron_tool"),
    ("prometheus.tools.cron", "cronjob_tools", "cronjob_tool_handler"),
    ("prometheus.tools.devops", "checkpoint_manager", "CheckpointManager"),
    ("prometheus.tools.devops", "clarify_tool", "clarify_tool"),
    ("prometheus.tools.devops", "credential_files", "get_credential_path"),
    ("prometheus.tools.devops", "delegate_tool", "delegate_tool"),
    ("prometheus.tools.devops", "homeassistant_tool", "homeassistant_tool"),
    ("prometheus.tools.devops", "kanban_tools", "kanban_tool_handler"),
    ("prometheus.tools.devops", "mcp_oauth", "mcp_oauth_handler"),
    ("prometheus.tools.devops", "mcp_oauth_manager", "MCPOAuthManager"),
    ("prometheus.tools.devops", "mcp_tool", "mcp_tool_handler"),
    ("prometheus.tools.devops", "memory_tool", "memory_tool"),
    ("prometheus.tools.devops", "send_message_tool", "send_message_tool"),
    ("prometheus.tools.devops", "skill_manager_tool", "skill_manager_tool"),
    ("prometheus.tools.devops", "skill_usage", "record_skill_usage"),
    ("prometheus.tools.devops", "skills_guard", "skills_guard_handler"),
    ("prometheus.tools.devops", "skills_hub", "skills_hub_handler"),
    ("prometheus.tools.devops", "skills_sync", "skills_sync_handler"),
    ("prometheus.tools.devops", "todo_tool", "todo_tool"),
    ("prometheus.tools.file", "binary_extensions", "BINARY_EXTENSIONS"),
    ("prometheus.tools.file", "code_execution_tool", "code_execution_tool"),
    ("prometheus.tools.file", "file_operations", "file_read"),
    ("prometheus.tools.file", "file_tools", "file_tool_handler"),
    ("prometheus.tools.file", "patch_parser", "PatchParser"),
    ("prometheus.tools.messaging", "discord", "DiscordMessageTool"),
    ("prometheus.tools.messaging", "discord_tool", "discord_tool"),
    ("prometheus.tools.messaging", "slack", "SlackTool"),
    ("prometheus.tools.messaging", "telegram", "TelegramTool"),
    ("prometheus.tools.messaging", "telegram_network", "telegram_network_tool"),
    ("prometheus.tools.platform", "browser_camofox", "browser_camofox_tool"),
    ("prometheus.tools.platform", "browser_camofox_state", "CamofoxBrowserState"),
    ("prometheus.tools.platform", "dingtalk", "dingtalk_tool"),
    ("prometheus.tools.platform", "feishu_doc_tool", "feishu_doc_tool"),
    ("prometheus.tools.platform", "feishu_drive_tool", "feishu_drive_tool"),
    ("prometheus.tools.platform", "image_generation_tool", "image_generation_tool"),
    ("prometheus.tools.platform", "managed_tool_gateway", "managed_tool_gateway"),
    ("prometheus.tools.platform", "mixture_of_agents", "mixture_of_agents_tool"),
    ("prometheus.tools.platform", "rl_training_tool", "rl_training_tool"),
    ("prometheus.tools.platform", "vision_tools", "vision_tool"),
    ("prometheus.tools.platform", "yuanbao_tools", "yuanbao_tool"),
    ("prometheus.tools.security", "approval", "approve_session"),
    ("prometheus.tools.security", "budget_config", "BudgetConfig"),
    ("prometheus.tools.security", "env_passthrough", "get_passthrough_env"),
    ("prometheus.tools.security", "fuzzy_match", "fuzzy_match"),
    ("prometheus.tools.security", "interrupt", "InterruptManager"),
    ("prometheus.tools.security", "osv_check", "osv_vulnerability_check"),
    ("prometheus.tools.security", "path_security", "PathSecurity"),
    ("prometheus.tools.security", "process_registry", "ProcessRegistry"),
    ("prometheus.tools.security", "registry", "registry"),
    ("prometheus.tools.security", "schema_sanitizer", "sanitize_tool_schemas"),
    ("prometheus.tools.security", "tirith_security", "tirith_security_tool"),
    ("prometheus.tools.security", "tool_output_limits", "limit_tool_output"),
    ("prometheus.tools.security", "tool_result_storage", "ToolResultStorage"),
    ("prometheus.tools.security", "url_safety", "is_url_safe"),
    ("prometheus.tools.voice", "neutts_synth", "neutts_synth"),
    ("prometheus.tools.voice", "transcription_tools", "transcribe_audio"),
    ("prometheus.tools.voice", "tts_tool", "tts_tool"),
    ("prometheus.tools.voice", "voice_mode", "enter_voice_mode"),
    ("prometheus.tools.web", "session_search_tool", "session_search_tool"),
    ("prometheus.tools.web", "web_tools", "web_fetch"),
    ("prometheus.tools.web", "xai_http", "xai_http_tool"),
]

errors = []
ok_count = 0

for module_path, submodule, symbol in imports_to_check:
    try:
        full = f"{module_path}.{submodule}"
        mod = importlib.import_module(full)
        val = getattr(mod, symbol, None)
        if val is None:
            errors.append(f"  MISSING: {full}.{symbol}")
        else:
            ok_count += 1
    except Exception as e:
        errors.append(f"  ERROR: {module_path}.{submodule}: {type(e).__name__}: {e}")

if errors:
    print(f"Found {len(errors)} errors ({ok_count} OK):\n")
    for e in errors:
        print(e)
else:
    print(f"All {ok_count} imports OK")
