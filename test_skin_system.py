
#!/usr/bin/env python3
"""
测试 Prometheus 史诗级皮肤和 emoji 系统
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔥 测试 Prometheus 史诗级系统...\n")

try:
    # 测试皮肤引擎
    from prometheus import skin_engine
    print("✅ 皮肤引擎加载成功")
    
    # 列出皮肤
    skins = skin_engine.list_skins()
    print(f"\n📜 可用皮肤 ({len(skins)}):")
    for skin in skins:
        print(f"  - {skin['name']:10} {skin['description']}")
    
    # 获取当前皮肤
    active = skin_engine.get_active_skin()
    print(f"\n✨ 当前皮肤: {active.name}")
    print(f"  提示符: {skin_engine.get_active_prompt_symbol()}")
    print(f"  欢迎语: {skin_engine.get_active_welcome()}")
    print(f"  告别语: {skin_engine.get_active_goodbye()}")
    print(f"  工具前缀: {skin_engine.get_tool_prefix()}")
    
    # 测试皮肤切换
    print(f"\n🎭 测试皮肤切换:")
    for skin_name in ["zeus", "athena", "hades", "default"]:
        skin_engine.set_active_skin(skin_name)
        print(f"  - 切换到 {skin_name:10} → {skin_engine.get_active_prompt_symbol()}")
    
    # 测试显示系统
    from prometheus import display
    print("\n✅ 显示系统加载成功")
    
    # 测试工具 emoji 映射
    test_tools = [
        "stamp_seed",
        "trace_seed", 
        "append_historical_note",
        "inspect_seed",
        "list_stamps",
    ]
    
    print("\n😎 测试工具 emoji:")
    for tool in test_tools:
        emoji = display.get_tool_emoji(tool)
        print(f"  - {emoji} {tool}")
    
    # 测试 KawaiiSpinner
    print("\n🎠 测试 KawaiiSpinner (非交互模式):")
    spinner = display.KawaiiSpinner("测试动画")
    spinner.start()
    import time
    time.sleep(0.5)
    spinner.stop("动画测试完成")
    
    # 测试颜文字表情
    print("\n😊 测试颜文字表情:")
    print(f"  等待表情: {', '.join(display.KawaiiSpinner.get_waiting_faces())}")
    print(f"  思考表情: {', '.join(display.KawaiiSpinner.get_thinking_faces())}")
    
    print("\n🚀 测试工具预览:")
    preview = display.build_tool_preview("stamp_seed", {"seed_path": "my_seed.ttg", "mark": "Prometheus"})
    print(f"  - stamp_seed: {preview}")
    
    preview = display.build_tool_preview("append_historical_note", {"seed_path": "test.ttg", "note": "添加了重要历史记录"})
    print(f"  - append_historical_note: {preview}")
    
    preview = display.build_tool_preview("trace_seed", {"seed_path": "ancient_seed.ttg"})
    print(f"  - trace_seed: {preview}")
    
    print("\n✅ 所有测试通过！Prometheus 史诗级系统已就绪！🔥\n")

except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

