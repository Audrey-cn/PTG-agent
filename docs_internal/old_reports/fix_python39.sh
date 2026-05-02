#!/bin/bash
# Fix Python 3.9 compatibility by adding `from __future__ import annotations` to all .py files
# that use `| None` syntax without the future import.

cd /Users/audrey/ptg-agent/prometheus

# List of files to fix
FILES=(
    "agent_loop.py"
    "prometheus.py"
    "tui_chat.py"
    "interactive_tui.py"
    "orchestrator.py"
    "mcp_serve.py"
    "logs.py"
    "logging_core.py"
    "image_routing.py"
    "memory_provider.py"
    "honcho_integration.py"
    "agent/auxiliary_client.py"
    "agent/prompt_builder.py"
    "agent/display.py"
    "agent/usage_pricing.py"
    "agent/image_routing.py"
    "agent/image_gen_provider.py"
    "agent/google_oauth.py"
    "agent/lazy_imports.py"
    "cli/doctor.py"
    "cli/setup.py"
    "cli/kanban_db.py"
    "cli/logs.py"
    "cli/banner.py"
    "cli/skills_hub.py"
    "cli/plugins.py"
    "cli/oneshot.py"
    "cli/memory_setup.py"
    "cli/profiles.py"
    "tools/browser/browser_tool.py"
    "tools/browser/browser_camofox.py"
    "tools/browser/browser_supervisor.py"
    "tools/browser/browser_camofox_state.py"
    "tools/browser_providers/firecrawl.py"
    "tools/browser_providers/browserbase.py"
    "tools/browser_providers/browser_use.py"
    "tools/devops/mcp_tool.py"
    "tools/devops/delegate_tool.py"
    "tools/devops/send_message_tool.py"
    "tools/devops/homeassistant_tool.py"
    "tools/devops/skills_tool.py"
    "tools/devops/skill_manager_tool.py"
    "tools/devops/skills_hub.py"
    "tools/devops/memory_tool.py"
    "tools/devops/mcp_oauth.py"
    "tools/file/file_tools.py"
    "tools/file/file_state.py"
    "tools/file/file_operations.py"
    "tools/file.py"
    "tools/vision_tools.py"
    "tools/terminal_tool.py"
    "tools/web/web_tools.py"
    "tools/web/session_search_tool.py"
    "tools/vector_memory.py"
    "tools/security/tirith_security.py"
    "tools/security/fuzzy_match.py"
    "tools/security/process_registry.py"
    "tools/security/approval.py"
    "tools/managed_tool_gateway.py"
    "tools/mixture_of_agents.py"
    "tools/rl_training_tool.py"
    "tools/slash_confirm.py"
    "tools/xget_integration.py"
    "tools/voice/voice_mode.py"
    "tools/voice/tts_tool.py"
    "tools/voice/transcription_tools.py"
    "tools/messaging/discord_tool.py"
    "gateway/platforms/telegram.py"
    "gateway/platforms/discord.py"
    "gateway/platforms/feishu.py"
    "gateway/platforms/wecom.py"
    "gateway/platforms/weixin.py"
    "gateway/platforms/email.py"
    "gateway/platforms/sms.py"
    "gateway/platforms/matrix.py"
    "gateway/platforms/signal.py"
    "gateway/platforms/wecom_callback.py"
    "gateway/platforms/telegram_network.py"
    "memory/state.py"
    "memory/backup.py"
    "hooks/shell_hooks.py"
    "genes/epigenetics.py"
    "genes/repair.py"
    "providers/__init__.py"
    "plugins/memory/__init__.py"
    "plugins/memory/honcho/__init__.py"
    "plugins/kanban/dashboard/plugin_api.py"
    "plugins/prometheus-achievements/dashboard/plugin_api.py"
    "plugins/platforms/teams/adapter.py"
    "plugins/platforms/irc/adapter.py"
    "plugins/spotify/client.py"
    "plugins/observability/langfuse/__init__.py"
    "plugins/disk-cleanup/disk_cleanup.py"
    "plugins/google_meet/realtime/openai_client.py"
    "plugins/google_meet/process_manager.py"
    "plugins/google_meet/meet_bot.py"
    "plugins/google_meet/cli.py"
    "tui_gateway/server.py"
)

for FILE in "${FILES[@]}"; do
    FULL_PATH="/Users/audrey/ptg-agent/prometheus/$FILE"
    
    if [ ! -f "$FULL_PATH" ]; then
        echo "SKIP (not found): $FILE"
        continue
    fi
    
    # Check if file already has the future import
    if grep -q "from __future__ import annotations" "$FULL_PATH"; then
        echo "OK (already has future import): $FILE"
        continue
    fi
    
    # Check if file uses `| None` syntax
    if ! grep -q "| None" "$FULL_PATH"; then
        echo "OK (doesn't use | None): $FILE"
        continue
    fi
    
    # Add the future import after the first line (or after docstring)
    # Strategy: Find the first line that is not a comment or docstring start
    LINE_NUM=$(head -n 10 "$FULL_PATH" | grep -n -m1 "^import\|^from\|^[A-Z]\|^[a-z]" | head -1 | cut -d: -f1)
    
    if [ -z "$LINE_NUM" ]; then
        LINE_NUM=1
    fi
    
    # Insert the future import at line 1
    sed -i '' '1s/^/from __future__ import annotations\n/' "$FULL_PATH"
    echo "FIXED: $FILE"
done

echo "Done!"
