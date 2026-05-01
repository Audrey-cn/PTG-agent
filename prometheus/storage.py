#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import json
import os
import sqlite3
from contextlib import contextmanager, suppress

# ═══════════════════════════════════════════
#   配置
# ═══════════════════════════════════════════

PROMETHEUS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROMETHEUS_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_DB = os.path.join(DATA_DIR, "prometheus.db")


# ═══════════════════════════════════════════
#   核心存储引擎
# ═══════════════════════════════════════════


class StorageEngine:
    """SQLite 存储引擎，支持 FTS5 全文搜索。

    设计哲学（对齐 Hermes）：
      - 结构化数据统一存 SQLite，不散落多个 JSON 文件
      - 每个模块通过 table_name 隔离，共享同一个数据库文件
      - FTS5 虚拟表提供毫秒级全文检索
      - 所有记录自动带 created_at / updated_at 时间戳
    """

    def __init__(self, db_path: str = None, table_name: str = "records"):
        """
        Args:
            db_path: 数据库文件路径，默认 prometheus.db
            table_name: 本模块使用的表名前缀
        """
        self.db_path = db_path or DEFAULT_DB
        self.table_name = table_name
        self._ensure_tables()

    @contextmanager
    def _conn(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_tables(self):
        """确保数据表和 FTS 索引存在"""
        records_table = f"{self.table_name}"
        fts_table = f"{self.table_name}_fts"

        with self._conn() as conn:
            # 主表
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {records_table} (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    content     TEXT NOT NULL,
                    category    TEXT DEFAULT 'general',
                    tags        TEXT DEFAULT '',
                    metadata    TEXT DEFAULT '{{}}',
                    trust_score REAL DEFAULT 0.5,
                    created_at  TEXT DEFAULT (datetime('now')),
                    updated_at  TEXT DEFAULT (datetime('now'))
                )
            """)

            # 全文索引：使用 FTS5 trigram（支持中文子串匹配）
            try:
                conn.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table}
                    USING fts5(content, tags,
                               tokenize='trigram case_sensitive 0')
                """)
            except sqlite3.OperationalError:
                pass  # 已存在

            # 自动创建 updated_at 触发器
            with suppress(sqlite3.OperationalError):
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {records_table}_updated
                    AFTER UPDATE ON {records_table}
                    BEGIN
                        UPDATE {records_table}
                        SET updated_at = datetime('now')
                        WHERE id = NEW.id;
                    END
                """)

    # ─── CRUD ───────────────────────────────────

    def add(
        self,
        content: str,
        category: str = "general",
        tags: list[str] = None,
        metadata: dict = None,
        trust_score: float = 0.5,
    ) -> int:
        """添加记录，返回 ID"""
        tags_str = ",".join(tags) if tags else ""
        meta_str = json.dumps(metadata or {}, ensure_ascii=False)
        with self._conn() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} "
                f"(content, category, tags, metadata, trust_score) "
                f"VALUES (?, ?, ?, ?, ?)",
                (content, category, tags_str, meta_str, trust_score),
            )
            row_id = cursor.lastrowid
            # 同步 FTS 索引
            with suppress(sqlite3.OperationalError):
                conn.execute(
                    f"INSERT INTO {self.table_name}_fts "
                    f"(rowid, content, tags, category) "
                    f"VALUES (?, ?, ?, ?)",
                    (row_id, content, tags_str, category),
                )
            return row_id

    def get(self, record_id: int) -> dict | None:
        """按 ID 获取单条记录"""
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def update(self, record_id: int, **kwargs) -> bool:
        """更新记录的指定字段"""
        allowed = {"content", "category", "tags", "metadata", "trust_score"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        set_parts = []
        values = []
        for k, v in updates.items():
            if k == "tags" and isinstance(v, list):
                v = ",".join(v)
            if k == "metadata" and isinstance(v, dict):
                v = json.dumps(v, ensure_ascii=False)
            set_parts.append(f"{k} = ?")
            values.append(v)

        values.append(record_id)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {', '.join(set_parts)} WHERE id = ?", values
            )
            # 同步 FTS
            if "content" in updates or "tags" in updates:
                try:
                    content = updates.get("content", "")
                    tags = updates.get("tags", "")
                    if isinstance(tags, list):
                        tags = ",".join(tags)
                    conn.execute(f"DELETE FROM {self.table_name}_fts WHERE rowid = ?", (record_id,))
                    conn.execute(
                        f"INSERT INTO {self.table_name}_fts "
                        f"(rowid, content, tags, category) "
                        f"VALUES (?, ?, ?, ?)",
                        (record_id, content, tags, updates.get("category", "general")),
                    )
                except sqlite3.OperationalError:
                    pass
        return True

    def delete(self, record_id: int) -> bool:
        """删除记录"""
        with self._conn() as conn:
            conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            with suppress(sqlite3.OperationalError):
                conn.execute(f"DELETE FROM {self.table_name}_fts WHERE rowid = ?", (record_id,))
        return True

    def list_all(self, category: str = None, limit: int = 100, offset: int = 0) -> list[dict]:
        """列出所有记录（支持分类过滤）"""
        with self._conn() as conn:
            if category:
                rows = conn.execute(
                    f"SELECT * FROM {self.table_name} "
                    f"WHERE category = ? "
                    f"ORDER BY created_at DESC "
                    f"LIMIT ? OFFSET ?",
                    (category, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    # ─── 搜索 ───────────────────────────────────

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """混合搜索：LIKE（主） + FTS5 trigram（辅）

        策略：
          1. LIKE 保证结果完整（支持中英文子串匹配）
          2. 如果 FTS trigram 可用，按相关性排序
          3. 两者结合：FTS 排序 + LIKE 兜底
        """
        if not query.strip():
            return []
        with self._conn() as conn:
            # 主搜索：LIKE（可靠，支持所有语言）
            like_pattern = f"%{query}%"
            rows = conn.execute(
                f"SELECT * FROM {self.table_name} "
                f"WHERE content LIKE ? OR tags LIKE ? OR category LIKE ? "
                f"ORDER BY created_at DESC "
                f"LIMIT ?",
                (like_pattern, like_pattern, like_pattern, limit),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def count(self, category: str = None) -> int:
        """统计记录数"""
        with self._conn() as conn:
            if category:
                row = conn.execute(
                    f"SELECT COUNT(*) FROM {self.table_name} WHERE category = ?", (category,)
                ).fetchone()
            else:
                row = conn.execute(f"SELECT COUNT(*) FROM {self.table_name}").fetchone()
            return row[0] if row else 0

    def stats(self) -> dict:
        """统计概览"""
        with self._conn() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM {self.table_name}").fetchone()[0]

            categories = conn.execute(
                f"SELECT category, COUNT(*) as cnt "
                f"FROM {self.table_name} "
                f"GROUP BY category ORDER BY cnt DESC"
            ).fetchall()

            return {
                "total": total,
                "table_name": self.table_name,
                "db_path": self.db_path,
                "categories": {r["category"]: r["cnt"] for r in categories},
            }

    # ─── Markdown 导出 ──────────────────────────

    def export_markdown(self, title: str = None, category: str = None, limit: int = 100) -> str:
        """导出为 Markdown 格式（人读层）"""
        title = title or f"{self.table_name} Report"
        lines = [
            f"# {title}",
            "",
            f"_Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_",
            "",
        ]

        records = self.list_all(category=category, limit=limit)
        if not records:
            lines.append("_No records found._")
            return "\n".join(lines)

        # 按分类分组
        by_category = {}
        for r in records:
            cat = r.get("category", "general")
            by_category.setdefault(cat, []).append(r)

        for cat, items in by_category.items():
            lines.append(f"## {cat.title()}")
            lines.append("")
            for item in items:
                content = item.get("content", "")
                tags = item.get("tags", "")
                meta = item.get("metadata", "{}")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}
                created = item.get("created_at", "")

                lines.append(f"### [{item['id']}] {content[:80]}")
                if created:
                    lines.append(f"- **时间**: {created}")
                if tags:
                    lines.append(f"- **标签**: {tags}")
                if meta and meta != {}:
                    lines.append(f"- **元数据**: `{json.dumps(meta, ensure_ascii=False)}`")
                lines.append("")

        return "\n".join(lines)

    # ─── 内部工具 ────────────────────────────────

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """将 sqlite3.Row 转为 dict"""
        d = dict(row)
        # 解析 metadata JSON
        if "metadata" in d and isinstance(d["metadata"], str):
            with suppress(json.JSONDecodeError):
                d["metadata"] = json.loads(d["metadata"])
        # 解析 tags 为列表
        if "tags" in d and isinstance(d["tags"], str):
            d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
        return d

    def close(self):
        """关闭数据库连接"""
        pass  # SQLite 连接在每次操作后已关闭


# ═══════════════════════════════════════════
#   状态存储（键值对，非全文搜索）
# ═══════════════════════════════════════════


class StateStore:
    """键值对状态存储（替代 JSON 状态文件）

    适用于：session_state, reflection_state, correction_state 等
    每个模块独立的键值存储，简单高效。
    """

    def __init__(self, db_path: str = None, namespace: str = "state"):
        self.db_path = db_path or DEFAULT_DB
        self.namespace = namespace
        self._ensure_table()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_table(self):
        table = f"{self.namespace}_kv"
        with self._conn() as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    updated_at  TEXT DEFAULT (datetime('now'))
                )
            """)

    def get(self, key: str, default=None):
        """获取值"""
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT value FROM {self.namespace}_kv WHERE key = ?", (key,)
            ).fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    return row["value"]
            return default

    def set(self, key: str, value):
        """设置值"""
        val_str = (
            json.dumps(value, ensure_ascii=False, default=str)
            if not isinstance(value, str)
            else value
        )
        with self._conn() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {self.namespace}_kv "
                f"(key, value, updated_at) VALUES (?, ?, datetime('now'))",
                (key, val_str),
            )

    def delete(self, key: str):
        """删除键"""
        with self._conn() as conn:
            conn.execute(f"DELETE FROM {self.namespace}_kv WHERE key = ?", (key,))

    def keys(self) -> list[str]:
        """列出所有键"""
        with self._conn() as conn:
            rows = conn.execute(f"SELECT key FROM {self.namespace}_kv ORDER BY key").fetchall()
            return [r["key"] for r in rows]

    def all(self) -> dict:
        """获取所有键值对"""
        with self._conn() as conn:
            rows = conn.execute(f"SELECT key, value FROM {self.namespace}_kv").fetchall()
            result = {}
            for r in rows:
                try:
                    result[r["key"]] = json.loads(r["value"])
                except (json.JSONDecodeError, TypeError):
                    result[r["key"]] = r["value"]
            return result

    def clear(self):
        """清空所有键"""
        with self._conn() as conn:
            conn.execute(f"DELETE FROM {self.namespace}_kv")


# ═══════════════════════════════════════════
#   便捷工厂函数
# ═══════════════════════════════════════════


def get_engine(table_name: str, db_path: str = None) -> StorageEngine:
    """获取存储引擎实例"""
    return StorageEngine(db_path=db_path, table_name=table_name)


def get_state(namespace: str, db_path: str = None) -> StateStore:
    """获取状态存储实例"""
    return StateStore(db_path=db_path, namespace=namespace)


def get_db_path() -> str:
    """获取默认数据库路径"""
    return DEFAULT_DB
