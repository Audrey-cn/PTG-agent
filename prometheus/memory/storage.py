#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   💾 普罗米修斯 · 混合存储层 · Hybrid Storage               ║
║                                                              ║
║   双写机制：同时写入 MD 文件和 SQLite 数据库                 ║
║     - MD 文件：人可读、编辑器维护、Git 版本控制              ║
║     - SQLite：高效查询、向量检索、全文搜索                   ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import yaml
import sqlite3
import hashlib
import datetime
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
from pathlib import Path


MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(MEMORY_DIR, "data")
DEFAULT_DB = os.path.join(DATA_DIR, "memory.db")


@dataclass
class MemoryRecord:
    memory_id: str
    content: str
    layer: str = "working"
    importance: float = 0.5
    source: str = "unknown"
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    accessed_at: str = ""
    access_count: int = 0
    token_estimate: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.accessed_at:
            self.accessed_at = self.created_at
        if self.token_estimate == 0:
            self.token_estimate = self._estimate_tokens(self.content)
        if not self.content_hash:
            self.content_hash = self._compute_hash(self.content)
    
    @staticmethod
    def _compute_hash(text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
    
    @staticmethod
    def _estimate_tokens(text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 4)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "MemoryRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class HybridStorage:
    """混合存储层：同时管理 MD 文件和 SQLite 数据库"""
    
    LAYERS = ["working", "episodic", "longterm"]
    
    def __init__(self, data_dir: str = None, db_path: str = None):
        self.data_dir = data_dir or DATA_DIR
        self.db_path = db_path or os.path.join(self.data_dir, "memory.db")
        
        os.makedirs(self.data_dir, exist_ok=True)
        for layer in self.LAYERS:
            os.makedirs(os.path.join(self.data_dir, layer), exist_ok=True)
        
        self._init_db()
    
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    layer TEXT DEFAULT 'working',
                    importance REAL DEFAULT 0.5,
                    source TEXT DEFAULT 'unknown',
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    token_estimate INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    content_hash TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_layer ON memories(layer)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at DESC)")
            
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                        memory_id, content, tags,
                        content='memories',
                        content_rowid='rowid'
                    )
                """)
            except sqlite3.OperationalError:
                pass
    
    def _content_hash(self, content: str) -> str:
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]
    
    def _md_path(self, memory_id: str, layer: str) -> str:
        return os.path.join(self.data_dir, layer, f"{memory_id}.md")
    
    def _generate_id(self) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(str(datetime.datetime.now().timestamp()).encode()).hexdigest()[:6]
        return f"mem_{timestamp}_{random_suffix}"
    
    def save(self, record: MemoryRecord) -> str:
        if not record.memory_id:
            record.memory_id = self._generate_id()
        
        record.updated_at = datetime.datetime.now().isoformat()
        record.content_hash = self._content_hash(record.content)
        
        self._save_to_md(record)
        self._save_to_sqlite(record)
        
        return record.memory_id
    
    def _save_to_md(self, record: MemoryRecord):
        filepath = self._md_path(record.memory_id, record.layer)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        frontmatter = {
            "id": record.memory_id,
            "layer": record.layer,
            "importance": record.importance,
            "source": record.source,
            "tags": record.tags,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "accessed_at": record.accessed_at,
            "access_count": record.access_count,
            "token_estimate": record.token_estimate,
        }
        frontmatter.update(record.metadata)
        
        fm_yaml = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"---\n{fm_yaml}---\n\n")
            f.write(record.content)
    
    def _save_to_sqlite(self, record: MemoryRecord):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memories 
                (memory_id, content, layer, importance, source, tags,
                 created_at, updated_at, accessed_at, access_count, 
                 token_estimate, metadata, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.memory_id,
                record.content,
                record.layer,
                record.importance,
                record.source,
                json.dumps(record.tags, ensure_ascii=False),
                record.created_at,
                record.updated_at,
                record.accessed_at,
                record.access_count,
                record.token_estimate,
                json.dumps(record.metadata, ensure_ascii=False),
                record.content_hash,
            ))
            try:
                conn.execute("""
                    INSERT INTO memories_fts(rowid, memory_id, content, tags)
                    SELECT rowid, memory_id, content, tags FROM memories
                    WHERE memory_id = ?
                """, (record.memory_id,))
            except sqlite3.OperationalError:
                pass
    
    def load(self, memory_id: str) -> Optional[MemoryRecord]:
        record = self._load_from_sqlite(memory_id)
        if record:
            return record
        return self._load_from_md(memory_id)
    
    def _load_from_sqlite(self, memory_id: str) -> Optional[MemoryRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE memory_id = ?", (memory_id,)
            ).fetchone()
        
        if not row:
            return None
        
        return MemoryRecord(
            memory_id=row["memory_id"],
            content=row["content"],
            layer=row["layer"],
            importance=row["importance"],
            source=row["source"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            accessed_at=row["accessed_at"],
            access_count=row["access_count"],
            token_estimate=row["token_estimate"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
    
    def _load_from_md(self, memory_id: str) -> Optional[MemoryRecord]:
        for layer in self.LAYERS:
            filepath = self._md_path(memory_id, layer)
            if os.path.exists(filepath):
                return self._parse_md(filepath)
        return None
    
    def _parse_md(self, filepath: str) -> Optional[MemoryRecord]:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if not match:
            return None
        
        frontmatter = yaml.safe_load(match.group(1))
        body = match.group(2).strip()
        
        return MemoryRecord(
            memory_id=frontmatter.get("id", ""),
            content=body,
            layer=frontmatter.get("layer", "working"),
            importance=frontmatter.get("importance", 0.5),
            source=frontmatter.get("source", "unknown"),
            tags=frontmatter.get("tags", []),
            created_at=frontmatter.get("created_at", ""),
            updated_at=frontmatter.get("updated_at", ""),
            accessed_at=frontmatter.get("accessed_at", ""),
            access_count=frontmatter.get("access_count", 0),
            token_estimate=frontmatter.get("token_estimate", 0),
            metadata={k: v for k, v in frontmatter.items() 
                     if k not in ["id", "layer", "importance", "source", "tags",
                                 "created_at", "updated_at", "accessed_at", 
                                 "access_count", "token_estimate"]},
        )
    
    def delete(self, memory_id: str) -> bool:
        record = self.load(memory_id)
        if not record:
            return False
        
        md_path = self._md_path(memory_id, record.layer)
        if os.path.exists(md_path):
            os.remove(md_path)
        
        with self._conn() as conn:
            conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))
        
        return True
    
    def list_by_layer(self, layer: str, limit: int = 100) -> List[MemoryRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE layer = ? ORDER BY created_at DESC LIMIT ?",
                (layer, limit)
            ).fetchall()
        
        return [MemoryRecord(
            memory_id=r["memory_id"],
            content=r["content"],
            layer=r["layer"],
            importance=r["importance"],
            source=r["source"],
            tags=json.loads(r["tags"]) if r["tags"] else [],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            accessed_at=r["accessed_at"],
            access_count=r["access_count"],
            token_estimate=r["token_estimate"],
            metadata=json.loads(r["metadata"]) if r["metadata"] else {},
        ) for r in rows]
    
    def search(self, query: str, limit: int = 10) -> List[MemoryRecord]:
        with self._conn() as conn:
            rows = []
            try:
                rows = conn.execute("""
                    SELECT m.* FROM memories m
                    JOIN memories_fts fts ON m.memory_id = fts.memory_id
                    WHERE memories_fts MATCH ?
                    ORDER BY m.importance DESC
                    LIMIT ?
                """, (query, limit)).fetchall()
            except sqlite3.OperationalError:
                pass
            
            if not rows:
                rows = conn.execute("""
                    SELECT * FROM memories 
                    WHERE content LIKE ? OR tags LIKE ?
                    ORDER BY importance DESC
                    LIMIT ?
                """, (f"%{query}%", f"%{query}%", limit)).fetchall()
        
        return [MemoryRecord(
            memory_id=r["memory_id"],
            content=r["content"],
            layer=r["layer"],
            importance=r["importance"],
            source=r["source"],
            tags=json.loads(r["tags"]) if r["tags"] else [],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            accessed_at=r["accessed_at"],
            access_count=r["access_count"],
            token_estimate=r["token_estimate"],
            metadata=json.loads(r["metadata"]) if r["metadata"] else {},
        ) for r in rows]
    
    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            by_layer = {}
            for layer in self.LAYERS:
                count = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE layer = ?", (layer,)
                ).fetchone()[0]
                by_layer[layer] = count
            
            total_tokens = conn.execute(
                "SELECT COALESCE(SUM(token_estimate), 0) FROM memories"
            ).fetchone()[0]
        
        return {
            "total": total,
            "by_layer": by_layer,
            "total_tokens": total_tokens,
            "db_path": self.db_path,
            "data_dir": self.data_dir,
        }
