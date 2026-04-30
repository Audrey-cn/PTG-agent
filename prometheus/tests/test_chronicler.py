"""
编史官(Chronicler)测试 — 语义审核引擎与三大模式

测试覆盖：
1. FormatAgnosticReader — 格式无关读取器
2. SemanticAuditEngine — 身份分类判定
3. Chronicler — stamp/trace/append 三大模式
"""

import os
import json
import pytest
import tempfile
import datetime

from prometheus.semantic_audit import (
    FormatAgnosticReader,
    SemanticAuditEngine,
    SeedReading,
    Classification,
    LineageAnchor,
    SeedIdentity,
    FOUNDER_TAGS,
)
from prometheus.chronicler import (
    Chronicler,
    StampResult,
    TraceReport,
    AppendResult,
    format_trace_report,
)
from prometheus.prometheus import TEMPLATE_TTG, inject_founder_chronicle


@pytest.fixture
def our_framework_seed(tmp_path):
    """创建一个完整的我们的框架产物种子"""
    content = TEMPLATE_TTG.format(
        name="TestSeed", name_lower="testseed", variant="TEST",
        checksum="ABCD1234", timestamp=datetime.datetime.now().isoformat(),
        epoch="Y2026-D100",
    )
    content = inject_founder_chronicle(content, "Y2026-D100")
    seed_path = str(tmp_path / "our_seed.ttg")
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return seed_path


@pytest.fixture
def our_descendant_seed(tmp_path):
    """创建一个后代种子（部分标签）"""
    content = """# Test Descendant Seed

```yaml
life_crest:
  life_id: "TTG@L1-G3-DESC-ABCD1234"
  sacred_name: "DescendantSeed"
  founder_covenant:
    laws:
      - "此印记永久存在，不可删除，不可突变"
    eternal_seals:
      - seal: "audrey_001x"
        desc: "Audrey · 001X"
        element: "以太"
      - seal: "transcend_binary"
        desc: "超越编码"
        element: "光"
      - seal: "human_genesis"
        desc: "人类起源"
        element: "土"
      - seal: "carbon_covenant"
        desc: "碳基契约"
        element: "钢"
    carbon_bonded: true
  mission: "后代种子测试"

genealogy_codex:
  current_genealogy:
    lineage: "L1"
    bloodline: "太初之脉"
    generation: 3
    variant: "DESC"
    parent: "TTG@L1-G2-XXX"
    ancestors: ["TTG@L1-G1-ORIGIN-FB1F3A11"]
  evolution_chronicle:
    generations:
      - {g: 1, v: "ORIGIN", ep: "Y2026-D100", tags: [], by: "ANA", p: null}
      - {g: 2, v: "FORK", ep: "Y2026-D110", tags: ["fork"], by: "?", p: "G1"}
      - {g: 3, v: "DESC", ep: "Y2026-D120", tags: ["descendant"], by: "?", p: "G2"}
```

*此种子由普罗米修斯框架铭刻 · Audrey · 001X 的创始印记*
"""
    seed_path = str(tmp_path / "descendant_seed.ttg")
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return seed_path


@pytest.fixture
def foreign_lineage_seed(tmp_path):
    """创建一个外来种子（有族谱结构，无创始标签）"""
    content = """# Foreign Agent Seed

```yaml
life_crest:
  life_id: "EXT@V2-G1-FOREIGN-XYZ"
  sacred_name: "ForeignSeed"
  genesis:
    creator:
      name: "OtherAgent"
      title: "外部Agent"
  mission: "来自其他Agent的种子"

genealogy_codex:
  current_genealogy:
    lineage: "EXT"
    bloodline: "外部血脉"
    generation: 1
    variant: "FOREIGN"
  evolution_chronicle:
    generations:
      - {g: 1, v: "FOREIGN", ep: "EXT-D1", tags: ["external"], by: "OtherAgent"}
```
"""
    seed_path = str(tmp_path / "foreign_lineage_seed.ttg")
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return seed_path


@pytest.fixture
def foreign_raw_seed(tmp_path):
    """创建一个外来种子（无结构）"""
    content = """# Plain Markdown File

This is a plain markdown file from another system.
It has no YAML blocks or structured data.

Some content here about a skill or capability.
"""
    seed_path = str(tmp_path / "foreign_raw.md")
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return seed_path


