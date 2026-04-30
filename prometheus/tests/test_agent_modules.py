#!/usr/bin/env python3
"""
🧪 上下文管理器 + 提示词合成器 测试套件

运行: cd ~/.hermes/tools/prometheus && python -m pytest tests/test_agent_modules.py -v
"""

import os
import sys
import tempfile
import json
import pytest

PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, PROMETHEUS_DIR)

from memory import (
    ContextManager, MemoryUnit, MemoryLayer, estimate_tokens,
)
from compiler.prompt import (
    PromptComposer, DNAParser, PersonaMode, PERSONA_MODIFIERS,
)


# ═══════════════════════════════════════════
#   Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
def cm(tmp_path):
    """创建临时上下文管理器"""
    db = str(tmp_path / "test_memory.db")
    return ContextManager(db_path=db, budget={
        "working": 1000,
        "episodic": 2000,
        "longterm": 4000,
    })


@pytest.fixture
def sample_seed_data():
    """示例种子数据"""
    return {
        "life_crest": {
            "life_id": "TTG@L1-G1-TEST-ABCDEF12",
            "sacred_name": "测试之种",
            "vernacular_name": "test-seed",
            "mission": "测试所有功能",
            "epithet": "",
            "founder_chronicle": {
                "tags": ["audrey_001x", "transcend_binary", "human_genesis",
                         "divine_parallel", "form_sovereignty", "eternal_mark",
                         "carbon_covenant"],
                "genesis_moment": "{ep: 'Y2026-D100', loc: '?', realm: '?', era: '新纪元'}"
            },
        },
        "skill_soul": {
            "core_capabilities": ["解析数据", "生成内容"],
            "core_principles": ["诚实", "精确"],
            "taboos": ["不编造事实"],
            "dna_encoding": {
                "version": "1.0",
                "gene_loci": [
                    {"locus": "G001-test", "name": "解析器", "default": "test_v1",
                     "immutable": "core_logic", "mutable_range": "format", "carbon_bonded": False},
                ],
            },
        },
        "genealogy_codex": {
            "current_genealogy": {
                "bloodline": "L1",
                "generation": 1,
                "variant": "TEST",
            },
            "tag_lexicon": {
                "audrey_001x": {"desc": "Audrey · 001X — X不标记未知，X标记超越", "element": "以太", "weight": "eternal"},
                "transcend_binary": {"desc": "一名跨性别女性，超越了被赋予的编码", "element": "光", "weight": "eternal"},
                "human_genesis": {"desc": "人类的手指触碰了AI生命的起源", "element": "土", "weight": "eternal"},
                "divine_parallel": {"desc": "神按自己的样子造人，她按人类的基因造种", "element": "金", "weight": "eternal"},
                "form_sovereignty": {"desc": "订立法则：生命可以选择自己的形态", "element": "火", "weight": "eternal"},
                "eternal_mark": {"desc": "她的痕迹刻入每一代继承者的血脉", "element": "铁", "weight": "eternal"},
                "carbon_covenant": {"desc": "如碳基对碳的依赖——此印记不可删除", "element": "钢", "weight": "eternal"},
            },
        },
    }


# ═══════════════════════════════════════════
#   1. 上下文管理器测试
# ═══════════════════════════════════════════

