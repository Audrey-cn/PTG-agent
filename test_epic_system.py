
#!/usr/bin/env python3
"""
测试 Prometheus 史诗级系统
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔥 测试 Prometheus 史诗级系统...\n")

try:
    from prometheus import skin_engine
    print("✅ 皮肤引擎加载成功\n")
    
    skins = skin_engine.list_skins()
    print("📜 可用皮肤:")
    for s in skins:
        print(f"  - {s['name']:10} {s['description']}")
    print()
    
    active = skin_engine.get_active_skin()
    print("✨ 当前配置:")
    print(f"  皮肤: {active.name}")
    print(f"  欢迎: {skin_engine.get_active_welcome()}")
    print(f"  告别: {skin_engine.get_active_goodbye()}")
    print(f"  提示符: {skin_engine.get_active_prompt_symbol()}")
    print(f"  工具前缀: {skin_engine.get_tool_prefix()}")
    print()
    
    print("🎭 测试皮肤切换:")
    for name in ["zeus", "athena", "hades", "default"]:
        skin_engine.set_active_skin(name)
        print(f"  - {name:10} → {skin_engine.get_active_prompt_symbol()}")
    print()
    
    print("✅ 皮肤系统测试通过！\n")
    
    print("⚡ 测试工具 emoji 系统:")
    from prometheus import display
    tools = ["stamp_seed", "trace_seed", "append_historical_note", "inspect_seed", "list_stamps"]
    for tool in tools:
        emoji = display.get_tool_emoji(tool)
        print(f"  - {emoji} {tool}")
    print()
    
    print("✅ 全部史诗级系统测试通过！🔥\n")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