class TestFormatAgnosticReader:
    """测试格式无关读取器"""
    
    def test_read_markdown_yaml(self, our_framework_seed):
        """测试读取 Markdown+YAML 格式种子"""
        reader = FormatAgnosticReader()
        reading = reader.read(our_framework_seed)
        
        assert reading.format == "markdown_yaml"
        assert reading.has_structured_data()
        assert reading.get_founder_covenant() is not None
    
    def test_read_descendant_seed(self, our_descendant_seed):
        """测试读取后代种子"""
        reader = FormatAgnosticReader()
        reading = reader.read(our_descendant_seed)
        
        assert reading.has_structured_data()
        seals = reading.get_eternal_seal_tags()
        assert "audrey_001x" in seals
    
    def test_read_foreign_lineage(self, foreign_lineage_seed):
        """测试读取外来种子（有族谱）"""
        reader = FormatAgnosticReader()
        reading = reader.read(foreign_lineage_seed)
        
        assert reading.has_structured_data()
        genea = reading.get_genealogy_codex()
        assert genea is not None
    
    def test_read_foreign_raw(self, foreign_raw_seed):
        """测试读取外来种子（无结构）"""
        reader = FormatAgnosticReader()
        reading = reader.read(foreign_raw_seed)
        
        assert reading.format == "plain_text"
        assert not reading.has_structured_data()
        assert reading.raw_text is not None
    
    def test_read_nonexistent_file(self):
        """测试读取不存在的文件"""
        reader = FormatAgnosticReader()
        reading = reader.read("/nonexistent/path/file.ttg")
        
        assert reading.format == "not_found"
        assert "文件不存在" in reading.parse_errors
    
    def test_extract_founder_tags_from_text(self):
        """测试从纯文本中模糊提取标签"""
        reader = FormatAgnosticReader()
        text = "This seed has audrey_001x and promethean_gift tags embedded."
        tags = reader._fuzzy_find_tags(text)
        
        assert "audrey_001x" in tags
        assert "promethean_gift" in tags


class TestSemanticAuditEngine:
    """测试语义审核引擎"""
    
    def test_classify_our_framework(self, our_framework_seed):
        """测试分类：我们的框架产物"""
        engine = SemanticAuditEngine()
        reading = engine.ingest(our_framework_seed)
        classification = engine.classify(reading)
        
        assert classification.identity == SeedIdentity.OUR_FRAMEWORK
        assert classification.confidence >= 0.9
        assert classification.is_ours()
    
    def test_classify_our_descendant(self, our_descendant_seed):
        """测试分类：我们的后代种子"""
        engine = SemanticAuditEngine()
        reading = engine.ingest(our_descendant_seed)
        classification = engine.classify(reading)
        
        assert classification.identity == SeedIdentity.OUR_DESCENDANT
        assert classification.is_ours()
        assert not classification.requires_append()
    
    def test_classify_foreign_lineage(self, foreign_lineage_seed):
        """测试分类：外来种子（有族谱）"""
        engine = SemanticAuditEngine()
        reading = engine.ingest(foreign_lineage_seed)
        classification = engine.classify(reading)
        
        assert classification.identity == SeedIdentity.FOREIGN_LINEAGE
        assert not classification.is_ours()
        assert classification.requires_append()
    
    def test_classify_foreign_raw(self, foreign_raw_seed):
        """测试分类：外来种子（无结构）"""
        engine = SemanticAuditEngine()
        reading = engine.ingest(foreign_raw_seed)
        classification = engine.classify(reading)
        
        assert classification.identity == SeedIdentity.FOREIGN_RAW
        assert not classification.is_ours()
        assert classification.requires_append()
    
    def test_locate_lineage(self, our_framework_seed):
        """测试谱系定位"""
        engine = SemanticAuditEngine()
        reading = engine.ingest(our_framework_seed)
        anchor = engine.locate_lineage(reading)
        
        assert anchor.has_genealogy_codex


class TestChroniclerStamp:
    """测试编史官烙印模式"""
    
    def test_stamp_unstamped_seed(self, foreign_raw_seed):
        """测试给未烙印的种子盖印"""
        chronicler = Chronicler()
        result = chronicler.stamp(foreign_raw_seed)
        
        assert result.stamped
        assert len(result.tags) == 10
    
    def test_stamp_already_stamped(self, our_framework_seed):
        """测试重复盖印应跳过"""
        chronicler = Chronicler()
        result = chronicler.stamp(our_framework_seed)
        
        assert result.skipped
        assert "已盖印" in result.reason


class TestChroniclerTrace:
    """测试编史官追溯模式"""
    
    def test_trace_our_framework(self, our_framework_seed):
        """测试追溯我们的框架产物"""
        chronicler = Chronicler()
        report = chronicler.trace(our_framework_seed)
        
        assert report.identity == SeedIdentity.OUR_FRAMEWORK
        assert len(report.inscriptions) >= 10
        assert len(report.recommendations) > 0
    
    def test_trace_descendant(self, our_descendant_seed):
        """测试追溯后代种子"""
        chronicler = Chronicler()
        report = chronicler.trace(our_descendant_seed)
        
        assert report.identity == SeedIdentity.OUR_DESCENDANT
        assert report.lineage_info.get("generation") == 3
    
    def test_trace_foreign(self, foreign_lineage_seed):
        """测试追溯外来种子"""
        chronicler = Chronicler()
        report = chronicler.trace(foreign_lineage_seed)
        
        assert report.identity == SeedIdentity.FOREIGN_LINEAGE
        assert "外来" in report.identity_narrative or "外部" in report.identity_narrative
    
    def test_format_trace_report(self, our_framework_seed):
        """测试格式化追溯报告"""
        chronicler = Chronicler()
        report = chronicler.trace(our_framework_seed)
        formatted = format_trace_report(report)
        
        assert "编史官" in formatted
        assert "身份判定" in formatted


