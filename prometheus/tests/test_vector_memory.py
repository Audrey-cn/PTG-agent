#!/usr/bin/env python3
"""
P2-6 向量记忆（HRR）测试
"""

import sys
import os
import tempfile
import shutil
import pytest

PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(PROMETHEUS_DIR, "tools")
if PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, PROMETHEUS_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from vector_memory import (
    TextVectorizer, VectorStore, SemanticMemory,
    _vec_to_bytes, _bytes_to_vec
)
import numpy as np


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="prometheus_vec_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ═══════════════════════════════════════════
#   TextVectorizer
# ═══════════════════════════════════════════

class TestTextVectorizer:
    def test_basic(self):
        v = TextVectorizer(dim=128)
        vec = v.vectorize("hello world")
        assert vec.shape == (128,)
        assert np.linalg.norm(vec) > 0.99

    def test_deterministic(self):
        v = TextVectorizer(dim=128)
        v1 = v.vectorize("test sentence")
        v2 = v.vectorize("test sentence")
        assert np.allclose(v1, v2)

    def test_semantic_similarity(self):
        v = TextVectorizer(dim=256)
        ml1 = v.vectorize("机器学习是人工智能的子领域")
        ml2 = v.vectorize("深度学习属于机器学习的范畴")
        weather = v.vectorize("今天天气很好适合出去玩")
        sim_related = v.similarity(ml1, ml2)
        sim_unrelated = v.similarity(ml1, weather)
        assert sim_related > sim_unrelated, \
            f"related({sim_related:.4f}) > unrelated({sim_unrelated:.4f})"

    def test_chinese(self):
        v = TextVectorizer(dim=128)
        vec = v.vectorize("普罗米修斯是希腊神话中的泰坦")
        assert np.linalg.norm(vec) > 0

    def test_mixed(self):
        v = TextVectorizer(dim=128)
        vec = v.vectorize("Prometheus 始祖种子包含 G001-G008 基因")
        assert np.linalg.norm(vec) > 0

    def test_bind(self):
        v = TextVectorizer(dim=128)
        a = v.vectorize("概念A")
        b = v.vectorize("概念B")
        bound = v.bind(a, b)
        assert bound.shape == a.shape
        assert np.linalg.norm(bound) > 0
        assert not np.allclose(bound, a)
        assert not np.allclose(bound, b)

    def test_superpose(self):
        v = TextVectorizer(dim=128)
        sup = v.superpose([v.vectorize("苹果"), v.vectorize("香蕉")])
        assert sup.shape == (128,)
        assert np.linalg.norm(sup) > 0

    def test_empty(self):
        v = TextVectorizer(dim=128)
        vec = v.vectorize("")
        assert np.linalg.norm(vec) < 0.01

    def test_performance(self):
        import time
        v = TextVectorizer(dim=512)
        texts = [f"这是第{i}段测试文本，用于性能验证" for i in range(100)]
        start = time.time()
        for t in texts:
            v.vectorize(t)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"100 texts in {elapsed:.3f}s"


# ═══════════════════════════════════════════
#   VectorStore
# ═══════════════════════════════════════════

class TestVectorStore:
    def test_add_and_get(self, tmp_dir):
        store = VectorStore(db_path=os.path.join(tmp_dir, "s.db"), dim=64)
        vec = np.random.randn(64).astype(np.float32)
        vec /= np.linalg.norm(vec)
        rid = store.add("测试内容", vec, layer="working", importance=0.8)
        assert rid > 0
        rec = store.get(rid)
        assert rec is not None
        assert rec["content"] == "测试内容"
        assert rec["layer"] == "working"
        assert rec["importance"] > 0.7

    def test_search(self, tmp_dir):
        store = VectorStore(db_path=os.path.join(tmp_dir, "s.db"), dim=128)
        v = TextVectorizer(dim=128)
        for text, layer, imp in [
            ("机器学习算法训练模型", "longterm", 0.9),
            ("神经网络反向传播", "episodic", 0.7),
            ("今天午饭吃米饭", "working", 0.3),
            ("深度学习卷积层", "longterm", 0.8),
            ("周末想去爬山", "working", 0.4),
        ]:
            store.add(text, v.vectorize(text), layer=layer, importance=imp)

        results = store.search(v.vectorize("人工智能模型训练"), limit=3)
        assert len(results) >= 1
        top = results[0]
        assert any(kw in top["content"] for kw in ["机器学习", "神经网络", "深度学习"])
        assert top["similarity"] > 0

    def test_layer_filter(self, tmp_dir):
        store = VectorStore(db_path=os.path.join(tmp_dir, "s.db"), dim=64)
        v = TextVectorizer(dim=64)
        vec = v.vectorize("test")
        store.add("working", vec, layer="working")
        store.add("longterm", vec, layer="longterm")
        assert len(store.search(vec, layer="working")) == 1
        assert len(store.search(vec, layer="longterm")) == 1

    def test_delete(self, tmp_dir):
        store = VectorStore(db_path=os.path.join(tmp_dir, "s.db"), dim=64)
        vec = np.zeros(64, dtype=np.float32); vec[0] = 1.0
        rid = store.add("x", vec)
        assert store.count() == 1
        store.delete(rid)
        assert store.count() == 0

    def test_stats(self, tmp_dir):
        store = VectorStore(db_path=os.path.join(tmp_dir, "s.db"), dim=64)
        vec = np.zeros(64, dtype=np.float32); vec[0] = 1.0
        store.add("a", vec, layer="working", importance=0.5)
        store.add("b", vec, layer="longterm", importance=0.9)
        s = store.stats()
        assert s["total_records"] == 2
        assert s["by_layer"]["working"] == 1
        assert s["by_layer"]["longterm"] == 1
        assert s["avg_importance"] > 0.5


