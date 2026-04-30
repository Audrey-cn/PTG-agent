
#!/usr/bin/env python3
"""测试 Prometheus Doctor 和记忆系统（直接导入）。"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("🔥 Prometheus Doctor 和记忆系统测试")
print("=" * 70)

print("\n1. 测试配置模块...")
try:
    from prometheus.config import get_config_path, ensure_prometheus_home
    print(f"   配置路径: {get_config_path()}")
    ensure_prometheus_home()
    print("   ✅ 配置模块正常")
except Exception as e:
    print(f"   ❌ 配置模块错误: {e}")

print("\n2. 测试记忆系统模块...")
try:
    from prometheus.memory_system import MemorySystem
    ms = MemorySystem()
    print(f"   ✅ 记忆系统模块正常")
except Exception as e:
    print(f"   ❌ 记忆系统模块错误: {e}")

print("\n3. 测试 Doctor 模块...")
try:
    from prometheus.doctor import PrometheusDoctor
    doctor = PrometheusDoctor()
    print(f"   ✅ Doctor 模块导入正常")
    
    # 测试诊断（不输出详细信息）
    results = doctor.diagnose(verbose=False)
    print(f"   诊断结果: {len(results['all'])} 项检查")
    print(f"   - 正常: {len(results['info'])}")
    print(f"   - 警告: {len(results['warning'])}")
    print(f"   - 严重: {len(results['critical'])}")
    
except Exception as e:
    print(f"   ❌ Doctor 模块错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("📝 使用提示")
print("=" * 70)
print("\n你可以通过以下方式使用功能:")
print("  - doctor: 系统诊断与修复")
print("  - memory_system: 用户/记忆管理")
print("  - config: 配置管理")
print("\n")