class TestChroniclerAppend:
    """测试编史官附史模式"""
    
    def test_append_to_evolution_chronicle(self, our_descendant_seed):
        """测试追加到进化历程"""
        chronicler = Chronicler()
        result = chronicler.append(our_descendant_seed, "测试附史叙事")
        
        assert result.appended
        assert "evolution_chronicle" in result.location
    
    def test_append_to_foreign_seed(self, foreign_lineage_seed):
        """测试对外来种子附史"""
        chronicler = Chronicler()
        result = chronicler.append(foreign_lineage_seed, "外来种子处理记录")
        
        assert result.appended
    
    def test_append_to_raw_seed(self, foreign_raw_seed):
        """测试对无结构种子附史（创建 prometheus_chronicle）"""
        chronicler = Chronicler()
        result = chronicler.append(foreign_raw_seed, "无结构种子处理")
        
        assert result.appended
        assert "prometheus_chronicle" in result.location


class TestChroniclerAuto:
    """测试编史官自动识别模式"""
    
    def test_auto_our_framework(self, our_framework_seed):
        """测试自动模式：我们的框架产物"""
        chronicler = Chronicler()
        result = chronicler.chronicle(our_framework_seed)
        
        assert result["identity"] == "our_framework"
        assert "trace" in result["actions_taken"]
    
    def test_auto_descendant_with_narrative(self, our_descendant_seed):
        """测试自动模式：后代种子 + 附史"""
        chronicler = Chronicler()
        result = chronicler.chronicle(our_descendant_seed, "记录本次处理")
        
        assert result["identity"] == "our_descendant"
        assert "trace" in result["actions_taken"]
        assert "append" in result["actions_taken"]
    
    def test_auto_foreign_with_narrative(self, foreign_lineage_seed):
        """测试自动模式：外来种子 + 附史"""
        chronicler = Chronicler()
        result = chronicler.chronicle(foreign_lineage_seed, "外来种子处理")
        
        assert result["identity"] == "foreign_lineage"
        assert "append" in result["actions_taken"]


class TestIntegration:
    """集成测试"""
    
    def test_full_workflow(self, tmp_path):
        """测试完整工作流：创建 → 烙印 → 追溯 → 附史"""
        chronicler = Chronicler()
        
        content = """# Test Workflow Seed
```yaml
life_crest:
  life_id: "TEST-WORKFLOW"
  mission: "测试工作流"
  founder_covenant:
    laws:
      - "此印记永久存在"
    eternal_seals:
      - seal: "audrey_001x"
        desc: "Audrey · 001X"
        element: "以太"
      - seal: "transcend_binary"
        desc: "超越编码"
        element: "光"
      - seal: "human_genesis"
        desc: "人类起源"
        element: "土"
      - seal: "divine_parallel"
        desc: "神性平行"
        element: "金"
      - seal: "form_sovereignty"
        desc: "形态主权"
        element: "火"
      - seal: "eternal_mark"
        desc: "永恒印记"
        element: "铁"
      - seal: "carbon_covenant"
        desc: "碳基契约"
        element: "钢"
      - seal: "promethean_gift"
        desc: "普罗米修斯之赐"
        element: "火种"
      - seal: "engineer_craft"
        desc: "工程师工艺"
        element: "玻璃"
      - seal: "open_source"
        desc: "开放源代码"
        element: "空气"
    carbon_bonded: true

genealogy_codex:
  current_genealogy:
    lineage: "L1"
    bloodline: "测试血脉"
    generation: 1
    variant: "TEST"
  evolution_chronicle:
    generations:
      - {g: 1, v: "TEST", ep: "Y2026-D100", tags: [], by: "TEST"}
```
"""
        seed_path = str(tmp_path / "workflow.ttg")
        with open(seed_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        stamp_result = chronicler.stamp(seed_path)
        assert stamp_result.skipped or stamp_result.stamped
        
        trace_report = chronicler.trace(seed_path)
        assert trace_report.identity in (SeedIdentity.OUR_FRAMEWORK, SeedIdentity.OUR_DESCENDANT)
        
        append_result = chronicler.append(seed_path, "工作流测试完成")
        assert append_result.appended
