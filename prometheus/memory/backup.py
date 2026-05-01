#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import logging
import os
import shutil
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BackupInfo:
    name: str
    path: str
    backup_type: str  # "daily", "hourly", "manual"
    created_at: str
    size_bytes: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "type": self.backup_type,
            "created_at": self.created_at,
            "size_kb": round(self.size_bytes / 1024, 1),
        }


class BackupManager:
    """备份管理器"""

    DEFAULT_CONFIG = {
        "enabled": True,
        "daily_retention": 30,
        "hourly_retention": 24,
        "backup_dir": None,
    }

    def __init__(self, data_dir: str, config: dict = None):
        self.data_dir = data_dir
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        self.backup_dir = self.config.get("backup_dir") or os.path.join(
            os.path.dirname(data_dir), "backup"
        )

        self.daily_dir = os.path.join(self.backup_dir, "daily")
        self.hourly_dir = os.path.join(self.backup_dir, "hourly")
        self.manual_dir = os.path.join(self.backup_dir, "manual")

        os.makedirs(self.daily_dir, exist_ok=True)
        os.makedirs(self.hourly_dir, exist_ok=True)
        os.makedirs(self.manual_dir, exist_ok=True)

    def backup_daily(self, name: str = None) -> BackupInfo:
        """创建每日备份"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
        backup_name = name or timestamp
        backup_path = os.path.join(self.daily_dir, backup_name)

        if os.path.exists(backup_path):
            logger.warning(f"Daily backup already exists: {backup_name}")
            return self._get_backup_info(backup_path, "daily")

        self._create_backup(backup_path)
        self._cleanup_old_backups("daily", self.config["daily_retention"])

        logger.info(f"Created daily backup: {backup_name}")
        return self._get_backup_info(backup_path, "daily")

    def backup_hourly(self, name: str = None) -> BackupInfo:
        """创建每小时备份"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H")
        backup_name = name or timestamp
        backup_path = os.path.join(self.hourly_dir, backup_name)

        if os.path.exists(backup_path):
            logger.warning(f"Hourly backup already exists: {backup_name}")
            return self._get_backup_info(backup_path, "hourly")

        self._create_backup(backup_path)
        self._cleanup_old_backups("hourly", self.config["hourly_retention"])

        logger.info(f"Created hourly backup: {backup_name}")
        return self._get_backup_info(backup_path, "hourly")

    def backup_manual(self, name: str) -> BackupInfo:
        """创建手动备份（永久保留）"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{name}_{timestamp}"
        backup_path = os.path.join(self.manual_dir, backup_name)

        self._create_backup(backup_path)

        logger.info(f"Created manual backup: {backup_name}")
        return self._get_backup_info(backup_path, "manual")

    def _create_backup(self, backup_path: str):
        """创建备份"""
        os.makedirs(backup_path, exist_ok=True)

        if os.path.exists(self.data_dir):
            shutil.copytree(self.data_dir, os.path.join(backup_path, "data"), dirs_exist_ok=True)

        manifest = {
            "created_at": datetime.datetime.now().isoformat(),
            "source_dir": self.data_dir,
            "version": "1.0",
        }

        manifest_path = os.path.join(backup_path, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            import json

            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def _cleanup_old_backups(self, backup_type: str, retention: int):
        """清理旧备份"""
        if backup_type == "daily":
            backup_dir = self.daily_dir
        elif backup_type == "hourly":
            backup_dir = self.hourly_dir
        else:
            return

        backups = []
        for name in os.listdir(backup_dir):
            path = os.path.join(backup_dir, name)
            if os.path.isdir(path):
                stat = os.stat(path)
                backups.append((name, path, stat.st_mtime))

        backups.sort(key=lambda x: x[2], reverse=True)

        for name, path, _ in backups[retention:]:
            shutil.rmtree(path)
            logger.info(f"Cleaned up old backup: {name}")

    def restore(self, backup_name: str, backup_type: str = None) -> dict[str, any]:
        """从备份恢复"""
        backup_path = self._find_backup(backup_name, backup_type)

        if not backup_path:
            return {"success": False, "error": f"Backup not found: {backup_name}"}

        data_backup = os.path.join(backup_path, "data")
        if not os.path.exists(data_backup):
            return {"success": False, "error": "Backup data not found"}

        if os.path.exists(self.data_dir):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore_backup = os.path.join(self.manual_dir, f"pre_restore_{timestamp}")
            shutil.copytree(self.data_dir, pre_restore_backup)
            logger.info(f"Created pre-restore backup: {pre_restore_backup}")

            shutil.rmtree(self.data_dir)

        shutil.copytree(data_backup, self.data_dir)

        logger.info(f"Restored from backup: {backup_name}")
        return {
            "success": True,
            "restored_from": backup_name,
            "backup_type": backup_type or "unknown",
        }

    def _find_backup(self, name: str, backup_type: str = None) -> str | None:
        """查找备份"""
        if backup_type:
            dirs = {
                "daily": self.daily_dir,
                "hourly": self.hourly_dir,
                "manual": self.manual_dir,
            }
            if backup_type in dirs:
                path = os.path.join(dirs[backup_type], name)
                if os.path.exists(path):
                    return path
        else:
            for backup_dir in [self.daily_dir, self.hourly_dir, self.manual_dir]:
                path = os.path.join(backup_dir, name)
                if os.path.exists(path):
                    return path

        return None

    def list_backups(self, backup_type: str = None) -> list[BackupInfo]:
        """列出所有备份"""
        backups = []

        types_to_check = []
        if backup_type:
            types_to_check = [(backup_type, getattr(self, f"{backup_type}_dir"))]
        else:
            types_to_check = [
                ("daily", self.daily_dir),
                ("hourly", self.hourly_dir),
                ("manual", self.manual_dir),
            ]

        for btype, bdir in types_to_check:
            if not os.path.exists(bdir):
                continue

            for name in os.listdir(bdir):
                path = os.path.join(bdir, name)
                if os.path.isdir(path):
                    backups.append(self._get_backup_info(path, btype))

        backups.sort(key=lambda x: x.created_at, reverse=True)
        return backups

    def _get_backup_info(self, backup_path: str, backup_type: str) -> BackupInfo:
        """获取备份信息"""
        name = os.path.basename(backup_path)

        manifest_path = os.path.join(backup_path, "manifest.json")
        created_at = ""
        if os.path.exists(manifest_path):
            try:
                import json

                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
                    created_at = manifest.get("created_at", "")
            except Exception:
                pass

        if not created_at:
            stat = os.stat(backup_path)
            created_at = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()

        size_bytes = self._get_dir_size(backup_path)

        return BackupInfo(
            name=name,
            path=backup_path,
            backup_type=backup_type,
            created_at=created_at,
            size_bytes=size_bytes,
        )

    def _get_dir_size(self, path: str) -> int:
        """计算目录大小"""
        total = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp)
        return total

    def get_status(self) -> dict:
        """获取备份状态"""
        daily_backups = self.list_backups("daily")
        hourly_backups = self.list_backups("hourly")
        manual_backups = self.list_backups("manual")

        return {
            "enabled": self.config["enabled"],
            "daily": {
                "count": len(daily_backups),
                "latest": daily_backups[0].to_dict() if daily_backups else None,
                "retention_days": self.config["daily_retention"],
            },
            "hourly": {
                "count": len(hourly_backups),
                "latest": hourly_backups[0].to_dict() if hourly_backups else None,
                "retention_hours": self.config["hourly_retention"],
            },
            "manual": {
                "count": len(manual_backups),
            },
        }