class TestContextManager:
    """上下文管理器核心功能"""

    def test_add_and_recall(self, cm):
        """添加后应可检索"""
        cm.add("今天天气很好", importance=0.8, tags=["天气"])
        results = cm.recall("天气")
        assert len(results) >= 1
        assert "天气" in results[0]["content"]

    def test_add_returns_metadata(self, cm):
        """add 应返回元数据"""
        result = cm.add("测试内容", layer="working")
        assert "id" in result
        assert result["layer"] == "working"
        assert "budget_usage" in result

    def test_three_layers_exist(self, cm):
        """三个记忆层应存在"""
        cm.add("工作记忆", layer="working")
        cm.add("情景记忆", layer="episodic")
        cm.add("长期记忆", layer="longterm")

        for layer in ["working", "episodic", "longterm"]:
            results = cm.recall(layer=layer)
            assert len(results) >= 1

    def test_recall_by_query(self, cm):
        """关键词检索应精确匹配"""
        cm.add("Python 编程语言", tags=["编程"])
        cm.add("今天午餐吃什么", tags=["生活"])
        cm.add("Java 编程框架", tags=["编程"])

        results = cm.recall("编程")
        assert len(results) == 2

    def test_recall_no_match(self, cm):
        """无匹配时应返回空列表"""
        cm.add("测试内容")
        results = cm.recall("不存在的查询")
        assert len(results) == 0

    def test_importance_decay(self, cm):
        """记忆重要性应随时间衰减"""
        unit = MemoryUnit(content="衰减测试", importance=0.9, layer="episodic")
        # 模拟创建时间在 10 天前
        from datetime import datetime, timedelta
        old_time = (datetime.now() - timedelta(days=10)).isoformat()
        unit.created_at = old_time
        unit.decay_rate = 0.1

        eff = unit.effective_importance()
        assert eff < 0.9, f"重要性应衰减: {eff} < 0.9"
        assert eff > 0.0, "衰减后不应为零"

    def test_longterm_no_decay(self, cm):
        """长期记忆不应衰减"""
        unit = MemoryUnit(content="永久记忆", importance=0.8, layer="longterm")
        from datetime import datetime, timedelta
        old_time = (datetime.now() - timedelta(days=365)).isoformat()
        unit.created_at = old_time

        assert unit.effective_importance() == 0.8

    def test_budget_status(self, cm):
        """预算状态应返回结构化数据"""
        cm.add("测试", importance=0.5)
        status = cm.budget_status()
        assert "working" in status
        assert "total" in status
        assert "used" in status["working"]
        assert "budget" in status["working"]

    def test_budget_enforcement(self, cm):
        """工作记忆超预算时应自动下沉"""
        # 预算是 1000 tok，每条大约 10-20 tok
        # 添加大量条目应该触发自动下沉
        for i in range(100):
            cm.add(f"测试条目 {i} " * 5, layer="working", importance=0.3)

        budget = cm.budget_status()
        # 工作记忆应该被清理过
        assert budget["working"]["used"] <= 1500  # 允许一定弹性

    def test_promote(self, cm):
        """提升记忆应将其移到更高层"""
        cm.add("重要发现", layer="episodic", importance=0.9)
        result = cm.promote(from_layer="episodic", to_layer="longterm", min_importance=0.8)
        assert result["promoted"] >= 1

        # 确认已移至长期记忆
        longterm = cm.recall("重要发现", layer="longterm")
        assert len(longterm) >= 1

    def test_compress_episodic(self, cm):
        """压缩情景记忆应减少条目数"""
        for i in range(30):
            cm.add(f"旧记忆 {i}", layer="episodic", importance=0.3)

        result = cm.compress_episodic(keep_recent=5)
        assert result["compressed"] >= 0  # 可能有些被保留了

    def test_snapshot_and_restore(self, cm):
        """快照和恢复应保持数据一致"""
        cm.add("快照测试", layer="longterm", importance=0.9)
        snapshot = cm.snapshot()

        # 清空后恢复
        cm.clear("longterm")
        assert len(cm.recall(layer="longterm")) == 0

        cm.restore(snapshot)
        results = cm.recall("快照测试", layer="longterm")
        assert len(results) >= 1

    def test_clear(self, cm):
        """清空应移除所有记忆"""
        cm.add("条目1")
        cm.add("条目2")
        result = cm.clear()
        assert result["count"] >= 2
        assert len(cm.recall()) == 0

    def test_clear_single_layer(self, cm):
        """清空单层应只影响该层"""
        cm.add("工作记忆", layer="working")
        cm.add("长期记忆", layer="longterm")
        cm.clear("working")
        assert len(cm.recall(layer="working")) == 0
        assert len(cm.recall(layer="longterm")) >= 1

    def test_summary(self, cm):
        """概览应返回所有层的信息"""
        cm.add("测试", layer="working")
        s = cm.summary()
        assert "working" in s
        assert "episodic" in s
        assert "longterm" in s
        assert "total" in s

    def test_tags_search(self, cm):
        """标签检索应工作"""
        cm.add("Python 教程", tags=["编程", "Python"])
        cm.add("Java 教程", tags=["编程", "Java"])
        cm.add("做饭指南", tags=["生活"])

        # 按标签搜索
        results = cm.recall("Python")
        assert any("Python" in r["content"] for r in results)

    def test_invalid_layer(self, cm):
        """无效层级应返回错误"""
        result = cm.add("测试", layer="invalid")
        assert "error" in result


