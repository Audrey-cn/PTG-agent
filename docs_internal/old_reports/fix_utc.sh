#!/bin/bash
# Fix Python 3.9 compatibility: replace datetime.UTC with datetime.timezone.utc

cd /Users/audrey/ptg-agent/prometheus

# List of files using UTC
FILES=(
    "gateway/platforms/signal.py"
    "tools/devops/skills_hub.py"
    "cli/main.py"
    "agent/usage_pricing.py"
    "tools/devops/skill_usage.py"
    "plugins/disk-cleanup/disk_cleanup.py"
    "gateway/platforms/sms.py"
    "tools/managed_tool_gateway.py"
    "gateway/platforms/qqbot/adapter.py"
    "gateway/platforms/dingtalk.py"
    "gateway/status.py"
    "cli/backup.py"
    "gateway/platforms/yuanbao.py"
    "tools/webhook_tool.py"
    "self_evolution/verifier.py"
    "self_evolution/observer.py"
    "self_evolution/learner.py"
    "agent/rate_limit_tracker.py"
    "cli/status.py"
    "tools/devops/skills_guard.py"
    "debug.py"
    "cli/curator.py"
    "bootstrap/workspace.py"
    "bootstrap/onboard.py"
    "agent/account_usage.py"
)

for FILE in "${FILES[@]}"; do
    FULL_PATH="/Users/audrey/ptg-agent/prometheus/$FILE"
    
    if [ ! -f "$FULL_PATH" ]; then
        echo "SKIP (not found): $FILE"
        continue
    fi
    
    # Fix the import
    if grep -q "from datetime import.*UTC" "$FULL_PATH"; then
        # Replace "from datetime import UTC, datetime" with "from datetime import datetime, timezone"
        sed -i '' 's/from datetime import UTC, datetime/from datetime import datetime, timezone/g' "$FULL_PATH"
        sed -i '' 's/from datetime import UTC$/from datetime import timezone/g' "$FULL_PATH"
        sed -i '' 's/from datetime import UTC, datetime, timedelta, timezone/from datetime import datetime, timedelta, timezone/g' "$FULL_PATH"
        sed -i '' 's/from datetime import UTC, datetime, timedelta/from datetime import datetime, timedelta, timezone/g' "$FULL_PATH"
        
        # Replace UTC usage with timezone.utc
        sed -i '' 's/UTC\./timezone.utc./g' "$FULL_PATH"
        sed -i '' 's/([^a-zA-Z_])UTC\([^a-zA-Z_]\)/\1timezone.utc\2/g' "$FULL_PATH"
        sed -i '' 's/([^a-zA-Z_])UTC$/\1timezone.utc/g' "$FULL_PATH"
        sed -i '' 's/= UTC$/= timezone.utc/g' "$FULL_PATH"
        
        echo "FIXED: $FILE"
    else
        echo "OK (no UTC import): $FILE"
    fi
done

echo "Done!"
