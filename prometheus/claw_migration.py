from __future__ import annotations

import json
import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("prometheus.claw_migration")


class OpenClawMigration:
    """OpenClaw 到 Prometheus 的迁移工具。"""

    def __init__(self, source: str | None = None) -> None:
        self._source = Path(source) if source else Path.home() / ".openclaw"
        self._prometheus_home = Path.home() / ".prometheus"
        self._changes: list[dict[str, Any]] = []

    def scan(self) -> dict[str, Any]:
        """扫描 OpenClaw 目录并返回发现的内容。"""
        result = {
            "found": False,
            "config": False,
            "memories": False,
            "skills": False,
            "sessions": False,
            "api_keys": [],
        }

        if not self._source.exists():
            return result

        result["found"] = True

        if (self._source / "config.json").exists():
            result["config"] = True

        if (self._source / "memories").exists():
            memories_dir = self._source / "memories"
            result["memories"] = len(list(memories_dir.glob("*.md")))

        if (self._source / "skills").exists():
            skills_dir = self._source / "skills"
            result["skills"] = len(list(skills_dir.glob("*.yaml")))

        if (self._source / "sessions").exists():
            sessions_dir = self._source / "sessions"
            result["sessions"] = len(list(sessions_dir.glob("*.json")))

        api_keys_file = self._source / "api_keys.json"
        if api_keys_file.exists():
            try:
                with open(api_keys_file) as f:
                    keys = json.load(f)
                    result["api_keys"] = list(keys.keys())
            except Exception:
                pass

        return result

    def migrate(
        self,
        preset: str = "full",
        overwrite: bool = False,
        include_secrets: bool = False,
        backup: bool = True,
    ) -> bool:
        """执行迁移。

        Args:
            preset: 迁移预设 (user-data 或 full)
            overwrite: 是否覆盖现有文件
            include_secrets: 是否包含 API 密钥
            backup: 是否创建备份

        Returns:
            是否成功
        """
        scan_result = self.scan()

        if not scan_result["found"]:
            logger.error(f"OpenClaw 目录不存在: {self._source}")
            return False

        if backup:
            self._create_backup()

        if preset in ("user-data", "full"):
            self._migrate_config(overwrite)

        if preset == "full":
            self._migrate_memories(overwrite)
            self._migrate_skills(overwrite)

        if include_secrets:
            self._migrate_api_keys()

        self._log_changes()
        return True

    def _create_backup(self) -> None:
        """创建备份。"""
        backup_dir = self._prometheus_home / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"pre_claw_migration_{timestamp}.zip"

        try:
            with zipfile.ZipFile(backup_file, "w", zipfile.ZIP_DEFLATED) as zf:
                for item in self._source.rglob("*"):
                    if item.is_file():
                        zf.write(item, item.relative_to(self._source))

            logger.info(f"备份已创建: {backup_file}")
        except Exception as e:
            logger.warning(f"创建备份失败: {e}")

    def _migrate_config(self, overwrite: bool) -> None:
        """迁移配置文件。"""
        config_file = self._source / "config.json"
        if not config_file.exists():
            return

        dest = self._prometheus_home / "config.json"

        if dest.exists() and not overwrite:
            logger.info("配置文件已存在，跳过（使用 --overwrite 覆盖）")
            return

        try:
            with open(config_file) as f:
                config = json.load(f)

            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w") as f:
                json.dump(config, f, indent=2)

            self._changes.append(
                {
                    "action": "copied",
                    "source": str(config_file),
                    "dest": str(dest),
                }
            )
            logger.info("已迁移配置文件")
        except Exception as e:
            logger.error(f"迁移配置文件失败: {e}")

    def _migrate_memories(self, overwrite: bool) -> None:
        """迁移记忆文件。"""
        memories_dir = self._source / "memories"
        if not memories_dir.exists():
            return

        dest_dir = self._prometheus_home / "memories"
        dest_dir.mkdir(parents=True, exist_ok=True)

        for memory_file in memories_dir.glob("*.md"):
            dest = dest_dir / memory_file.name

            if dest.exists() and not overwrite:
                continue

            try:
                shutil.copy2(memory_file, dest)
                self._changes.append(
                    {
                        "action": "copied",
                        "source": str(memory_file),
                        "dest": str(dest),
                    }
                )
            except Exception as e:
                logger.error(f"迁移记忆文件失败 {memory_file}: {e}")

    def _migrate_skills(self, overwrite: bool) -> None:
        """迁移技能文件。"""
        skills_dir = self._source / "skills"
        if not skills_dir.exists():
            return

        dest_dir = self._prometheus_home / "skills"
        dest_dir.mkdir(parents=True, exist_ok=True)

        for skill_file in skills_dir.glob("*.yaml"):
            dest = dest_dir / skill_file.name

            if dest.exists() and not overwrite:
                continue

            try:
                shutil.copy2(skill_file, dest)
                self._changes.append(
                    {
                        "action": "copied",
                        "source": str(skill_file),
                        "dest": str(dest),
                    }
                )
            except Exception as e:
                logger.error(f"迁移技能文件失败 {skill_file}: {e}")

    def _migrate_api_keys(self) -> None:
        """迁移 API 密钥。"""
        api_keys_file = self._source / "api_keys.json"
        if not api_keys_file.exists():
            return

        try:
            with open(api_keys_file) as f:
                keys = json.load(f)

            dest = self._prometheus_home / ".api_keys_migrated.json"

            existing = {}
            if dest.exists():
                with open(dest) as f:
                    existing = json.load(f)

            existing.update(keys)

            with open(dest, "w") as f:
                json.dump(existing, f, indent=2)

            logger.info(f"已迁移 {len(keys)} 个 API 密钥")
        except Exception as e:
            logger.error(f"迁移 API 密钥失败: {e}")

    def _log_changes(self) -> None:
        """记录更改。"""
        if not self._changes:
            logger.info("没有文件被迁移")
            return

        logger.info(f"已迁移 {len(self._changes)} 个文件")

        changes_file = self._prometheus_home / "claw_migration_changes.json"
        with open(changes_file, "w") as f:
            json.dump(self._changes, f, indent=2)


