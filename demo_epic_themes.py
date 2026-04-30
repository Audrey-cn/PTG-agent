
#!/usr/bin/env python3
"""
演示 Prometheus 史诗级主题系统
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prometheus import skin_engine, display

def print_separator(char="="):
    print(char * 70)

def demo_theme(name):
    skin_engine.set_active_skin(name)
    skin = skin_engine.get_active_skin()
    
    print_separator()
    print(f"\n🎭  主题：{skin.name.upper()}  ")
    print(f"📜  {skin.description}\n")
    print("欢迎语：", skin_engine.get_active_welcome())
    print("告别语：", skin_engine.get_active_goodbye())
    print("回复标签：", skin_engine.get_active_response_label())
    print("提示符：", skin_engine.get_active_prompt_symbol())
    print("帮助头：", skin_engine.get_active_help_header())
    print("工具前缀：", skin_engine.get_tool_prefix())
    print()
    
    print("颜文字表情：")
    print("  等待：", " ".join(display.KawaiiSpinner.get_waiting_faces()[:5]))
    print("  思考：", " ".join(display.KawaiiSpinner.get_thinking_faces()[:5]))
    print()
    
    print("工具 Emoji 映射：")
    tools = ["stamp_seed", "trace_seed", "append_historical_note", "inspect_seed", "list_stamps"]
    for tool in tools:
        emoji = display.get_tool_emoji(tool)
        print(f"  {emoji} {tool}")
    
    print()
    time.sleep(1)

def main():
    print("\n" + "🔥" * 70)
    print("🔥  PROMETHEUS 史诗级主题系统 DEMO  🔥")
    print("🔥" * 70 + "\n")
    
    for theme in ["default", "zeus", "athena", "hades"]:
        demo_theme(theme)
    
    print_separator()
    print("\n" + "🎊" * 15)
    print("  🎉 全部主题演示完成！🔥  ")
    print("🎊" * 15 + "\n")

if __name__ == "__main__":
    main()

