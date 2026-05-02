#!/bin/bash
# Fix all remaining CLI issues

cd /Users/audrey/ptg-agent/prometheus

echo "=== 1. Fix UTC imports ==="

# Add from __future__ import annotations if missing
for FILE in cli/backup.py cli/curator.py; do
    if [ -f "$FILE" ]; then
        if ! grep -q "from __future__ import annotations" "$FILE"; then
            sed -i '' '1s/^/from __future__ import annotations\n/' "$FILE"
        fi
        # Fix UTC -> timezone.utc
        sed -i '' 's/from datetime import UTC, datetime/from datetime import datetime, timezone/g' "$FILE"
        sed -i '' 's/datetime\.now(UTC)/datetime.now(timezone.utc)/g' "$FILE"
        sed -i '' 's/([^a-zA-Z_])UTC\([^a-zA-Z_]\)/\1timezone.utc\2/g' "$FILE"
        echo "Fixed: $FILE"
    fi
done

echo ""
echo "=== 2. Add from __future__ to files with Python 3.10+ syntax ==="

for FILE in cli/cli_output.py cli/clipboard.py cli/cron.py cli/curses_ui.py cli/mcp_config.py cli/skin_engine.py cli/relaunch.py; do
    if [ -f "$FILE" ]; then
        if ! grep -q "from __future__ import annotations" "$FILE"; then
            sed -i '' '1s/^/from __future__ import annotations\n/' "$FILE"
            echo "Added future import: $FILE"
        fi
    fi
done

echo ""
echo "=== 3. Fix relaunch.py missing Tuple import ==="

if [ -f "cli/relaunch.py" ]; then
    if grep -q "from typing import" "cli/relaunch.py" && ! grep -q "Tuple" "cli/relaunch.py"; then
        sed -i '' 's/from typing import /from typing import Tuple, /g' "cli/relaunch.py"
        echo "Fixed relaunch.py Tuple import"
    fi
fi

echo ""
echo "=== Done ==="
