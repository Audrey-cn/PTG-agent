
#!/usr/bin/env python3
"""测试新的 Doctor 系统。"""
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🔥 测试 Prometheus Doctor 系统")
print("=" * 70)

# 测试诊断功能
print("\n📋 1. 运行诊断...")
try:
    from prometheus.doctor import PrometheusDoctor
    doctor = PrometheusDoctor()
    results = doctor.diagnose(verbose=True)
    print(f"✅ 诊断完成！")
except Exception as e:
    print(f"❌ 诊断失败: {e}")
    import traceback
    traceback.print_exc()

# 测试备份功能
print("\n📦 2. 检查备份目录...")
try:
    backup_dir = Path.home() / ".prometheus" / "doctor_backups"
    if backup_dir.exists():
        backups = list(backup_dir.glob("*.bak"))
        print(f"✅ 备份目录: {backup_dir}")
        print(f"   现有备份: {len(backups)} 个")
    else:
        print(f"⚠️  备份目录不存在（首次使用时会创建）")
except Exception as e:
    print(f"❌ 备份检查失败: {e}")

print("\n" + "=" * 70)
print("📝 Doctor 命令使用说明")
print("=" * 70)
print("\n  ptg doctor                  # 运行诊断")
print("  ptg doctor --fix            # 交互式修复")
print("  ptg doctor --backups        # 列出备份")
print("  ptg doctor --restore NAME   # 从备份恢复")
print("  ptg doctor --emergency      # 紧急修复（非交互式）")
print("\n✅ 新 Doctor 系统已就绪！")
