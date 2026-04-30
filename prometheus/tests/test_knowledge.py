#!/usr/bin/env python3
"""
P2-7 知识管理测试
"""

import sys
import os
import tempfile
import shutil
import json
import pytest

PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(PROMETHEUS_DIR, "tools")
if PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, PROMETHEUS_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from knowledge import (
    WikiConnector, SeedIndex, LocalKnowledge, KnowledgeManager,
    WikiPage, SeedInfo
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="prometheus_knowledge_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def wiki_dir(tmp_dir):
    """创建测试 Wiki 目录结构。"""
    wiki = os.path.join(tmp_dir, "wiki")
    concepts = os.path.join(wiki, "concepts")
    projects = os.path.join(wiki, "projects")
    os.makedirs(concepts)
    os.makedirs(projects)
    
    # 写几个测试页面
    with open(os.path.join(concepts, "机器学习.md"), 'w') as f:
        f.write("""---
type: concept
maturity: reviewed
tags: [ai, ml, deep-learning]
aliases: [ML, machine learning]
date: 2026-04-01
---

# 机器学习

机器学习是人工智能的一个分支，通过数据训练模型来完成任务。

相关概念：[[深度学习]]、[[神经网络]]
""")

    with open(os.path.join(concepts, "深度学习.md"), 'w') as f:
        f.write("""---
type: concept
maturity: authoritative
tags: [ai, ml, deep-learning, neural-network]
date: 2026-04-01
---

# 深度学习

深度学习是机器学习的一个子领域，使用多层神经网络。

相关概念：[[机器学习]]、[[卷积神经网络]]
""")

    with open(os.path.join(projects, "hermes-upgrade.md"), 'w') as f:
        f.write("""---
type: project
maturity: draft
tags: [hermes, setup]
date: 2026-04-28
---

# Hermes 系统升级

完成了系统架构升级，包括 wiki-compiler 集成和每日复盘。
""")

    return wiki


@pytest.fixture
def seed_dir(tmp_dir):
    """创建测试种子目录。"""
    seeds = os.path.join(tmp_dir, "seeds")
    os.makedirs(seeds)
    
    with open(os.path.join(seeds, "teach-to-grow.ttg"), 'w') as f:
        f.write("""---
name: teach-to-grow
version: 1.0.0
description: TTG始祖种子，包含完整的自进化系统
---

# Teach-To-Grow 始祖种子

## 基因列表

G001 — 元数据基因（Meta Gene）
G002 — 语义字典基因（Dictionary Gene）
G003 — 族谱基因（Genealogy Gene）
G004 — 压缩编码基因（Codec Gene）
G005 — 进化控制基因（Evolution Gene）
G006 — 种子园丁基因（SeedGardener Gene）
G007 — 休眠守卫基因（DormancyGuard Gene）
G008 — 叙事基因（Narrative Gene）

## 语义字典

- "种子" → 独立自给自足的生命体
- "基因" → 种子的最小功能单元
- "族谱" → 种子的进化历史记录
- "压缩编码" → 叙事的紧凑存储方式
""")

    with open(os.path.join(seeds, "meta-seed.ttg"), 'w') as f:
        f.write("""---
name: meta-seed
version: 0.1.0
description: 元种子，管理其他种子的种子
---

# 元种子

G001 — 调度基因（Dispatcher Gene）
G009 — 监控基因（Monitor Gene）

- "调度" → 种子的执行管理
- "监控" → 种子状态的实时追踪
""")

    return seeds


# ═══════════════════════════════════════════
#   WikiConnector
# ═══════════════════════════════════════════

class TestWikiConnector:
    def test_connect(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        assert wc.is_connected
        assert wc.page_count == 3

    def test_connect_invalid(self, tmp_dir):
        wc = WikiConnector(wiki_paths=[os.path.join(tmp_dir, "nonexistent")])
        assert not wc.is_connected
        assert wc.page_count == 0

    def test_search(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        results = wc.search("机器学习")
        assert len(results) >= 1
        assert any("机器学习" in r["title"] for r in results)

    def test_search_by_type(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        results = wc.search("ai", page_type="concept")
        assert all(r["type"] == "concept" for r in results)

    def test_search_by_maturity(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        results = wc.search("learning", min_maturity="authoritative")
        # 只有深度学习是 authoritative
        assert all(r["maturity"] == "authoritative" for r in results)

    def test_get_page(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        path = wc.find_page_by_title("机器学习")
        assert path is not None
        page = wc.get_page(path)
        assert page is not None
        assert page.page_type == "concept"
        assert "ai" in page.tags

    def test_find_by_alias(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        path = wc.find_page_by_title("ML")
        assert path is not None

    def test_get_pages_by_tag(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        pages = wc.get_pages_by_tag("ai")
        assert len(pages) == 2

    def test_list_pages(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        all_pages = wc.list_pages()
        assert len(all_pages) == 3
        concepts = wc.list_pages(page_type="concept")
        assert len(concepts) == 2

    def test_stats(self, wiki_dir):
        wc = WikiConnector(wiki_paths=[wiki_dir])
        s = wc.stats()
        assert s["connected"]
        assert s["total_pages"] == 3
        assert "concept" in s["by_type"]

    def test_multiple_wiki_dirs(self, wiki_dir, tmp_dir):
        """测试多 Wiki 目录。"""
        wiki2 = os.path.join(tmp_dir, "wiki2")
        os.makedirs(wiki2)
        with open(os.path.join(wiki2, "extra.md"), 'w') as f:
            f.write("# Extra\nSome extra content.\n")
        
        wc = WikiConnector(wiki_paths=[wiki_dir, wiki2])
        assert wc.page_count == 4  # 3 from wiki_dir + 1 from wiki2


# ═══════════════════════════════════════════
#   SeedIndex
# ═══════════════════════════════════════════

class TestSeedIndex:
    def test_build_index(self, seed_dir):
        si = SeedIndex(seed_paths=[seed_dir])
        s = si.stats()
        assert s["total_seeds"] == 2
        assert s["total_genes"] >= 9  # G001-G008 + G009

    def test_search(self, seed_dir):
        si = SeedIndex(seed_paths=[seed_dir])
        results = si.search("始祖种子")
        assert len(results) >= 1
        assert "teach-to-grow" in results[0]["name"]

    def test_get_by_gene(self, seed_dir):
        si = SeedIndex(seed_paths=[seed_dir])
        seeds = si.get_by_gene("G001")
        assert len(seeds) == 2  # 两个种子都有 G001

    def test_get_by_gene_unique(self, seed_dir):
        si = SeedIndex(seed_paths=[seed_dir])
        seeds = si.get_by_gene("G008")
        assert len(seeds) == 1
        assert seeds[0].name == "teach-to-grow"

    def test_get_by_concept(self, seed_dir):
        si = SeedIndex(seed_paths=[seed_dir])
        seeds = si.get_by_concept("种子")
        assert len(seeds) >= 1

    def test_list_seeds(self, seed_dir):
        si = SeedIndex(seed_paths=[seed_dir])
        seeds = si.list_seeds()
        assert len(seeds) == 2
        names = [s["name"] for s in seeds]
        assert "teach-to-grow" in names
        assert "meta-seed" in names

    def test_gene_info(self, seed_dir):
        si = SeedIndex(seed_paths=[seed_dir])
        results = si.search("元数据基因")
        assert len(results) >= 1


# ═══════════════════════════════════════════
#   LocalKnowledge
# ═══════════════════════════════════════════

class TestLocalKnowledge:
    def test_add_and_search(self, tmp_dir):
        import knowledge as km_mod
        old_dir = km_mod.LOCAL_KB_DIR
        old_idx = km_mod.LocalKnowledge.INDEX_FILE
        km_mod.LOCAL_KB_DIR = os.path.join(tmp_dir, "local_kb")
        km_mod.LocalKnowledge.INDEX_FILE = os.path.join(km_mod.LOCAL_KB_DIR, "index.json")
        
        try:
            lk = LocalKnowledge()
            entry_id = lk.add("测试概念", "这是一个测试概念的描述", tags=["test", "demo"])
            assert len(entry_id) > 0
            
            results = lk.search("测试概念")
            assert len(results) >= 1
            assert results[0]["title"] == "测试概念"
            
            assert lk.count() == 1
        finally:
            km_mod.LOCAL_KB_DIR = old_dir
            km_mod.LocalKnowledge.INDEX_FILE = old_idx

    def test_search_by_content(self, tmp_dir):
        import knowledge as km_mod
        old_dir = km_mod.LOCAL_KB_DIR
        old_idx = km_mod.LocalKnowledge.INDEX_FILE
        km_mod.LOCAL_KB_DIR = os.path.join(tmp_dir, "local_kb2")
        km_mod.LocalKnowledge.INDEX_FILE = os.path.join(km_mod.LOCAL_KB_DIR, "index.json")
        
        try:
            lk = LocalKnowledge()
            lk.add("笔记A", "今天学习了机器学习的基础知识", tags=["学习"])
            lk.add("笔记B", "周末去爬山的计划", tags=["生活"])
            
            results = lk.search("机器学习")
            assert len(results) >= 1
        finally:
            km_mod.LOCAL_KB_DIR = old_dir
            km_mod.LocalKnowledge.INDEX_FILE = old_idx


# ═══════════════════════════════════════════
#   KnowledgeManager
# ═══════════════════════════════════════════

class TestKnowledgeManager:
    def test_wiki_mode(self, wiki_dir, seed_dir):
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir])
        s = km.stats()
        assert s["wiki_connected"]
        assert s["seeds"] == 2

    def test_local_mode(self, tmp_dir, seed_dir):
        """Wiki 不可用时自动降级到本地。"""
        km = KnowledgeManager(
            wiki_paths=[os.path.join(tmp_dir, "nonexistent")],
            seed_paths=[seed_dir]
        )
        s = km.stats()
        assert not s["wiki_connected"]
        assert s["mode"] == "local"

    def test_force_local(self, wiki_dir, seed_dir):
        """强制本地模式。"""
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir],
                             force_local=True)
        s = km.stats()
        assert s["mode"] == "local"

    def test_search_unified(self, wiki_dir, seed_dir):
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir])
        results = km.search("机器学习")
        # 应该同时从 Wiki 和种子中找到结果
        assert results["total"] >= 1

    def test_search_seeds_only(self, wiki_dir, seed_dir):
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir])
        results = km.search("G001", source="seeds")
        assert len(results["seeds"]) >= 1
        assert len(results["wiki"]) == 0

    def test_add_knowledge(self, wiki_dir, seed_dir):
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir])
        entry_id = km.add_knowledge("新发现", "这是一个新发现的知识", tags=["discovery"])
        assert len(entry_id) > 0

    def test_find_seeds_by_gene(self, wiki_dir, seed_dir):
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir])
        seeds = km.find_seeds_by_gene("G005")
        assert len(seeds) == 1
        assert seeds[0].name == "teach-to-grow"

    def test_summary(self, wiki_dir, seed_dir):
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir])
        summary = km.summary()
        assert "Wiki" in summary
        assert "种子" in summary

    def test_list_wiki_pages(self, wiki_dir, seed_dir):
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir])
        pages = km.list_wiki_pages()
        assert len(pages) == 3

    def test_stats(self, wiki_dir, seed_dir):
        km = KnowledgeManager(wiki_paths=[wiki_dir], seed_paths=[seed_dir])
        s = km.stats()
        assert s["wiki_connected"]
        assert s["wiki_pages"] == 3
        assert s["seeds"] == 2
        assert s["seed_genes"] >= 9
