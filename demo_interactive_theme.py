
#!/usr/bin/env python3
"""
交互式演示 Prometheus 主题系统
模拟终端中的真实使用体验
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prometheus import skin_engine, display

def typewriter_effect(text, delay=0.02):
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

def simulate_repl_conversation(theme):
    skin_engine.set_active_skin(theme)
    skin = skin_engine.get_active_skin()
    
    print("\n" + "=" * 70)
    print(f"🎭  模拟 {skin.name.upper()} 主题终端体验")
    print("=" * 70 + "\n")
    
    # 模拟启动横幅
    typewriter_effect(f"✨ {skin.get_branding('agent_name')} 正在启动...", 0.01)
    time.sleep(0.5)
    print()
    
    print("🔥 史诗级欢迎横幅：")
    print()
    print(f"{skin_engine.get_active_welcome()}")
    print()
    
    # 模拟 REPL 对话
    print("💬 模拟会话：")
    print("-" * 50)
    
    prompt = skin_engine.get_active_prompt_symbol()
    
    def print_user_message(msg):
        print(f"{prompt} {msg}")
        time.sleep(0.3)
    
    def print_assistant_message(msg):
        print(f"\n{skin_engine.get_active_response_label()}")
        print(f"  {msg}\n")
        time.sleep(0.5)
    
    # 对话1: 列出工具
    print_user_message("tools")
    time.sleep(0.5)
    print("📜 可用工具：")
    tools = ["stamp_seed", "trace_seed", "append_historical_note", "inspect_seed", "list_stamps"]
    for tool in tools:
        emoji = display.get_tool_emoji(tool)
        time.sleep(0.1)
        print(f"  {skin_engine.get_tool_prefix()} {emoji} {tool}")
    print()
    
    # 对话2: 检查种子
    print_user_message("inspect_seed my_seed.ttg")
    emoji = display.get_tool_emoji("inspect_seed")
    print(f"\n  {skin_engine.get_tool_prefix()} {emoji} 正在检查种子...")
    time.sleep(0.3)
    print_assistant_message("种子结构分析完成！发现 5 个永恒标签，创始契约完好！")
    
    # 对话3: 切换主题
    print_user_message("skin")
    time.sleep(0.2)
    print("当前可用主题：")
    print("  default (🔥) - 普罗米修斯")
    print("  zeus (⚡) - 宙斯")
    print("  athena (♀) - 雅典娜")
    print("  hades (💀) - 冥界")
    
    print()
    print("-" * 50)
    print("✅ 模拟会话结束！")
    print()
    time.sleep(1)

def main():
    print("\n" + "🔥" * 70)
    print("🔥  PROMETHEUS 史诗级主题系统 - 终端仿真 DEMO  🔥")
    print("🔥" * 70 + "\n")
    print("这个演示模拟在真实终端中使用不同主题的效果！\n")
    
    time.sleep(1)
    
    for theme in ["default", "zeus", "athena", "hades"]:
        simulate_repl_conversation(theme)
    
    print("\n" + "🎊" * 15)
    print("  🎉  全部终端仿真演示完成！🔥  ")
    print("🎊" * 15 + "\n")

if __name__ == "__main__":
    main()

