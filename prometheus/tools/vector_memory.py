#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 普罗米修斯 · 向量记忆 · Vector Memory (HRR)           ║
║                                                              ║
║   基于 Holographic Reduced Representations 思想的            ║
║   语义向量记忆系统。                                          ║
║                                                              ║
║   核心思想：                                                  ║
║     • 每段文本映射到固定维度的稠密向量                        ║
║     • 相似语义的文本产生相似向量                              ║
║     • 通过余弦相似度检索语义相关记忆                          ║
║     • 支持权重衰减、重要性加权、多层过滤                      ║
║                                                              ║
║   技术实现：                                                  ║
║     • 特征哈希（Hashing Trick） + 随机投影                    ║
║     • TF 加权 + L2 归一化                                    ║
║     • 纯 Python + NumPy，零外部依赖                           ║
║                                                              ║
║   与 ContextManager 的关系：                                  ║
║     ContextManager 是关键词检索（FTS5），                     ║
║     VectorMemory 是语义检索（余弦相似度），                   ║
║     两者互补，共同服务于 Prometheus 的记忆系统。               ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import re
import math
import json
import struct
import hashlib
import sqlite3
import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

import numpy as np


# ═══════════════════════════════════════════
#   配置
# ═══════════════════════════════════════════

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_DB = os.path.join(DATA_DIR, "vector_memory.db")

# 默认向量维度（512 维在精度和性能间取得平衡）
DEFAULT_DIM = 512

# 哈希空间大小（用于特征哈希）
HASH_SPACE = 2 ** 18  # 262144

# 中文停用词（高频低信息量词）
_ZH_STOPS = set("的了在是我有和人这中大为上个国不也子时道出会三要于下得可你年生自")

# 英文停用词
_EN_STOPS = set("the a an is are was were be been being have has had do does did will would shall should may might can could of in on at to for with by from as into through during before after above below between out off over under".split())


# ═══════════════════════════════════════════
#   文本向量化器
# ═══════════════════════════════════════════

