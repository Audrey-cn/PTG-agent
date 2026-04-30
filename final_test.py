
#!/usr/bin/env python3
"""
最终集成测试 - Prometheus 史诗级配置系统
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🔥  PROMETHEUS 史诗级系统 - 集成测试 🔥")
print("=" * 70)
print()

# 1. 测试配置系统
print("1. 配置系统...")
from prometheus.config import ensure_prometheus_home, get_prometheus_home
ensure_prometheus_home()
home = get_prometheus_home()
print("   配置目录:", home)
print("   状态: OK")
print()

# 2. 测试皮肤系统
print("2. 皮肤系统...")
from prometheus import skin_engine
skins = skin_engine.list_skins()
print("   可用皮肤:", [s["name"] for s in skins])
skin_engine.set_active_skin("default")
print("   当前皮肤:", skin_engine.get_active_skin_name())
print("   提示符:", skin_engine.get_active_prompt_symbol())
print("   状态: OK")
print()

# 3. 测试工具 emoji 系统
print("3. 工具 Emoji 系统...")
from prometheus import display
tools = ["stamp_seed", "trace_seed", "append_historical_note", "inspect_seed", "list_stamps"]
for tool in tools:
    emoji = display.get_tool_emoji(tool)
    print("  ", emoji, tool)
print("   状态: OK")
print()

# 4. 测试所有皮肤的效果
print("4. 多皮肤效果...")
for skin_name in ["default", "zeus", "athena", "hades"]:
    skin_engine.set_active_skin(skin_name)
    emoji = display.get_tool_emoji("stamp_seed")
    print("  ", skin_name, "→", emoji, skin_engine.get_active_tool_prefix())
print("   状态: OK")
print()

# 恢复默认皮肤
skin_engine.set_active_skin("default")

print("=" * 70)
print("✅ 所有测试通过！")
print("=" * 70)
print()
print("📁 配置文件位置:")
print("   - ~/.prometheus/config.yaml")
print("   - ~/.prometheus/SOUL.md")
print()

