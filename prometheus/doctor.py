
"""
Prometheus Doctor - 守门员式诊断与修复引擎
核心理念：只确保网关能开机，剩余问题交给自然语言对话解决
"""
import os
import sys
import yaml
import shutil
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class IssueType:
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class DoctorCheck:
    def __init__(self, name, description, check_func, fix_func=None, is_gateway=True):
        self.name = name
        self.description = description
        self.check_func = check_func
        self.fix_func = fix_func
        self.is_gateway = is_gateway
        self.issue_type = None
        self.message = ""
        self.fixable = fix_func is not None

    def run(self):
        try:
            result = self.check_func()
            self.issue_type, self.message = result
            return self.issue_type in (IssueType.CRITICAL, IssueType.WARNING)
        except Exception as e:
            self.issue_type = IssueType.CRITICAL
            self.message = f"检查失败: {str(e)}"
            return True

    def fix(self):
        if not self.fix_func:
            return False, "无修复方法"
        try:
            return self.fix_func()
        except Exception as e:
            return False, f"修复失败: {str(e)}"


class PrometheusDoctor:
    GATEWAY_CHECKS = [
        "主配置文件",
        "SOUL.md",
    ]

    ALL_CHECKS = [
        "Python 版本",
        "核心依赖",
        "目录结构",
        "主配置文件",
        "SOUL.md",
        "记忆系统",
        "主数据库",
        "种子仓库",
    ]

    def __init__(self, full_mode=False):
        self.full_mode = full_mode
        self.checks = []
        self.backup_dir = None
        self._init_backup_dir()
        self._register_checks()

    def _init_backup_dir(self):
        home = Path.home() / ".prometheus"
        self.backup_dir = home / "doctor_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _register_checks(self):
        self.checks.append(DoctorCheck(
            name="Python 版本",
            description="检查 Python 版本",
            check_func=self._check_python_version,
            fix_func=None,
            is_gateway=False
        ))

        self.checks.append(DoctorCheck(
            name="核心依赖",
            description="检查核心依赖库",
            check_func=self._check_dependencies,
            fix_func=None,
            is_gateway=False
        ))

        self.checks.append(DoctorCheck(
            name="目录结构",
            description="检查目录结构",
            check_func=self._check_dir_structure,
            fix_func=self._fix_dir_structure,
            is_gateway=False
        ))

        self.checks.append(DoctorCheck(
            name="主配置文件",
            description="检查 config.yaml",
            check_func=self._check_config_file,
            fix_func=self._fix_config_file,
            is_gateway=True
        ))

        self.checks.append(DoctorCheck(
            name="SOUL.md",
            description="检查 SOUL.md",
            check_func=self._check_soul_file,
            fix_func=self._fix_soul_file,
            is_gateway=True
        ))

        self.checks.append(DoctorCheck(
            name="记忆系统",
            description="检查 USER.md 和 MEMORY.md",
            check_func=self._check_memory_files,
            fix_func=self._fix_memory_files,
            is_gateway=False
        ))

        self.checks.append(DoctorCheck(
            name="主数据库",
            description="检查 prometheus.db",
            check_func=self._check_main_db,
            fix_func=None,
            is_gateway=False
        ))

        self.checks.append(DoctorCheck(
            name="种子仓库",
            description="检查种子仓库",
            check_func=self._check_seed_vault,
            fix_func=None,
            is_gateway=False
        ))

    def _get_active_checks(self):
        if self.full_mode:
            return self.checks
        return [c for c in self.checks if c.is_gateway]

    def _backup_file(self, path):
        if not path.exists():
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{path.name}.{timestamp}.bak"
        shutil.copy2(path, backup_path)
        return backup_path

    def _check_python_version(self):
        version_str = ".".join(map(str, sys.version_info[:3]))
        major = sys.version_info[0]
        minor = sys.version_info[1]
        is_ok = major == 3 and minor >= 10
        if is_ok:
            return IssueType.INFO, f"Python {version_str}"
        else:
            return IssueType.WARNING, f"Python {version_str} (建议 3.10+)"

    def _check_dependencies(self):
        issues = []
        try:
            import numpy
        except ImportError:
            issues.append("numpy 未安装")
        try:
            import yaml
        except ImportError:
            issues.append("pyyaml 未安装")
        if issues:
            return IssueType.CRITICAL, ", ".join(issues)
        return IssueType.INFO, "所有依赖正常"

    def _check_dir_structure(self):
        home = Path.home() / ".prometheus"
        required_dirs = ["cron", "sessions", "logs", "memories", "checkpoints", "skills", "data"]
        missing = [d for d in required_dirs if not (home / d).exists()]
        if missing:
            return IssueType.WARNING, f"缺少目录: {', '.join(missing)}"
        return IssueType.INFO, "目录结构完整"

    def _fix_dir_structure(self):
        from prometheus.config import ensure_prometheus_home
        ensure_prometheus_home()
        return True, "目录结构已重建"

    def _check_config_file(self):
        from prometheus.config import get_config_path
        config_path = get_config_path()
        if not config_path.exists():
            return IssueType.CRITICAL, "配置文件不存在"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
            return IssueType.INFO, "配置文件有效"
        except Exception as e:
            return IssueType.CRITICAL, f"配置文件损坏: {str(e)[:60]}"

    def _fix_config_file(self):
        from prometheus.config import get_config_path, DEFAULT_CONFIG
        config_path = get_config_path()
        backup = self._backup_file(config_path)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
            msg = "配置文件已重置"
            if backup:
                msg += f" (旧版已备份)"
            return True, msg
        except Exception as e:
            return False, f"修复失败: {str(e)}"

    def _check_soul_file(self):
        from prometheus.config import get_soul_path
        soul_path = get_soul_path()
        if not soul_path.exists():
            return IssueType.WARNING, "SOUL.md 不存在"
        try:
            content = soul_path.read_text(encoding="utf-8")
            if not content.strip():
                return IssueType.WARNING, "SOUL.md 为空"
            return IssueType.INFO, "SOUL.md 正常"
        except Exception as e:
            return IssueType.WARNING, f"SOUL.md 读取失败"

    def _fix_soul_file(self):
        from prometheus.config import get_soul_path, DEFAULT_SOUL_MD
        soul_path = get_soul_path()
        backup = self._backup_file(soul_path)
        try:
            soul_path.write_text(DEFAULT_SOUL_MD, encoding="utf-8")
            msg = "SOUL.md 已重置"
            if backup:
                msg += f" (旧版已备份)"
            return True, msg
        except Exception as e:
            return False, f"修复失败: {str(e)}"

    def _check_memory_files(self):
        from prometheus.memory_system import get_user_profile_path, get_memory_path
        user_path = get_user_profile_path()
        memory_path = get_memory_path()
        issues = []
        if not user_path.exists():
            issues.append("USER.md 不存在")
        if not memory_path.exists():
            issues.append("MEMORY.md 不存在")
        if issues:
            return IssueType.WARNING, ", ".join(issues)
        return IssueType.INFO, "记忆系统正常"

    def _fix_memory_files(self):
        from prometheus.memory_system import MemorySystem
        backup1 = self._backup_file(Path.home() / ".prometheus" / "memories" / "USER.md")
        backup2 = self._backup_file(Path.home() / ".prometheus" / "memories" / "MEMORY.md")
        try:
            ms = MemorySystem()
            ms.create_user_profile(
                username="Audrey",
                communication_style="简洁专业",
                work_preferences="效率优先"
            )
            ms.create_soul(personality="友好、专业、简洁")
            ms.create_memory()
            backups = []
            if backup1:
                backups.append(backup1.name)
            if backup2:
                backups.append(backup2.name)
            msg = "记忆系统已重置"
            if backups:
                msg += f" ({len(backups)} 个旧文件已备份)"
            return True, msg
        except Exception as e:
            return False, f"修复失败: {str(e)}"

    def _check_main_db(self):
        home = Path.home() / ".prometheus"
        db_path = home / "data" / "prometheus.db"
        if db_path.exists():
            size_kb = os.path.getsize(db_path) / 1024
            return IssueType.INFO, f"主数据库存在 ({size_kb:.1f} KB)"
        else:
            return IssueType.WARNING, "主数据库不存在 (首次使用时自动创建)"

    def _check_seed_vault(self):
        vault = Path.home() / ".hermes" / "seed-vault"
        if not vault.exists():
            return IssueType.WARNING, "种子仓库不存在"
        ttg_files = [f for f in vault.iterdir() if f.suffix == ".ttg"]
        if not ttg_files:
            return IssueType.WARNING, "种子仓库为空"
        return IssueType.INFO, f"种子仓库有 {len(ttg_files)} 个种子"

    def diagnose(self):
        active_checks = self._get_active_checks()
        results = {
            "critical": [],
            "warning": [],
            "info": [],
            "all": []
        }

        print("=" * 70)
        if self.full_mode:
            print("🩺 Prometheus Doctor - 深度诊断")
        else:
            print("🩺 Prometheus Doctor")
        print("=" * 70)

        for check in active_checks:
            has_issue = check.run()
            result = {
                "name": check.name,
                "type": check.issue_type,
                "message": check.message,
                "fixable": check.fixable
            }
            results["all"].append(result)

            if check.issue_type == IssueType.CRITICAL:
                results["critical"].append(result)
            elif check.issue_type == IssueType.WARNING:
                results["warning"].append(result)
            else:
                results["info"].append(result)

            icon = "✅"
            if check.issue_type == IssueType.CRITICAL:
                icon = "❌"
            elif check.issue_type == IssueType.WARNING:
                icon = "⚠️"
            print(f"\n{icon} {check.name}")
            print(f"   {check.message}")

        print(f"\n{'━' * 70}")

        critical = len(results["critical"])
        warning = len(results["warning"])

        if self.full_mode:
            print(f"  📊 深度诊断: {len(results['all'])} 项")
            print(f"     ✅ 正常: {len(results['info'])}")
            print(f"     ⚠️ 警告: {warning}")
            print(f"     ❌ 严重: {critical}")
            if critical == 0:
                print(f"  🎉 无严重问题。")
            else:
                print(f"  💡 运行 'ptg doctor --fix' 修复严重问题。")
        else:
            if critical == 0:
                print(f"  ✅ 网关就绪。系统可正常启动。")
                print(f"  💡 其他问题请通过对话让 Agent 自行修复，或运行 'ptg doctor --full' 深度诊断。")
            else:
                gateway_checks = [r for r in results["critical"] if r["name"] in self.GATEWAY_CHECKS]
                if gateway_checks:
                    print(f"  ❌ 网关受阻。运行 'ptg doctor --fix' 修复。")
                else:
                    print(f"  ⚠️ 发现 {critical} 个严重问题。")
                    print(f"  💡 运行 'ptg doctor --fix' 修复，或运行 'ptg doctor --full' 查看详情。")

        print()
        return results

    def fix(self):
        active_checks = self._get_active_checks()
        results = {
            "fixed": [],
            "failed": [],
            "skipped": []
        }

        print("=" * 70)
        print("🔧 Prometheus Doctor - 修复模式")
        print("=" * 70)

        fixed_something = False
        for check in active_checks:
            check.run()
            if check.issue_type in (IssueType.CRITICAL, IssueType.WARNING):
                if check.fixable:
                    print(f"\n🔧 正在修复: {check.name}")
                    success, msg = check.fix()
                    if success:
                        print(f"   ✅ {msg}")
                        results["fixed"].append({"name": check.name, "message": msg})
                        fixed_something = True
                    else:
                        print(f"   ❌ {msg}")
                        results["failed"].append({"name": check.name, "message": msg})
                else:
                    results["skipped"].append(check.name)
            else:
                results["skipped"].append(check.name)

        print(f"\n{'━' * 70}")
        print(f"  📊 修复结果:")
        print(f"     ✅ 已修复: {len(results['fixed'])}")
        print(f"     ❌ 失败: {len(results['failed'])}")
        print(f"     ⏭️ 跳过: {len(results['skipped'])}")

        if fixed_something:
            print(f"\n  ✅ 修复完成！")
            print(f"  💡 运行 'ptg doctor' 确认网关状态。")
        print()

        return results

    def list_backups(self):
        backups = sorted(self.backup_dir.glob("*.bak"), reverse=True)

        print("=" * 70)
        print("📦 Prometheus Doctor - 备份列表")
        print("=" * 70)
        print()

        if not backups:
            print("  暂无备份")
            print()
            return

        for i, backup in enumerate(backups, 1):
            size = backup.stat().st_size
            print(f"  {i:2d}. {backup.name} ({size} 字节)")

        print()

    def restore_backup(self, backup_name, target_name=None):
        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            print(f"  ❌ 备份不存在: {backup_name}")
            return False

        if not target_name:
            if ".yaml.bak" in backup_name:
                target_name = "config.yaml"
            elif ".md.bak" in backup_name:
                if "SOUL" in backup_name:
                    target_name = "SOUL.md"
                elif "USER" in backup_name:
                    target_name = "memories/USER.md"
                elif "MEMORY" in backup_name:
                    target_name = "memories/MEMORY.md"

        if not target_name:
            print(f"  ❌ 无法确定目标文件，请指定")
            return False

        home = Path.home() / ".prometheus"
        target_path = home / target_name
        current_backup = self._backup_file(target_path)

        try:
            shutil.copy2(backup_path, target_path)
            msg = f"已从 {backup_name} 恢复到 {target_name}"
            if current_backup:
                msg += f" (当前文件已备份为 {current_backup.name})"
            print(f"  ✅ {msg}")
            return True
        except Exception as e:
            print(f"  ❌ 恢复失败: {str(e)}")
            return False