def migrate_from_openclaw(
    source: str | None = None,
    dry_run: bool = False,
    preset: str = "full",
    overwrite: bool = False,
    include_secrets: bool = False,
    backup: bool = True,
    confirm: bool = False,
) -> bool:
    """从 OpenClaw 迁移到 Prometheus。"""
    migration = OpenClawMigration(source=source)

    scan_result = migration.scan()

    if not scan_result["found"]:
        print(f"❌ OpenClaw 目录不存在: {source or '~/.openclaw'}")
        return False

    print("  发现 OpenClaw 安装:")
    print(f"    配置: {'是' if scan_result['config'] else '否'}")
    print(f"    记忆: {scan_result['memories']} 个文件")
    print(f"    技能: {scan_result['skills']} 个文件")
    print(f"    会话: {scan_result['sessions']} 个文件")
    if scan_result["api_keys"]:
        print(f"    API密钥: {len(scan_result['api_keys'])} 个")
    print()

    if dry_run:
        print("🔍 预览模式 - 以下文件将被迁移:")
        for change in migration._changes:
            print(f"    {change['source']} -> {change['dest']}")
        return True

    if not confirm:
        response = input("继续迁移? [y/N] ").strip().lower()
        if response not in ("y", "yes"):
            print("已取消")
            return False

    return migration.migrate(
        preset=preset,
        overwrite=overwrite,
        include_secrets=include_secrets,
        backup=backup,
    )


def cleanup_openclaw(
    source: str | None = None,
    dry_run: bool = False,
    confirm: bool = False,
) -> None:
    """清理 OpenClaw 残留目录。"""
    openclaw_dirs = [
        Path(source) if source else Path.home() / ".openclaw",
        Path.home() / ".openclaw-old",
        Path.home() / ".openclaw-backup",
    ]

    to_cleanup = [d for d in openclaw_dirs if d.exists()]

    if not to_cleanup:
        print("  没有发现 OpenClaw 残留目录")
        return

    print(f"  发现 {len(to_cleanup)} 个残留目录:")
    for d in to_cleanup:
        print(f"    - {d}")
    print()

    if dry_run:
        print("🔍 预览模式 - 以下目录将被归档:")
        for d in to_cleanup:
            print(f"    - {d}")
        return

    if not confirm:
        response = input("归档这些目录? [y/N] ").strip().lower()
        if response not in ("y", "yes"):
            print("已取消")
            return

    archive_dir = Path.home() / ".openclaw-archived"
    archive_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for d in to_cleanup:
        try:
            archive_path = archive_dir / f"{d.name}_{timestamp}"
            shutil.move(str(d), str(archive_path))
            print(f"  已归档: {d} -> {archive_path}")
        except Exception as e:
            print(f"  归档失败 {d}: {e}")

    print(f"\n✅ 已归档 {len(to_cleanup)} 个目录到 {archive_dir}")
