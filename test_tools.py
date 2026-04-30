
#!/usr/bin/env python3
"""
测试 Prometheus 工具系统
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔥 测试 Prometheus 工具系统...")
print()

try:
    from prometheus.tools.registry import registry, discover_builtin_tools
    
    print("1. 发现并加载工具...")
    loaded = discover_builtin_tools()
    print(f"   成功加载 {len(loaded)} 个工具模块")
    print()
    
    print("2. 列出所有可用工具:")
    tool_names = registry.get_all_tool_names()
    if not tool_names:
        print("   (未找到工具)")
    else:
        for name in tool_names:
            emoji = registry.get_emoji(name)
            toolset = registry.get_toolset_for_tool(name)
            print(f"   {emoji} {name} (工具集: {toolset})")
    print()
    
    print("3. 列出工具集:")
    toolsets = registry.get_registered_toolset_names()
    for ts in toolsets:
        tools = registry.get_tool_names_for_toolset(ts)
        print(f"   {ts}: {len(tools)} 个工具")
    print()
    
    print("✅ 测试完成！")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