def run_doctor_diagnose():
    doctor = PrometheusDoctor(full_mode=False)
    doctor.diagnose()


def run_doctor_full():
    doctor = PrometheusDoctor(full_mode=True)
    doctor.diagnose()


def run_doctor_fix():
    doctor = PrometheusDoctor(full_mode=False)
    doctor.fix()


def run_doctor_backups():
    doctor = PrometheusDoctor()
    doctor.list_backups()


def run_doctor_restore(backup_name):
    doctor = PrometheusDoctor()
    doctor.restore_backup(backup_name)


def emergency_repair():
    print("=" * 70)
    print("🚨 Prometheus Doctor - 紧急修复模式")
    print("=" * 70)
    print()

    doctor = PrometheusDoctor(full_mode=False)

    print("📦 备份现有配置...")
    from prometheus.config import get_config_path, get_soul_path
    for path in [get_config_path(), get_soul_path()]:
        if path.exists():
            backup = doctor._backup_file(path)
            if backup:
                print(f"   ✅ 已备份: {path.name}")

    print("\n🔧 重置主配置...")
    success, msg = doctor._fix_config_file()
    print(f"   {msg}")

    print("\n🔧 重置 SOUL.md...")
    success, msg = doctor._fix_soul_file()
    print(f"   {msg}")

    print("\n" + "=" * 70)
    print("✅ 紧急修复完成！")
    print("   所有旧配置已备份到 ~/.prometheus/doctor_backups/")
    print("   运行 'ptg doctor' 确认网关状态。")
    print("=" * 70)
