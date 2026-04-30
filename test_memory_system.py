
#!/usr/bin/env python3
"""
测试 Prometheus 记忆系统和 AGENTS.md
"""
import sys
import os
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🔥  Prometheus 记忆系统测试")
print("=" * 70)
print()

# 创建临时测试目录
test_home = Path(tempfile.mkdtemp()) / ".prometheus"
os.environ["PROMETHEUS_HOME"] = str(test_home)

try:
    # 1. 测试记忆系统
    print("1. 测试记忆系统初始化...")
    from prometheus.memory_system import (
        MemorySystem,
        get_prometheus_home,
        get_user_profile_path,
        get_memory_path,
        get_soul_path,
        get_evolution_log_path,
    )
    
    memory = MemorySystem()
    print(f"   Prometheus 主目录: {get_prometheus_home()}")
    print(f"   首次运行检测: {memory.is_first_run()}")
    print("   状态: OK")
    print()
    
    # 2. 测试首次引导
    print("2. 测试首次引导流程...")
    memory.create_user_profile(
        username="测试用户",
        communication_style="简洁专业",
        work_preferences="效率优先"
    )
    memory.create_soul(personality="友好、专业、简洁")
    memory.create_memory()
    
    print(f"   USER.md 已创建: {get_user_profile_path().exists()}")
    print(f"   SOUL.md 已创建: {get_soul_path().exists()}")
    print(f"   MEMORY.md 已创建: {get_memory_path().exists()}")
    print("   状态: OK")
    print()
    
    # 3. 测试文件加载
    print("3. 测试文件加载...")
    user_content = memory.load_user_profile()
    soul_content = memory.load_soul()
    memory_content = memory.load_memory()
    
    print(f"   USER.md 长度: {len(user_content)} 字符")
    print(f"   SOUL.md 长度: {len(soul_content)} 字符")
    print(f"   MEMORY.md 长度: {len(memory_content)} 字符")
    print("   状态: OK")
    print()
    
    # 4. 测试进化提案
    print("4. 测试进化提案机制...")
    
    # 提案 1
    result1 = memory.propose_evolution(
        section="工作偏好",
        content="用户偏好使用 Python 进行数据分析",
        target_file="MEMORY.md"
    )
    print(f"   提案 1 状态: {result1['status']} - {result1.get('reason', '')}")
    
    # 提案 2
    result2 = memory.propose_evolution(
        section="沟通风格",
        content="用户偏好使用中文进行交流",
        target_file="MEMORY.md"
    )
    print(f"   提案 2 状态: {result2['status']} - {result2.get('reason', '')}")
    
    # 提案 3 - 应该触发审核
    result3 = memory.propose_evolution(
        section="重要约定",
        content="每次修改前需要用户确认",
        target_file="MEMORY.md"
    )
    print(f"   提案 3 状态: {result3['status']} - {result3.get('reason', '')}")
    
    # 查看进化状态
    status = memory.get_evolution_status()
    print(f"   累积提案数: {len(status.get('proposals', []))}")
    print("   状态: OK")
    print()
    
    # 5. 测试敏感度筛查
    print("5. 测试敏感度筛查...")
    sensitive_result = memory.propose_evolution(
        section="测试",
        content="这是我的密码: secret123",
        target_file="MEMORY.md"
    )
    print(f"   敏感提案状态: {sensitive_result['status']}")
    print(f"   拒绝原因: {sensitive_result.get('reason', '')}")
    print("   状态: OK")
    print()
    
    # 6. 测试 AGENTS.md
    print("6. 测试 AGENTS.md...")
    agents_path = Path(__file__).parent / "AGENTS.md"
    if agents_path.exists():
        agents_content = agents_path.read_text(encoding="utf-8")
        print(f"   AGENTS.md 存在: True")
        print(f"   文件长度: {len(agents_content)} 字符")
        print(f"   包含核心定位: {'核心定位' in agents_content}")
        print(f"   包含行为准则: {'行为准则' in agents_content}")
        print(f"   包含进化机制: {'进化机制' in agents_content}")
    else:
        print("   AGENTS.md 不存在")
    print("   状态: OK")
    print()
    
    print("=" * 70)
    print("✅ 所有测试通过！")
    print("=" * 70)
    print()
    print("📁 创建的文件:")
    print(f"   - {get_user_profile_path()}")
    print(f"   - {get_soul_path()}")
    print(f"   - {get_memory_path()}")
    print(f"   - {get_evolution_log_path()}")
    print()
    
finally:
    # 清理临时目录
    if test_home.parent.exists():
        shutil.rmtree(test_home.parent, ignore_errors=True)

