#!/usr/bin/env python3
"""
测试 Prometheus 技能系统
"""
import sys
import os
sys.path.insert(0, '/Users/audrey/ptg-agent')

print("=" * 70)
print("🔥  测试 Prometheus 技能系统")
print("=" * 70)

# 测试 1: 技能加载器
print("\n[1] 测试技能加载器...")
try:
    from prometheus.tools.skill_loader import load_skills
    
    loader = load_skills()
    stats = loader.stats()
    
    print(f"  - 发现技能总数: {stats['total']}")
    print(f"  - 分类数: {stats['categories']}")
    print(f"  - 标签数: {stats['tags']}")
    
    # 列出一些技能
    print("\n  部分技能列表:")
    for i, skill in enumerate(list(loader._skills.values())[:10]):
        print(f"    {i+1}. {skill.meta.name} [{skill.category or 'uncategorized'}]")
    
    print("  ✅ 技能加载器测试通过")
except Exception as e:
    print(f"  ❌ 技能加载器测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 2: 技能建议提取
print("\n[2] 测试技能建议提取...")
try:
    from prometheus.memory_system import analyze_session_for_skill_suggestion
    
    test_cases = [
        (
            "运行了 doctor 检查，发现 config.yaml 问题，修复并验证",
            ["list_dir", "read_file", "doctor_check", "write_file"],
            True
        ),
        (
            "简单查询",
            [],
            False
        ),
        (
            "多次调用搜索工具",
            ["search", "search", "search", "search"],
            True
        ),
    ]
    
    for summary, tool_calls, should_suggest in test_cases:
        result = analyze_session_for_skill_suggestion(summary, tool_calls)
        
        if result["suggested"] == should_suggest:
            print(f"  ✅ 测试通过: 摘要长度={len(summary)}, 工具调用={len(tool_calls)}")
            if result["suggested"]:
                print(f"     建议名称: {result['suggested_name']}")
                print(f"     原因: {result['reason']}")
        else:
            print(f"  ❌ 测试失败: 期望建议={should_suggest}, 实际={result['suggested']}")
            print(f"     结果: {result}")
    
    print("  ✅ 技能建议提取测试完成")
except Exception as e:
    print(f"  ❌ 技能建议提取测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 3: 检查内置技能
print("\n[3] 检查内置技能...")
try:
    # 检查 Prometheus 自己的内置技能
    from prometheus.tools.skill_loader import find_skill
    
    # 检查我们创建的技能
    for skill_name in ["doctor_quick_fix", "evolution_proposal"]:
        skill = find_skill(skill_name)
        if skill:
            print(f"  ✅ 找到技能: {skill_name}")
            print(f"     描述: {skill.meta.description}")
            print(f"     路径: {skill.path}")
        else:
            print(f"  ⚠️  未找到: {skill_name} (可能是分类路径问题)")
            
    print("  ✅ 内置技能检查完成")
except Exception as e:
    print(f"  ❌ 内置技能检查失败: {e}")
    import traceback
    traceback.print_exc()

# 总结
print("\n" + "=" * 70)
print("测试完成！")
print("=" * 70)