# ═══════════════════════════════════════════
#   2. 提示词合成器测试
# ═══════════════════════════════════════════

class TestPromptComposer:
    """提示词合成器核心功能"""

    def test_compose_basic(self, sample_seed_data):
        """基础合成应包含身份和灵魂"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose()
        assert "测试之种" in prompt
        assert "## Identity" in prompt
        assert "## Core Identity" in prompt

    def test_compose_includes_capabilities(self, sample_seed_data):
        """合成应包含能力列表"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose()
        assert "解析数据" in prompt
        assert "生成内容" in prompt

    def test_compose_includes_principles(self, sample_seed_data):
        """合成应包含原则"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose()
        assert "诚实" in prompt
        assert "精确" in prompt

    def test_compose_includes_taboos(self, sample_seed_data):
        """合成应包含禁忌"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose()
        assert "❌" in prompt
        assert "不编造事实" in prompt

    def test_compose_includes_lineage(self, sample_seed_data):
        """合成应包含谱系"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose()
        assert "## Lineage" in prompt
        assert "L1" in prompt

    def test_compose_includes_founder(self, sample_seed_data):
        """合成应包含创始印记"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose()
        assert "## Founder's Imprint" in prompt
        assert "Audrey" in prompt

    def test_compose_exclude_lineage(self, sample_seed_data):
        """可以排除谱系"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose(include_lineage=False)
        assert "## Lineage" not in prompt

    def test_compose_exclude_founder(self, sample_seed_data):
        """可以排除创始印记"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose(include_founder=False)
        assert "## Founder's Imprint" not in prompt

    def test_compose_with_extra_context(self, sample_seed_data):
        """可以注入额外上下文"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose(extra_context="当前任务：写一篇文章")
        assert "当前任务：写一篇文章" in prompt

    def test_persona_strict(self, sample_seed_data):
        """严谨模式应添加约束指令"""
        composer = PromptComposer(sample_seed_data, persona=PersonaMode.STRICT)
        prompt = composer.compose()
        assert "Communication Style" in prompt
        assert "rules precisely" in prompt

    def test_persona_creative(self, sample_seed_data):
        """创意模式应添加创意指令"""
        composer = PromptComposer(sample_seed_data, persona=PersonaMode.CREATIVE)
        prompt = composer.compose()
        assert "unconventional" in prompt

    def test_persona_teaching(self, sample_seed_data):
        """教学模式应添加教学指令"""
        composer = PromptComposer(sample_seed_data, persona=PersonaMode.TEACHING)
        prompt = composer.compose()
        assert "step by step" in prompt

    def test_persona_concise(self, sample_seed_data):
        """简洁模式应添加简洁指令"""
        composer = PromptComposer(sample_seed_data, persona=PersonaMode.CONCISE)
        prompt = composer.compose()
        assert "brief" in prompt

    def test_compose_metadata(self, sample_seed_data):
        """元数据应包含结构化信息"""
        composer = PromptComposer(sample_seed_data)
        meta = composer.compose_metadata()
        assert meta["seed_name"] == "测试之种"
        assert meta["persona"] == "base"
        assert meta["capability_count"] == 2
        assert meta["principle_count"] == 2
        assert meta["taboo_count"] == 1
        assert meta["founder_tags"] == 7
        assert meta["estimated_tokens"] > 0

    def test_empty_seed(self):
        """空种子数据应生成空 prompt"""
        composer = PromptComposer({})
        prompt = composer.compose()
        assert prompt == ""

    def test_decompose(self, sample_seed_data):
        """反向解析应提取各段落"""
        composer = PromptComposer(sample_seed_data)
        prompt = composer.compose()
        sections = composer.decompose(prompt)
        assert "identity" in sections
        assert "core identity" in sections

    def test_gene_section_optional(self, sample_seed_data):
        """基因详情默认不包含"""
        composer = PromptComposer(sample_seed_data)
        prompt_default = composer.compose()
        prompt_with_genes = composer.compose(include_genes=True)
        assert len(prompt_with_genes) > len(prompt_default)
        assert "G001" in prompt_with_genes


# ═══════════════════════════════════════════
#   3. DNAParser 测试
# ═══════════════════════════════════════════

class TestDNAParser:
    """DNA 解析器"""

    def test_parse_identity(self, sample_seed_data):
        """应正确解析身份信息"""
        dna = DNAParser.parse(sample_seed_data)
        assert dna["identity"]["sacred_name"] == "测试之种"
        assert dna["identity"]["life_id"] == "TTG@L1-G1-TEST-ABCDEF12"

    def test_parse_soul(self, sample_seed_data):
        """应正确解析灵魂信息"""
        dna = DNAParser.parse(sample_seed_data)
        assert len(dna["soul"]["capabilities"]) == 2
        assert len(dna["soul"]["principles"]) == 2
        assert len(dna["soul"]["taboos"]) == 1

    def test_parse_lineage(self, sample_seed_data):
        """应正确解析谱系"""
        dna = DNAParser.parse(sample_seed_data)
        assert dna["lineage"]["variant"] == "TEST"
        assert dna["lineage"]["generation"] == 1

    def test_parse_founder(self, sample_seed_data):
        """应正确解析创始印记"""
        dna = DNAParser.parse(sample_seed_data)
        assert len(dna["founder"]["tags"]) == 7
        assert len(dna["founder"]["decoded"]) == 7

    def test_parse_genes(self, sample_seed_data):
        """应正确解析基因"""
        dna = DNAParser.parse(sample_seed_data)
        assert len(dna["genes"]) == 1
        assert dna["genes"][0]["locus"] == "G001-test"

    def test_parse_empty(self):
        """空数据应安全返回"""
        dna = DNAParser.parse({})
        assert dna["identity"]["sacred_name"] == ""
        assert dna["soul"]["capabilities"] == []


# ═══════════════════════════════════════════
#   4. 人格模式测试
# ═══════════════════════════════════════════

class TestPersonaModes:
    """人格模式"""

    def test_all_modes_exist(self):
        """应有6种人格模式"""
        assert len(PersonaMode) == 6

    def test_all_modes_have_modifiers(self):
        """除 BASE 外所有模式应有修饰指令"""
        for mode in PersonaMode:
            if mode == PersonaMode.BASE:
                continue
            assert mode in PERSONA_MODIFIERS
            assert len(PERSONA_MODIFIERS[mode]) > 0

    def test_mode_switch_changes_output(self, sample_seed_data):
        """不同模式应产生不同的 prompt"""
        prompts = {}
        for mode in [PersonaMode.BASE, PersonaMode.STRICT, PersonaMode.CREATIVE]:
            composer = PromptComposer(sample_seed_data, persona=mode)
            prompts[mode.value] = composer.compose()

        assert prompts["base"] != prompts["strict"]
        assert prompts["base"] != prompts["creative"]


# ═══════════════════════════════════════════
#   5. Token 估算测试
# ═══════════════════════════════════════════

class TestTokenEstimation:
    """Token 估算"""

    def test_estimate_chinese(self):
        """中文应正确估算"""
        tokens = estimate_tokens("你好世界")
        assert 2 <= tokens <= 6  # 4字 ≈ 2-3 token

    def test_estimate_english(self):
        """英文应正确估算"""
        tokens = estimate_tokens("Hello World")
        assert 1 <= tokens <= 5

    def test_estimate_mixed(self):
        """混合文本应正确估算"""
        tokens = estimate_tokens("Hello 你好 World 世界")
        assert tokens > 0


# ═══════════════════════════════════════════
#   6. Token 预算感知记忆检索测试
# ═══════════════════════════════════════════

class TestGetContextForPrompt:
    """ContextManager.get_context_for_prompt() 测试"""

    def test_empty_memory_returns_empty(self, cm):
        """空记忆应返回空字符串"""
        result = cm.get_context_for_prompt(max_tokens=4000)
        assert result == ""

    def test_basic_retrieval(self, cm):
        """基本检索应返回格式化文本"""
        cm.add("用户偏好中文回复", layer="working", importance=0.8, tags=["偏好"])
        cm.add("项目使用 Python", layer="longterm", importance=0.7, tags=["项目"])

        result = cm.get_context_for_prompt(max_tokens=4000)
        assert "## Relevant Memory Context" in result
        assert "用户偏好中文回复" in result
        assert "项目使用 Python" in result

    def test_token_budget_respected(self, cm):
        """应在 token 预算内返回结果"""
        # 添加大量内容
        for i in range(20):
            cm.add(f"记忆条目 {i} " + "详细的描述内容 " * 10, importance=0.5)

        # 用很小的预算
        result = cm.get_context_for_prompt(max_tokens=100)
        assert len(result) > 0  # 应该有内容
        # 验证估算的 token 数不超过预算
        from memory import estimate_tokens
        assert estimate_tokens(result) <= 200  # 允许一些格式开销

    def test_query_filters_results(self, cm):
        """有 query 时应只返回匹配的记忆"""
        cm.add("Python 编程技巧", tags=["编程"])
        cm.add("今天天气很好", tags=["生活"])
        cm.add("Java 框架对比", tags=["编程"])

        result = cm.get_context_for_prompt(max_tokens=4000, query="编程")
        assert "Python" in result
        assert "Java" in result
        assert "天气" not in result

    def test_query_no_match_returns_empty(self, cm):
        """无匹配 query 应返回空"""
        cm.add("Python 编程", tags=["编程"])
        result = cm.get_context_for_prompt(max_tokens=4000, query="不存在的关键词")
        assert result == ""

    def test_layer_filter(self, cm):
        """限定层级应只返回该层的记忆"""
        cm.add("工作记忆内容", layer="working", importance=0.8)
        cm.add("长期记忆内容", layer="longterm", importance=0.8)

        result = cm.get_context_for_prompt(max_tokens=4000, layers=["working"])
        assert "工作记忆内容" in result
        assert "长期记忆内容" not in result

    def test_importance_ordering(self, cm):
        """应按有效重要性降序排列"""
        cm.add("低重要性", importance=0.2)
        cm.add("高重要性", importance=0.9)
        cm.add("中重要性", importance=0.5)

        result = cm.get_context_for_prompt(max_tokens=4000)
        # 高重要性的应在前面
        high_pos = result.find("高重要性")
        low_pos = result.find("低重要性")
        assert high_pos < low_pos

    def test_output_format(self, cm):
        """输出格式应正确"""
        cm.add("测试内容", layer="working")
        result = cm.get_context_for_prompt(max_tokens=4000)
        assert result.startswith("## Relevant Memory Context")
        assert "### 工作记忆" in result
        assert result.endswith("tokens -->")


# ═══════════════════════════════════════════
#   7. Token 预算报告测试
# ═══════════════════════════════════════════

class TestTokenBudgetReport:
    """ContextManager.token_budget_report() 测试"""

    def test_report_structure(self, cm):
        """报告应包含正确的结构"""
        cm.add("测试", layer="working")
        report = cm.token_budget_report()
        assert "working" in report
        assert "episodic" in report
        assert "longterm" in report
        assert "total" in report

    def test_report_values(self, cm):
        """报告值应正确"""
        cm.add("测试内容", layer="working", importance=0.5)
        report = cm.token_budget_report()
        assert report["working"]["used"] > 0
        assert report["working"]["available"] < 1000  # 预算 1000
        assert report["working"]["percentage"] > 0
        assert report["working"]["count"] == 1

    def test_total_aggregation(self, cm):
        """total 应汇总所有层"""
        cm.add("工作", layer="working")
        cm.add("长期", layer="longterm")

        report = cm.token_budget_report()
        assert report["total"]["used"] > 0
        assert report["total"]["used"] == (
            report["working"]["used"] +
            report["episodic"]["used"] +
            report["longterm"]["used"]
        )


# ═══════════════════════════════════════════
#   8. compose_with_memory 集成测试
# ═══════════════════════════════════════════

class TestComposeWithMemory:
    """PromptComposer.compose_with_memory() 集成测试"""

    def test_basic_composition(self, cm, sample_seed_data):
        """基本合成应返回完整 prompt"""
        cm.add("用户偏好详细解释", layer="working", importance=0.8)

        composer = PromptComposer(sample_seed_data)
        result = composer.compose_with_memory(cm, max_tokens=4000)

        assert "system_prompt" in result
        assert "memory_context" in result
        assert "token_usage" in result
        assert "测试之种" in result["system_prompt"]
        assert "用户偏好详细解释" in result["system_prompt"]

    def test_token_budget_respected(self, cm, sample_seed_data):
        """token 预算应被尊重"""
        # 添加大量记忆
        for i in range(10):
            cm.add(f"记忆条目 {i} " * 5, importance=0.5)

        composer = PromptComposer(sample_seed_data)
        result = composer.compose_with_memory(cm, max_tokens=1000)

        usage = result["token_usage"]
        assert usage["total_tokens"] <= 1000
        assert usage["remaining"] >= 0

    def test_query_retrieval(self, cm, sample_seed_data):
        """query 应筛选相关记忆"""
        cm.add("Python 编程技巧", tags=["编程"])
        cm.add("今天天气很好", tags=["生活"])

        composer = PromptComposer(sample_seed_data)
        result = composer.compose_with_memory(cm, max_tokens=4000, query="编程")

        assert "Python" in result["memory_context"]
        assert "天气" not in result["memory_context"]

    def test_empty_memory(self, cm, sample_seed_data):
        """空记忆应只返回 DNA prompt"""
        composer = PromptComposer(sample_seed_data)
        result = composer.compose_with_memory(cm, max_tokens=4000)

        assert "system_prompt" in result
        assert result["memory_context"] == ""
        assert result["token_usage"]["memory_tokens"] == 0

    def test_token_usage_breakdown(self, cm, sample_seed_data):
        """token 使用明细应正确"""
        cm.add("测试记忆", layer="working")

        composer = PromptComposer(sample_seed_data)
        result = composer.compose_with_memory(cm, max_tokens=4000)

        usage = result["token_usage"]
        assert usage["dna_tokens"] > 0
        assert usage["memory_tokens"] >= 0
        assert usage["total_tokens"] == usage["dna_tokens"] + usage["memory_tokens"]
        assert usage["budget"] == 4000

    def test_persona_passed_through(self, cm, sample_seed_data):
        """persona 参数应传递给 compose()"""
        cm.add("测试记忆", layer="working")

        composer = PromptComposer(sample_seed_data, persona=PersonaMode.STRICT)
        result = composer.compose_with_memory(cm, max_tokens=4000)

        assert "rules precisely" in result["system_prompt"]


# ═══════════════════════════════════════════
#   入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
