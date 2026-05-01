#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import glob
import logging
import os

from .storage import HybridStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SyncManager:
    """MD 文件与 SQLite 同步管理器"""

    def __init__(self, storage: HybridStorage = None):
        self.storage = storage or HybridStorage()

    def sync_from_md(self, force: bool = False) -> dict[str, int]:
        """
        从 MD 文件同步到 SQLite

        Args:
            force: 是否强制覆盖 SQLite 中的记录

        Returns:
            {"synced": N, "skipped": M, "errors": E}
        """
        result = {"synced": 0, "skipped": 0, "errors": 0}

        md_files = glob.glob(os.path.join(self.storage.data_dir, "**/*.md"), recursive=True)

        for md_file in md_files:
            try:
                record = self.storage._parse_md(md_file)
                if not record or not record.memory_id:
                    result["skipped"] += 1
                    continue

                existing = self.storage._load_from_sqlite(record.memory_id)

                if existing and not force:
                    if existing.content_hash == record.content_hash:
                        result["skipped"] += 1
                        continue

                    if existing.updated_at > record.updated_at:
                        result["skipped"] += 1
                        continue

                self.storage._save_to_sqlite(record)
                result["synced"] += 1
                logger.debug(f"Synced: {record.memory_id}")

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error syncing {md_file}: {e}")

        logger.info(f"Sync from MD: {result}")
        return result

    def sync_to_md(self, force: bool = False) -> dict[str, int]:
        """
        从 SQLite 同步到 MD 文件

        Args:
            force: 是否强制覆盖 MD 文件

        Returns:
            {"synced": N, "skipped": M, "errors": E}
        """
        result = {"synced": 0, "skipped": 0, "errors": 0}

        for layer in self.storage.LAYERS:
            records = self.storage.list_by_layer(layer, limit=10000)

            for record in records:
                try:
                    md_path = self.storage._md_path(record.memory_id, layer)

                    if os.path.exists(md_path) and not force:
                        existing = self.storage._parse_md(md_path)
                        if existing and existing.content_hash == record.content_hash:
                            result["skipped"] += 1
                            continue

                        if existing and existing.updated_at > record.updated_at:
                            result["skipped"] += 1
                            continue

                    self.storage._save_to_md(record)
                    result["synced"] += 1
                    logger.debug(f"Synced to MD: {record.memory_id}")

                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Error syncing {record.memory_id}: {e}")

        logger.info(f"Sync to MD: {result}")
        return result

    def reconcile(self) -> dict[str, list[str]]:
        """
        检测并报告 MD 和 SQLite 之间的差异

        Returns:
            {"md_only": [...], "sqlite_only": [...], "conflicts": [...]}
        """
        result = {
            "md_only": [],
            "sqlite_only": [],
            "conflicts": [],
        }

        md_ids = set()
        md_files = glob.glob(os.path.join(self.storage.data_dir, "**/*.md"), recursive=True)
        for md_file in md_files:
            record = self.storage._parse_md(md_file)
            if record and record.memory_id:
                md_ids.add(record.memory_id)

        with self.storage._conn() as conn:
            rows = conn.execute("SELECT memory_id FROM memories").fetchall()
            sqlite_ids = {row[0] for row in rows}

        result["md_only"] = list(md_ids - sqlite_ids)
        result["sqlite_only"] = list(sqlite_ids - md_ids)

        common_ids = md_ids & sqlite_ids
        for mid in common_ids:
            md_record = self.storage._load_from_md(mid)
            sqlite_record = self.storage._load_from_sqlite(mid)

            if md_record and sqlite_record:
                if md_record.content_hash != sqlite_record.content_hash:
                    result["conflicts"].append(mid)

        return result

    def full_sync(self) -> dict[str, int]:
        """
        完整双向同步：
        1. 检测差异
        2. 以更新时间为准解决冲突
        3. 确保两边一致
        """
        diff = self.reconcile()

        for mid in diff["md_only"]:
            record = self.storage._load_from_md(mid)
            if record:
                self.storage._save_to_sqlite(record)
                logger.info(f"Synced MD-only record to SQLite: {mid}")

        for mid in diff["sqlite_only"]:
            record = self.storage._load_from_sqlite(mid)
            if record:
                self.storage._save_to_md(record)
                logger.info(f"Synced SQLite-only record to MD: {mid}")

        for mid in diff["conflicts"]:
            md_record = self.storage._load_from_md(mid)
            sqlite_record = self.storage._load_from_sqlite(mid)

            if md_record and sqlite_record:
                if md_record.updated_at > sqlite_record.updated_at:
                    self.storage._save_to_sqlite(md_record)
                    logger.info(f"Resolved conflict (MD newer): {mid}")
                else:
                    self.storage._save_to_md(sqlite_record)
                    logger.info(f"Resolved conflict (SQLite newer): {mid}")

        return {
            "md_only_synced": len(diff["md_only"]),
            "sqlite_only_synced": len(diff["sqlite_only"]),
            "conflicts_resolved": len(diff["conflicts"]),
        }

    def verify_integrity(self) -> dict[str, any]:
        """
        验证数据完整性

        Returns:
            {"valid": bool, "issues": [...]}
        """
        issues = []

        diff = self.reconcile()
        if diff["md_only"] or diff["sqlite_only"] or diff["conflicts"]:
            issues.append(
                f"Sync differences detected: {len(diff['md_only'])} MD-only, {len(diff['sqlite_only'])} SQLite-only, {len(diff['conflicts'])} conflicts"
            )

        for layer in self.storage.LAYERS:
            records = self.storage.list_by_layer(layer)
            for record in records:
                expected_hash = self.storage._content_hash(record.content)
                if record.content_hash and record.content_hash != expected_hash:
                    issues.append(f"Content hash mismatch: {record.memory_id}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "stats": self.storage.stats(),
        }
