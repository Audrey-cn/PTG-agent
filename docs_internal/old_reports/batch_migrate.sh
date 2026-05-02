#!/bin/bash
# Batch migration script for remaining CLI and plugin files
# Migrates load_config/save_config calls to PrometheusConfig API

cd /Users/audrey/ptg-agent/prometheus

# Function to migrate a file
migrate_file() {
    local FILE="$1"
    local FULL_PATH="/Users/audrey/ptg-agent/prometheus/$FILE"
    
    if [ ! -f "$FULL_PATH" ]; then
        echo "SKIP (not found): $FILE"
        return
    fi
    
    # Check if file needs migration
    if ! grep -q "from.*config.*import.*load_config\|from.*config.*import.*save_config" "$FULL_PATH"; then
        echo "OK (no migration needed): $FILE"
        return
    fi
    
    # Skip files already migrated
    if grep -q "from prometheus.config import.*PrometheusConfig" "$FULL_PATH" && ! grep -q "from prometheus.cli.config import.*load_config\|from prometheus.cli.config import.*save_config" "$FULL_PATH"; then
        echo "OK (already migrated): $FILE"
        return
    fi
    
    # Replace imports at module level
    sed -i '' 's/from prometheus\.cli\.config import load_config, save_config/from prometheus.config import PrometheusConfig, save_config/g' "$FULL_PATH"
    sed -i '' 's/from prometheus\.cli\.config import save_config, load_config/from prometheus.config import PrometheusConfig, save_config/g' "$FULL_PATH"
    sed -i '' 's/from prometheus\.cli\.config import load_config/from prometheus.config import PrometheusConfig/g' "$FULL_PATH"
    sed -i '' 's/from prometheus\.cli\.config import save_config/from prometheus.config import save_config/g' "$FULL_PATH"
    sed -i '' 's/from prometheus\.config import get_env_value, load_config/from prometheus.config import get_env_value, PrometheusConfig/g' "$FULL_PATH"
    sed -i '' 's/from prometheus\.config import load_config, save_config/from prometheus.config import PrometheusConfig, save_config/g' "$FULL_PATH"
    sed -i '' 's/from prometheus\.config import load_config/from prometheus.config import PrometheusConfig/g' "$FULL_PATH"
    
    # Replace load_config() calls
    sed -i '' 's/config = load_config()/config = PrometheusConfig.load().to_dict()/g' "$FULL_PATH"
    sed -i '' 's/config = load_config() or {}/config = PrometheusConfig.load().to_dict() or {}/g' "$FULL_PATH"
    sed -i '' 's/cfg = load_config()/cfg = PrometheusConfig.load()/g' "$FULL_PATH"
    sed -i '' 's/cfg = load_config() or {}/cfg = PrometheusConfig.load().to_dict() or {}/g' "$FULL_PATH"
    sed -i '' 's/_refreshed = load_config()/_refreshed = PrometheusConfig.load().to_dict()/g' "$FULL_PATH"
    sed -i '' 's/config = load_config() or {}/config = PrometheusConfig.load().to_dict() or {}/g' "$FULL_PATH"
    sed -i '' 's/config = load_config() or {}/config = PrometheusConfig.load().to_dict() or {}/g' "$FULL_PATH"
    
    # Replace cfg_get calls with .get() dot notation
    sed -i '' 's/cfg_get(config, "plugins", "disabled", default=\[\])/config.get("plugins.disabled", default=[])/g' "$FULL_PATH"
    sed -i '' 's/cfg_get(config, "plugins", "enabled", default=\[\])/config.get("plugins.enabled", default=[])/g' "$FULL_PATH"
    
    echo "MIGRATED: $FILE"
}

# Migrate CLI files
migrate_file "cli/plugins_cmd.py"
migrate_file "cli/dump.py"
migrate_file "cli/commands.py"
migrate_file "cli/claw.py"
migrate_file "cli/voice.py"
migrate_file "cli/kanban.py"
migrate_file "cli/timeouts.py"
migrate_file "cli/status.py"
migrate_file "cli/skills_config.py"
migrate_file "cli/runtime_provider.py"
migrate_file "cli/webhook.py"
migrate_file "cli/fallback_cmd.py"
migrate_file "cli/hooks.py"

# Migrate plugin files
migrate_file "plugins/memory/__init__.py"
migrate_file "plugins/kanban/dashboard/plugin_api.py"
migrate_file "plugins/memory/honcho/client.py"
migrate_file "plugins/memory/honcho/cli.py"
migrate_file "plugins/image_gen/openai-codex/__init__.py"
migrate_file "plugins/image_gen/xai/__init__.py"
migrate_file "plugins/image_gen/openai/__init__.py"

echo ""
echo "Migration complete!"
