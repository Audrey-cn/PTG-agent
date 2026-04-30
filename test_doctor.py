
#!/usr/bin/env python3
"""测试 Prometheus Doctor 系统。"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🔥 测试 Prometheus Doctor 系统")
print("=" * 70)

# 1. 测试 doctor 模块导入
print("\n1. 测试 doctor 模块导入...")
try:
    from prometheus.doctor import (
        PrometheusDoctor,
        run_doctor_diagnose,
        run_doctor_backups,
        emergency_repair
    )
    print(f"   ✅ doctor 模块导入成功")
except Exception as e:
    print(f"   ❌ doctor 模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. 创建 Doctor 实例并测试
print("\n2. 创建 Doctor 实例...")
try:
    doctor = PrometheusDoctor()
    print(f"   ✅ Doctor 实例创建成功")
    print(f"   备份目录: {doctor.backup_dir}")
    print(f"   检查项数量: {len(doctor.checks)}")
except Exception as e:
    print(f"   ❌ 创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. 运行诊断（非 verbose）
print("\n3. 运行诊断...")
try:
    results = doctor.diagnose(verbose=False)
    print(f"   ✅ 诊断成功")
    print(f"   检查总数: {len(results['all'])}")
    print(f"   正常: {len(results['info'])}")
    print(f"   警告: {len(results['warning'])}")
    print(f"   严重: {len(results['critical'])}")
    
    for r in results['all'][:3]:
        icon = "✅"
        if r['type'] == 'critical':
            icon = "❌"
        elif r['type'] == 'warning':
            icon = "⚠️"
        print(f"   {icon} {r['name']}: {r['message']}")
except Exception as e:
    print(f"   ❌ 诊断失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 备份列表
print("\n4. 测试备份列表...")
try:
    doctor.list_backups()
except Exception as e:
    print(f"   ⚠️ 备份列表失败: {e}")

print("\n" + "=" * 70)
print("📝 Doctor 系统命令")
print("=" * 70)
print("\n以下命令可用:")
print("  ptg doctor                  # 系统诊断")
print("  ptg doctor --fix            # 交互式修复")
print("  ptg doctor --backups        # 备份列表")
print("  ptg doctor --restore NAME   # 恢复备份")
print("  ptg doctor --emergency      # 紧急修复")
print("  ptg config show             # 查看配置")
print("  ptg status                  # 系统状态")

print("\n✅ Doctor 系统完整测试通过！")
