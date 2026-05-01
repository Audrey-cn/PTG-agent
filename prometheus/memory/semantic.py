#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import hashlib
import json
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from .storage import HybridStorage

DEFAULT_DIM = 512
HASH_SPACE = 2**18

_ZH_STOPS = set("的了在是我有和人这中大为上个国不也子时道出会三要于下得可你年生自")
_EN_STOPS = set(
    [
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "can",
        "could",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "out",
        "off",
        "over",
        "under",
    ]
)


@dataclass
class VectorRecord:
    record_id: str
    content: str
    vector: list[float] = field(default_factory=list)
    layer: str = "working"
    importance: float = 0.5
    source: str = "unknown"
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    similarity: float = 0.0


class TextVectorizer:
    """文本向量化器"""

    def __init__(self, dim: int = DEFAULT_DIM, seed: int = 42):
        self.dim = dim
        self._seed = seed

        if HAS_NUMPY:
            import numpy as np

            rng = np.random.RandomState(seed)
            self._projection = self._build_projection(rng)
        else:
            self._projection = None

    def _build_projection(self, rng):
        import numpy as np

        k = max(HASH_SPACE // self.dim, 1)
        proj = np.zeros((HASH_SPACE, self.dim), dtype=np.float32)

        for i in range(HASH_SPACE):
            indices = rng.choice(self.dim, size=min(k, self.dim), replace=False)
            signs = rng.choice([-1.0, 1.0], size=len(indices))
            proj[i, indices] = signs / math.sqrt(k)

        return proj

    def _tokenize(self, text: str) -> list[str]:
        tokens = []
        text = text.lower().strip()

        en_words = re.findall(r"[a-z][a-z0-9]+", text)
        for w in en_words:
            if w not in _EN_STOPS and len(w) > 1:
                tokens.append(w)

        zh_segments = re.findall(r"[\u4e00-\u9fff]+", text)
        for seg in zh_segments:
            for ch in seg:
                if ch not in _ZH_STOPS:
                    tokens.append(ch)
            for i in range(len(seg) - 1):
                bigram = seg[i : i + 2]
                tokens.append(bigram)

        return tokens

    def _hash_token(self, token: str) -> int:
        h = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(h, 16) % HASH_SPACE

    def vectorize(self, text: str) -> list[float]:
        if not HAS_NUMPY:
            return self._simple_hash_vector(text)

        import numpy as np

        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dim

        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        total = len(tokens)

        sparse = np.zeros(HASH_SPACE, dtype=np.float32)
        for token, count in tf.items():
            idx = self._hash_token(token)
            weight = 0.5 + 0.5 * count / total
            sparse[idx] += weight

        vec = sparse @ self._projection

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm

        return vec.tolist()

    def _simple_hash_vector(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        vec = [0.0] * self.dim

        for _i, token in enumerate(tokens):
            h = self._hash_token(token)
            idx = h % self.dim
            vec[idx] += 1.0

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    @staticmethod
    def similarity(vec_a: list[float], vec_b: list[float]) -> float:
        if HAS_NUMPY:
            import numpy as np

            a = np.array(vec_a)
            b = np.array(vec_b)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
        else:
            dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
            norm_a = math.sqrt(sum(a * a for a in vec_a))
            norm_b = math.sqrt(sum(b * b for b in vec_b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)


class SemanticStore:
    """语义记忆系统"""

    def __init__(self, data_dir: str = None, dim: int = DEFAULT_DIM):
        self.storage = HybridStorage(data_dir=data_dir)
        self.vectorizer = TextVectorizer(dim=dim)
        self.dim = dim

        self.db_path = os.path.join(self.storage.data_dir, "vectors.db")
        self._init_vector_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_vector_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    record_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    layer TEXT DEFAULT 'working',
                    importance REAL DEFAULT 0.5,
                    source TEXT DEFAULT 'unknown',
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vectors_layer ON vectors(layer)")

    def remember(
        self,
        content: str,
        layer: str = "working",
        importance: float = 0.5,
        source: str = "task",
        tags: list[str] = None,
    ) -> dict:
        """记住内容（向量化存储）"""
        vector = self.vectorizer.vectorize(content)
        record_id = self._generate_id()

        vector_bytes = self._vector_to_bytes(vector)

        now = datetime.datetime.now().isoformat()

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO vectors
                (record_id, content, vector, layer, importance, source, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record_id,
                    content,
                    vector_bytes,
                    layer,
                    importance,
                    source,
                    json.dumps(tags or [], ensure_ascii=False),
                    now,
                ),
            )

        return {
            "id": record_id,
            "layer": layer,
            "importance": importance,
        }

    def recall(
        self, query: str, limit: int = 5, layer: str = None, min_similarity: float = 0.1
    ) -> list[VectorRecord]:
        """语义检索"""
        query_vector = self.vectorizer.vectorize(query)

        with self._conn() as conn:
            if layer:
                rows = conn.execute("SELECT * FROM vectors WHERE layer = ?", (layer,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM vectors").fetchall()

        results = []
        for row in rows:
            vec = self._bytes_to_vector(row[2])
            sim = TextVectorizer.similarity(query_vector, vec)

            if sim < min_similarity:
                continue

            results.append(
                VectorRecord(
                    record_id=row[0],
                    content=row[1],
                    vector=vec,
                    layer=row[3],
                    importance=row[4],
                    source=row[5],
                    tags=json.loads(row[6]) if row[6] else [],
                    created_at=row[7],
                    similarity=sim,
                )
            )

        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:limit]

    def associate(self, text: str, limit: int = 5) -> list[VectorRecord]:
        """关联发现"""
        return self.recall(text, limit=limit, min_similarity=0.15)

    def forget(self, record_id: str) -> bool:
        """删除记忆"""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM vectors WHERE record_id = ?", (record_id,))
            return cursor.rowcount > 0

    def stats(self) -> dict:
        """统计信息"""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]

            by_layer = {}
            for layer in ["working", "episodic", "longterm"]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM vectors WHERE layer = ?", (layer,)
                ).fetchone()[0]
                by_layer[layer] = count

        return {
            "total": total,
            "by_layer": by_layer,
            "dim": self.dim,
            "has_numpy": HAS_NUMPY,
        }

    def _generate_id(self) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(str(datetime.datetime.now().timestamp()).encode()).hexdigest()[
            :6
        ]
        return f"vec_{timestamp}_{random_suffix}"

    def _vector_to_bytes(self, vector: list[float]) -> bytes:
        if HAS_NUMPY:
            import numpy as np

            return np.array(vector, dtype=np.float32).tobytes()
        else:
            import struct

            return struct.pack(f"{len(vector)}f", *vector)

    def _bytes_to_vector(self, data: bytes) -> list[float]:
        if HAS_NUMPY:
            import numpy as np

            return np.frombuffer(data, dtype=np.float32).tolist()
        else:
            import struct

            count = len(data) // 4
            return list(struct.unpack(f"{count}f", data))
