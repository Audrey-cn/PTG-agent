
#!/usr/bin/env python3
"""Prometheus Doctor CLI 工具（临时使用）。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prometheus.doctor import (
    PrometheusDoctor,
    run_doctor_diagnose,
    run_doctor_fix,
    run_doctor_backups,
    run_doctor_restore,
    emergency_repair
)


def show_help():
    print("\n🔥 Prometheus Doctor\n")
    print("用法:")
    print("  python3 prometheus/doctor_cli.py              # 系统诊断")
    print("  python3 prometheus/doctor_cli.py --fix        # 交互式修复")
    print("  python3 prometheus/doctor_cli.py --backups    # 备份列表")
    print("  python3 prometheus/doctor_cli.py --restore NAME  # 恢复备份")
    print("  python3 prometheus/doctor_cli.py --emergency  # 紧急修复")
    print("\n")


if __name__ == "__main__":
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
            run_doctor_restore(sys.argv[2])
        elif cmd == "--emergency":
            emergency_repair()
        else:
            show_help()
