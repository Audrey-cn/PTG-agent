
#!/usr/bin/env python3
"""
Prometheus 史诗级配置系统 - 完整演示
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🔥  PROMETHEUS 史诗级配置系统 🔥")
print("=" * 70)
print()


# 1. 测试配置系统
print("📁 [1/4] 测试配置系统初始化...")
from prometheus.config import (
    get_prometheus_home,
    ensure_prometheus_home,
    PrometheusConfig,
    get_soul_content,
    load_env_vars,
    get_config_path,
    get_soul_path,
)
ensure_prometheus_home()
home = get_prometheus_home()
print(f"   配置目录: {home}")
print(f"   配置文件: {get_config_path()}")
print(f"   SOUL 文件: {get_soul_path()}")
print()


# 2. 加载 SOUL.md
print("📝 [2/4] 测试 SOUL.md 加载...")
soul_content = get_soul_content()
print(f"   SOUL.md 内容 ({len(soul_content)} chars):")
print("-" * 70)
if len(soul_content) &gt; 300:
    print(soul_content[:300] + "...")
else:
    print(soul_content)
print("-" * 70)
print()


# 3. 加载配置
print("⚙️ [3/4] 测试 config.yaml 加载...")
config = PrometheusConfig.load()
print(f"   当前配置版本: {config.get('_config_version')}")
print(f"   当前皮肤: {config.skin}")
print(f"   工具集: {config.get('toolsets')}")
print(f"   史诗编史官配置: {config.get('chronicler')}")
print()


# 4. 测试皮肤系统
print("🎨 [4/4] 测试皮肤系统...")
from prometheus import skin_engine
from prometheus import display
skins = skin_engine.list_skins()
print(f"   可用皮肤: {[s['name'] for s in skins]}")
for skin in skins:
    print()
    print(f"🎭  切换到: {skin['name']}")
    skin_engine.set_active_skin(skin['name'])
    config.skin = skin['name']
    
    print(f"   提示符: {skin_engine.get_active_prompt_symbol()}")
    print(f"   工具前缀: {skin_engine.get_tool_prefix()}")
    print(f"   工具 Emoji:")
    tools = ["stamp_seed", "trace_seed", "append_historical_note", "inspect_seed", "list_stamps"]
    for tool in tools:
        emoji = display.get_tool_emoji(tool)
        print(f"      {emoji} {tool}")
print()


# 保存皮肤到配置
skin_engine.set_active_skin("default")
config.skin = "default"
config.save()


print("=" * 70)
print("✅ 史诗级配置系统演示完成！！！")
print("=" * 70)
print()
print("📁 已创建的文件:")
print(f"   {get_config_path()}")
print(f"   {get_soul_path()}")
print(f"   {get_prometheus_home()}/")
print()