# ═══════════════════════════════════════════
#   SemanticMemory
# ═══════════════════════════════════════════

class TestSemanticMemory:
    def test_remember_and_recall(self, tmp_dir):
        mem = SemanticMemory(db_path=os.path.join(tmp_dir, "s.db"), dim=128)
        mem.remember("TTG始祖种子包含8个标准基因", layer="longterm", importance=0.9,
                     tags=["ttg", "genes"])
        mem.remember("基因G001是元数据基因", layer="longterm", importance=0.8)
        mem.remember("今天天气不错适合出门", layer="working", importance=0.3)
        results = mem.recall("种子基因系统", limit=5)
        assert len(results) >= 1
        assert any("种子" in r["content"] or "基因" in r["content"]
                    for r in results[:2])

    def test_associate(self, tmp_dir):
        mem = SemanticMemory(db_path=os.path.join(tmp_dir, "s.db"), dim=128)
        mem.remember("苹果公司发布新产品", layer="episodic")
        mem.remember("iPhone是苹果的旗舰手机", layer="longterm")
        mem.remember("香蕉富含钾元素", layer="episodic")
        results = mem.associate("苹果手机", limit=3)
        assert len(results) >= 1
        assert any("苹果" in r["content"] for r in results)

    def test_bind_concepts(self, tmp_dir):
        mem = SemanticMemory(db_path=os.path.join(tmp_dir, "s.db"), dim=128)
        r = mem.bind_concepts("种子", "基因")
        assert r["operation"] == "bind"
        assert r["id"] > 0
        assert mem.store.count() == 1

    def test_superpose(self, tmp_dir):
        mem = SemanticMemory(db_path=os.path.join(tmp_dir, "s.db"), dim=128)
        r = mem.superpose_memories(["A", "B", "C"], weights=[0.5, 0.3, 0.2])
        assert r["operation"] == "superpose"
        assert r["sources"] == ["A", "B", "C"]

    def test_summary(self, tmp_dir):
        mem = SemanticMemory(db_path=os.path.join(tmp_dir, "s.db"), dim=64)
        for i in range(5):
            mem.remember(f"内容{i}", layer="working" if i < 3 else "longterm")
        s = mem.summary()
        assert s["total_memories"] == 5
        assert s["by_layer"]["working"] == 3
        assert s["by_layer"]["longterm"] == 2
        assert s["vector_dim"] == 64

    def test_cross_language(self, tmp_dir):
        """同语言语义相似度（验证核心检索能力）。"""
        mem = SemanticMemory(db_path=os.path.join(tmp_dir, "s.db"), dim=256)
        mem.remember("机器学习是人工智能的重要分支", layer="longterm", importance=0.9)
        mem.remember("周末计划去公园散步", layer="working", importance=0.3)
        # 同语言查询
        results = mem.recall("深度学习和AI模型训练", limit=3)
        assert len(results) >= 1
        assert "机器学习" in results[0]["content"]

    def test_batch(self, tmp_dir):
        import time
        mem = SemanticMemory(db_path=os.path.join(tmp_dir, "s.db"), dim=256)
        start = time.time()
        for i in range(50):
            mem.remember(f"第{i}条记忆涉及第{i}个主题", layer="episodic", importance=0.5)
        elapsed = time.time() - start
        assert mem.store.count() == 50
        assert elapsed < 5.0

    def test_memory_dump(self, tmp_dir):
        mem = SemanticMemory(db_path=os.path.join(tmp_dir, "s.db"), dim=64)
        for i in range(3):
            mem.remember(f"记忆{i}")
        dump = mem.memory_dump(limit=10)
        assert len(dump) == 3
        assert all("content" in d for d in dump)


# ═══════════════════════════════════════════
#   工具函数
# ═══════════════════════════════════════════

class TestUtils:
    def test_vec_bytes_roundtrip(self):
        vec = np.random.randn(512).astype(np.float32)
        assert np.allclose(vec, _bytes_to_vec(_vec_to_bytes(vec), dim=512))

    def test_estimate_tokens(self):
        assert VectorStore._estimate_tokens("Hello World") > 0
        assert VectorStore._estimate_tokens("测试中文") > 0
        assert VectorStore._estimate_tokens("Prometheus 基因系统") > 0
