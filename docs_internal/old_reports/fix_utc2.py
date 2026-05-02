#!/usr/bin/env python3
"""Fix Python 3.9 UTC compatibility issues"""

import os
import re

BASE_DIR = '/Users/audrey/ptg-agent/prometheus'

FILES_TO_FIX = [
    "gateway/platforms/signal.py",
    "tools/devops/skills_hub.py",
    "cli/main.py",  # Already fixed manually
    "agent/usage_pricing.py",
    "tools/devops/skill_usage.py",
    "plugins/disk-cleanup/disk_cleanup.py",
    "gateway/platforms/sms.py",
    "tools/managed_tool_gateway.py",
    "gateway/platforms/qqbot/adapter.py",
    "gateway/platforms/dingtalk.py",
    "gateway/status.py",
    "cli/backup.py",
    "gateway/platforms/yuanbao.py",
    "tools/webhook_tool.py",
    "self_evolution/verifier.py",
    "self_evolution/observer.py",
    "self_evolution/learner.py",
    "agent/rate_limit_tracker.py",
    "cli/status.py",
    "tools/devops/skills_guard.py",
    "debug.py",
    "cli/curator.py",
    "bootstrap/workspace.py",
    "bootstrap/onboard.py",
    "agent/account_usage.py",
]

fixed_count = 0
skipped_count = 0

for file_rel in FILES_TO_FIX:
    file_path = os.path.join(BASE_DIR, file_rel)
    
    if not os.path.exists(file_path):
        print(f"SKIP (not found): {file_rel}")
        skipped_count += 1
        continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if file uses UTC
    if 'UTC' not in content:
        print(f"OK (no UTC usage): {file_rel}")
        skipped_count += 1
        continue
    
    # Fix imports
    # Pattern 1: from datetime import UTC, datetime
    content = re.sub(
        r'from datetime import UTC, datetime\b',
        'from datetime import datetime, timezone',
        content
    )
    
    # Pattern 2: from datetime import UTC
    content = re.sub(
        r'from datetime import UTC$',
        'from datetime import timezone',
        content,
        flags=re.MULTILINE
    )
    
    # Pattern 3: from datetime import UTC, datetime, timedelta, timezone
    content = re.sub(
        r'from datetime import UTC, datetime, timedelta, timezone',
        'from datetime import datetime, timedelta, timezone',
        content
    )
    
    # Pattern 4: from datetime import UTC, datetime, timedelta
    content = re.sub(
        r'from datetime import UTC, datetime, timedelta\b',
        'from datetime import datetime, timedelta, timezone',
        content
    )
    
    # Fix UTC usage
    # Pattern 1: datetime.now(UTC) -> datetime.now(timezone.utc)
    content = re.sub(
        r'\bUTC\b(?=\s*[)\])',
        'timezone.utc',
        content
    )
    
    # Pattern 2: standalone UTC -> timezone.utc (but not in comments)
    content = re.sub(
        r'(?<![a-zA-Z_.])\bUTC\b(?![a-zA-Z_])',
        'timezone.utc',
        content
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"FIXED: {file_rel}")
    fixed_count += 1

print(f"\nTotal: {fixed_count} fixed, {skipped_count} skipped")