class TextVectorizer:
    """将文本映射到固定维度的稠密向量。
    
    实现思路（HRR 启发）：
      1. 分词 + 去停用词
      2. 对每个 token 生成高维稀疏特征（哈希映射）
      3. TF 加权求和
      4. L2 归一化
    
    使用随机投影矩阵将稀疏特征降维到目标维度，
    类似于 Johnson-Lindenstrauss 变换。
    """
    
    def __init__(self, dim: int = DEFAULT_DIM, seed: int = 42):
        """
        Args:
            dim: 输出向量维度
            seed: 随机种子（保证可复现性）
        """
        self.dim = dim
        self._seed = seed
        
        # 预生成随机投影矩阵 (HASH_SPACE -> dim)
        # 使用固定种子保证一致性
        rng = np.random.RandomState(seed)
        # 稀疏随机投影：每行只有 sqrt(HASH_SPACE) 个非零元素
        self._projection = self._build_projection(HASH_SPACE, dim, rng)
        
        # 纹理矩阵（HRR 核心：用于向量绑定/解绑的循环卷积核）
        self._texture = self._build_texture(dim, rng)
    
    @staticmethod
    def _build_projection(hash_size: int, dim: int, rng: np.random.RandomState) -> np.ndarray:
        """构建稀疏随机投影矩阵。
        
        使用 ±1/sqrt(k) 的稀疏投影，其中 k = hash_size // dim。
        这保证了 Johnson-Lindenstrauss 引理：内积近似保持。
        """
        k = max(hash_size // dim, 1)
        proj = np.zeros((hash_size, dim), dtype=np.float32)
        
        for i in range(hash_size):
            # 随机选择 k 个位置
            indices = rng.choice(dim, size=min(k, dim), replace=False)
            # 随机 ±1 值
            signs = rng.choice([-1.0, 1.0], size=len(indices))
            proj[i, indices] = signs / math.sqrt(k)
        
        return proj
    
    @staticmethod
    def _build_texture(dim: int, rng: np.random.RandomState) -> np.ndarray:
        """构建纹理矩阵（HRR 的循环卷积核）。
        
        用于向量的绑定（binding）和解绑（unbinding）操作。
        纹理矩阵的行是单位向量，支持 superposition。
        """
        texture = rng.randn(16, dim).astype(np.float32)
        # 归一化为单位向量
        norms = np.linalg.norm(texture, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1.0)
        texture /= norms
        return texture
    
    def _tokenize(self, text: str) -> List[str]:
        """中英文混合分词。
        
        策略：
          - 英文：按空格/标点分词，转小写
          - 中文：unigram + bigram（无外部依赖）
          - 过滤停用词和长度为 1 的 token
        """
        tokens = []
        text = text.lower().strip()
        
        # 提取英文单词
        en_words = re.findall(r'[a-z][a-z0-9]+', text)
        for w in en_words:
            if w not in _EN_STOPS and len(w) > 1:
                tokens.append(w)
        
        # 提取中文字符序列
        zh_segments = re.findall(r'[\u4e00-\u9fff]+', text)
        for seg in zh_segments:
            # unigram
            for ch in seg:
                if ch not in _ZH_STOPS:
                    tokens.append(ch)
            # bigram
            for i in range(len(seg) - 1):
                bigram = seg[i:i+2]
                if bigram[0] not in _ZH_STOPS or bigram[1] not in _ZH_STOPS:
                    tokens.append(bigram)
        
        # 混合 n-gram（中英交界处）
        for m in re.finditer(r'[\u4e00-\u9fff]+[a-z0-9]+|[a-z0-9]+[\u4e00-\u9fff]+', text):
            tokens.append(m.group())
        
        return tokens
    
    def _hash_token(self, token: str) -> int:
        """将 token 哈希到固定空间。"""
        h = hashlib.md5(token.encode('utf-8')).hexdigest()
        return int(h, 16) % HASH_SPACE
    
    def vectorize(self, text: str) -> np.ndarray:
        """将文本转换为归一化向量。
        
        Args:
            text: 输入文本
            
        Returns:
            L2 归一化的稠密向量 (dim,)
        """
        tokens = self._tokenize(text)
        if not tokens:
            return np.zeros(self.dim, dtype=np.float32)
        
        # 计算 TF（词频归一化）
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        total = len(tokens)
        
        # 稀疏向量表示
        sparse = np.zeros(HASH_SPACE, dtype=np.float32)
        for token, count in tf.items():
            idx = self._hash_token(token)
            # TF 加权
            weight = (0.5 + 0.5 * count / total)  # 增强版 TF
            sparse[idx] += weight
        
        # 随机投影降维
        vec = sparse @ self._projection
        
        # L2 归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        
        return vec.astype(np.float32)
    
    def bind(self, vec_a: np.ndarray, vec_b: np.ndarray) -> np.ndarray:
        """HRR 绑定操作（Circular Convolution）。
        
        将两个向量"绑定"在一起，表示它们的关联。
        结果向量可以被解绑以恢复其中一个。
        
        近似实现：逐元素乘法 + 纹理混合。
        精确实现需要 FFT 做循环卷积，这里用近似。
        """
        # 近似循环卷积：element-wise product + texture mixing
        bound = vec_a * vec_b
        
        # 纹理增强（HRR 的 superposition 能力）
        idx = hash((vec_a.tobytes()[:16], vec_b.tobytes()[:16])) % len(self._texture)
        bound = bound + 0.1 * self._texture[idx]
        
        # 归一化
        norm = np.linalg.norm(bound)
        if norm > 0:
            bound /= norm
        
        return bound.astype(np.float32)
    
    def unbind(self, bound: np.ndarray, vec_hint: np.ndarray) -> np.ndarray:
        """HRR 解绑操作（Circular Correlation）。
        
        从绑定向量中恢复出另一个向量。
        """
        # 近似：element-wise division (在归一化空间中等价于反相关)
        # 加入 epsilon 防止除零
        eps = 1e-8
        unbound = bound / (vec_hint + eps)
        
        # 归一化
        norm = np.linalg.norm(unbound)
        if norm > 0:
            unbound /= norm
        
        return unbound.astype(np.float32)
    
    def superpose(self, vectors: List[np.ndarray], weights: List[float] = None) -> np.ndarray:
        """HRR 叠加操作（Superposition）。
        
        将多个向量叠加成一个向量，表示它们的集合。
        权重可选，默认等权。
        """
        if not vectors:
            return np.zeros(self.dim, dtype=np.float32)
        
        if weights is None:
            weights = [1.0 / len(vectors)] * len(vectors)
        
        result = np.zeros(self.dim, dtype=np.float32)
        for v, w in zip(vectors, weights):
            result += w * v
        
        norm = np.linalg.norm(result)
        if norm > 0:
            result /= norm
        
        return result.astype(np.float32)
    
    def similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """计算两个向量的余弦相似度。"""
        dot = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))


