
#!/usr/bin/env python3
"""
快速测试 Prometheus 配置系统
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🔥  PROMETHEUS 快速测试 🔥")
print("=" * 70)
print()

# 1. 初始化配置系统
print("1. 初始化配置目录...")
from prometheus.config import ensure_prometheus_home, get_prometheus_home
ensure_prometheus_home()
home = get_prometheus_home()
print(f"   配置目录: {home}")
print(f"   目录已创建: {home.exists()}")
print()

# 2. 测试皮肤系统
print("2. 测试皮肤系统...")
from prometheus import skin_engine
skins = skin_engine.list_skins()
print(f"   可用皮肤: {[s['name'] for s in skins]}")
skin_engine.set_active_skin("default")
print(f"   当前皮肤: {skin_engine.get_active_skin_name()}")
print()

# 3. 测试工具 emoji
print("3. 测试工具 Emoji...")
from prometheus import display
tools = ["stamp_seed", "trace_seed", "append_historical_note", "inspect_seed", "list_stamps"]
for tool in tools:
    emoji = display.get_tool_emoji(tool)
    print(f"   {emoji} {tool}")
print()

print("=" * 70)
print("✅ 快速测试通过！")
print("=" * 70)
print()

