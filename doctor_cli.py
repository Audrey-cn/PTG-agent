
#!/usr/bin/env python3
"""Prometheus Doctor CLI 工具。"""
import sys
import os

# 添加项目根目录
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

# 直接导入
from doctor = __import__('doctor')

def main():
    argc = len(sys.argv)
    if argc == 1:
        doctor.run_doctor_diagnose()
    else:
        cmd = sys.argv[1]
        if cmd == "--fix":
            doctor.run_doctor_fix()
        elif cmd == "--backups":
            doctor.run_doctor_backups()
        elif cmd == "--restore" and argc == 3:
            doctor.run_doctor_restore(sys.argv[2])
        elif cmd == "--emergency":
            doctor.emergency_repair()
        else:
            print("\n🔥 Prometheus Doctor\n")
            print("用法:")
            print("  python3 prometheus/doctor_cli.py              # 系统诊断")
            print("  python3 prometheus/doctor_cli.py --fix        # 交互式修复")
            print("  python3 prometheus/doctor_cli.py --backups    # 备份列表")
            print("  python3 prometheus/doctor_cli.py --restore NAME  # 恢复备份")
            print("  python3 prometheus/doctor_cli.py --emergency  # 紧急修复")
            print("\n")

if __name__ == "__main__":
    # 更简单的方式，用 sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from doctor import (
        run_doctor_diagnose,
        run_doctor_fix,
        run_doctor_backups,
        emergency_repair
    )
    argc = len(sys.argv)
    if argc == 1:
        run_doctor_diagnose()
    else:
        cmd = sys.argv[1]
        if cmd == "--fix":
            run_doctor_fix()
        elif cmd == "--backups":
            run_doctor_backups()
        elif cmd == "--restore" and argc == 3:
            from doctor import run_doctor_restore
            run_doctor_restore(sys.argv[2])
        elif cmd == "--emergency":
            emergency_repair()
        else:
            print("\n🔥 Prometheus Doctor\n")
            print("用法:")
            print("  python3 prometheus/doctor_cli.py              # 系统诊断")
            print("  python3 prometheus/doctor_cli.py --fix        # 交互式修复")
            print("  python3 prometheus/doctor_cli.py --backups    # 备份列表")
            print("  python3 prometheus/doctor_cli.py --restore NAME  # 恢复备份")
            print("  python3 prometheus/doctor_cli.py --emergency  # 紧急修复")
            print("\n")