# ═══════════════════════════════════════════
#   向量存储
# ═══════════════════════════════════════════

def _vec_to_bytes(vec: np.ndarray) -> bytes:
    """向量 → 二进制（float32 packed）。"""
    return vec.astype(np.float32).tobytes()


def _bytes_to_vec(data: bytes, dim: int = DEFAULT_DIM) -> np.ndarray:
    """二进制 → 向量。"""
    arr = np.frombuffer(data, dtype=np.float32)
    if len(arr) != dim:
        # 尝试重塑
        arr = np.zeros(dim, dtype=np.float32)
    return arr


class VectorStore:
    """SQLite 向量存储，支持余弦相似度检索。
    
    表结构：
      - id: 主键
      - content: 文本内容
      - vector: 二进制向量 (float32)
      - layer: 记忆层级 (working/episodic/longterm)
      - importance: 重要性 (0.0-1.0)
      - source: 来源
      - tags: JSON 标签数组
      - created_at: 创建时间
      - accessed_at: 最后访问时间
      - access_count: 访问次数
    """
    
    def __init__(self, db_path: str = None, dim: int = DEFAULT_DIM):
        self.db_path = db_path or DEFAULT_DB
        self.dim = dim
        self._init_db()
    
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
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
    
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    layer TEXT DEFAULT 'working',
                    importance REAL DEFAULT 0.5,
                    source TEXT DEFAULT 'unknown',
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    token_estimate INTEGER DEFAULT 0
                )
            """)
            # 索引加速
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vectors_layer ON vectors(layer)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vectors_importance ON vectors(importance DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vectors_created ON vectors(created_at DESC)")
    
    def add(self, content: str, vector: np.ndarray, layer: str = "working",
            importance: float = 0.5, source: str = "unknown",
            tags: List[str] = None) -> int:
        """存储一条向量化记忆。
        
        Returns:
            新记录的 ID
        """
        now = datetime.datetime.now().isoformat()
        token_est = self._estimate_tokens(content)
        
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO vectors 
                (content, vector, layer, importance, source, tags, 
                 created_at, accessed_at, access_count, token_estimate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                content,
                _vec_to_bytes(vector),
                layer,
                importance,
                source,
                json.dumps(tags or [], ensure_ascii=False),
                now,
                now,
                token_est,
            ))
            return cursor.lastrowid
    
    def search(self, query_vector: np.ndarray, limit: int = 10,
               layer: str = None, min_importance: float = 0.0,
               min_similarity: float = 0.0,
               time_decay: bool = True) -> List[dict]:
        """语义相似度检索。
        
        Args:
            query_vector: 查询向量
            limit: 最大返回数
            layer: 限定层级（None = 全部）
            min_importance: 最低重要性阈值
            min_similarity: 最低相似度阈值
            time_decay: 是否对结果施加时间衰减
            
        Returns:
            [{"id", "content", "similarity", "score", "layer", ...}, ...]
        """
        now = datetime.datetime.now()
        results = []
        
        with self._conn() as conn:
            where_parts = ["1=1"]
            params = []
            
            if layer:
                where_parts.append("layer = ?")
                params.append(layer)
            if min_importance > 0:
                where_parts.append("importance >= ?")
                params.append(min_importance)
            
            where_clause = " AND ".join(where_parts)
            
            rows = conn.execute(f"""
                SELECT id, content, vector, layer, importance, source, 
                       tags, created_at, accessed_at, access_count, token_estimate
                FROM vectors
                WHERE {where_clause}
            """, params).fetchall()
        
        for row in rows:
            vec = _bytes_to_vec(row[2], self.dim)
            
            # 余弦相似度
            sim = float(np.dot(query_vector, vec) / 
                       (np.linalg.norm(query_vector) * np.linalg.norm(vec) + 1e-8))
            
            if sim < min_similarity:
                continue
            
            # 综合得分 = 相似度 × importance × time_decay
            score = sim * row[4]  # × importance
            
            if time_decay:
                try:
                    created = datetime.datetime.fromisoformat(row[7])
                    days = (now - created).days
                    decay = math.exp(-0.01 * days)  # 每天衰减 1%
                    score *= max(decay, 0.1)  # 最低 10%
                except (ValueError, TypeError):
                    pass
            
            results.append({
                "id": row[0],
                "content": row[1],
                "similarity": round(sim, 4),
                "score": round(score, 4),
                "layer": row[3],
                "importance": row[4],
                "source": row[5],
                "tags": json.loads(row[6]) if row[6] else [],
                "created_at": row[7],
                "accessed_at": row[8],
                "access_count": row[9],
                "token_estimate": row[10],
            })
        
        # 按综合得分排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:limit]
    
    def get(self, record_id: int) -> Optional[dict]:
        """获取单条记录。"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT id, content, vector, layer, importance, source,
                       tags, created_at, accessed_at, access_count, token_estimate
                FROM vectors WHERE id = ?
            """, (record_id,)).fetchone()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "content": row[1],
            "vector": _bytes_to_vec(row[2], self.dim),
            "layer": row[3],
            "importance": row[4],
            "source": row[5],
            "tags": json.loads(row[6]) if row[6] else [],
            "created_at": row[7],
            "accessed_at": row[8],
            "access_count": row[9],
            "token_estimate": row[10],
        }
    
    def update_access(self, record_id: int):
        """更新访问时间和次数。"""
        now = datetime.datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute("""
                UPDATE vectors 
                SET accessed_at = ?, access_count = access_count + 1
                WHERE id = ?
            """, (now, record_id))
    
    def delete(self, record_id: int) -> bool:
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM vectors WHERE id = ?", (record_id,))
            return cursor.rowcount > 0
    
    def count(self, layer: str = None) -> int:
        with self._conn() as conn:
            if layer:
                row = conn.execute(
                    "SELECT COUNT(*) FROM vectors WHERE layer = ?", (layer,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()
            return row[0] if row else 0
    
    def stats(self) -> dict:
        """存储统计。"""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
            total_tokens = conn.execute(
                "SELECT COALESCE(SUM(token_estimate), 0) FROM vectors"
            ).fetchone()[0]
            
            by_layer = {}
            for layer in ["working", "episodic", "longterm"]:
                row = conn.execute(
                    "SELECT COUNT(*) FROM vectors WHERE layer = ?", (layer,)
                ).fetchone()
                by_layer[layer] = row[0]
            
            avg_importance = conn.execute(
                "SELECT COALESCE(AVG(importance), 0) FROM vectors"
            ).fetchone()[0]
        
        return {
            "total_records": total,
            "total_tokens": total_tokens,
            "by_layer": by_layer,
            "avg_importance": round(avg_importance, 3),
            "dim": self.dim,
            "db_size_bytes": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
        }
    
    @staticmethod
    def _estimate_tokens(text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 4)


# ═══════════════════════════════════════════
#   语义记忆（高层 API）
# ═══════════════════════════════════════════

class SemanticMemory:
    """语义记忆系统 —— Prometheus 的向量记忆入口。
    
    整合 TextVectorizer 和 VectorStore，提供高层 API：
      - remember(): 记住一段文本（自动向量化+存储）
      - recall(): 语义检索（输入自然语言查询）
      - associate(): 关联发现（找到与给定文本最相关的记忆）
      - summarize(): 记忆概览
    
    与 ContextManager 的分工：
      - ContextManager.search() → FTS5 关键词匹配（精确查找）
      - SemanticMemory.recall() → 向量相似度（语义联想）
    """
    
    def __init__(self, db_path: str = None, dim: int = DEFAULT_DIM):
        self.vectorizer = TextVectorizer(dim=dim)
        self.store = VectorStore(db_path=db_path, dim=dim)
    
    def remember(self, content: str, layer: str = "working",
                 importance: float = 0.5, source: str = "task",
                 tags: List[str] = None) -> dict:
        """记住一段文本。
        
        自动向量化并存储。返回存储信息。
        """
        vec = self.vectorizer.vectorize(content)
        record_id = self.store.add(
            content=content,
            vector=vec,
            layer=layer,
            importance=importance,
            source=source,
            tags=tags,
        )
        return {
            "id": record_id,
            "layer": layer,
            "importance": importance,
            "token_estimate": VectorStore._estimate_tokens(content),
        }
    
    def recall(self, query: str, limit: int = 5, layer: str = None,
               min_similarity: float = 0.1) -> List[dict]:
        """语义检索 —— 从记忆中找到与查询最相关的内容。
        
        Args:
            query: 自然语言查询
            limit: 最大返回数
            layer: 限定层级
            min_similarity: 最低相似度（默认 0.1 过滤噪声）
            
        Returns:
            按相关度排序的记忆列表
        """
        query_vec = self.vectorizer.vectorize(query)
        results = self.store.search(
            query_vector=query_vec,
            limit=limit,
            layer=layer,
            min_similarity=min_similarity,
        )
        
        # 更新访问记录
        for r in results:
            self.store.update_access(r["id"])
        
        return results
    
    def associate(self, text: str, limit: int = 5) -> List[dict]:
        """关联发现 —— 找到与给定文本语义相关的所有记忆。
        
        与 recall 的区别：不更新访问记录（只读探索）。
        """
        query_vec = self.vectorizer.vectorize(text)
        return self.store.search(
            query_vector=query_vec,
            limit=limit,
            min_similarity=0.15,  # 关联发现用稍高的阈值
            time_decay=False,
        )
    
    def bind_concepts(self, concept_a: str, concept_b: str) -> dict:
        """HRR 概念绑定 —— 将两个概念关联在一起。
        
        绑定后的向量可以用于检索同时涉及两个概念的记忆。
        """
        vec_a = self.vectorizer.vectorize(concept_a)
        vec_b = self.vectorizer.vectorize(concept_b)
        bound = self.vectorizer.bind(vec_a, vec_b)
        
        # 存储绑定向量
        record_id = self.store.add(
            content=f"[BIND] {concept_a} ↔ {concept_b}",
            vector=bound,
            layer="longterm",  # 概念关联默认长期
            importance=0.7,
            source="hrr_bind",
            tags=["hrr_bind", concept_a, concept_b],
        )
        
        return {
            "id": record_id,
            "concept_a": concept_a,
            "concept_b": concept_b,
            "operation": "bind",
        }
    
    def superpose_memories(self, contents: List[str], 
                          weights: List[float] = None) -> dict:
        """HRR 叠加 —— 将多段记忆融合为一个概念向量。"""
        vecs = [self.vectorizer.vectorize(c) for c in contents]
        superposed = self.vectorizer.superpose(vecs, weights)
        
        # 合并内容描述
        summary = " ⊕ ".join(c[:30] for c in contents)
        
        record_id = self.store.add(
            content=f"[SUPERPOSE] {summary}",
            vector=superposed,
            layer="longterm",
            importance=0.6,
            source="hrr_superpose",
            tags=["hrr_superpose"],
        )
        
        return {
            "id": record_id,
            "sources": contents,
            "operation": "superpose",
            "dim": len(superposed),
        }
    
    def find_related(self, text: str, threshold: float = 0.3) -> List[dict]:
        """发现与文本相关联的所有记忆（跨层级）。"""
        query_vec = self.vectorizer.vectorize(text)
        return self.store.search(
            query_vector=query_vec,
            limit=20,
            min_similarity=threshold,
            time_decay=False,
        )
    
    def memory_dump(self, limit: int = 20, layer: str = None) -> List[dict]:
        """导出记忆（用于调试/可视化）。"""
        with self.store._conn() as conn:
            where = "WHERE layer = ?" if layer else ""
            params = [layer] if layer else []
            rows = conn.execute(f"""
                SELECT id, content, layer, importance, source, 
                       tags, created_at, access_count, token_estimate
                FROM vectors {where}
                ORDER BY created_at DESC
                LIMIT ?
            """, params + [limit]).fetchall()
        
        return [
            {
                "id": r[0], "content": r[1][:80], "layer": r[2],
                "importance": r[3], "source": r[4],
                "tags": json.loads(r[5]) if r[5] else [],
                "created_at": r[6], "access_count": r[7],
                "token_estimate": r[8],
            }
            for r in rows
        ]
    
    def summary(self) -> dict:
        """记忆概览。"""
        stats = self.store.stats()
        return {
            "total_memories": stats["total_records"],
            "total_tokens": stats["total_tokens"],
            "by_layer": stats["by_layer"],
            "avg_importance": stats["avg_importance"],
            "vector_dim": stats["dim"],
            "db_size_kb": round(stats["db_size_bytes"] / 1024, 1),
        }


# ═══════════════════════════════════════════
#   便捷入口
# ═══════════════════════════════════════════

_global_memory: Optional[SemanticMemory] = None

def get_memory(db_path: str = None) -> SemanticMemory:
    """获取全局语义记忆实例。"""
    global _global_memory
    if _global_memory is None:
        _global_memory = SemanticMemory(db_path=db_path)
    return _global_memory

def remember(content: str, **kwargs) -> dict:
    return get_memory().remember(content, **kwargs)

def recall(query: str, **kwargs) -> List[dict]:
    return get_memory().recall(query, **kwargs)
