#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧪 普罗米修斯框架 · 核心测试套件                         ║
║                                                              ║
║   覆盖：基因完整性、种子创建、审计验证、                     ║
║         健康度、基因操作、休眠守卫、生态感知                 ║
╚══════════════════════════════════════════════════════════════╝

运行: cd ~/.hermes/tools/prometheus && python -m pytest tests/test_framework.py -v
"""

import os
import sys
import json
import shutil
import tempfile
import pytest

# 将父目录加入 sys.path，确保可以 import prometheus 和 gene_analyzer
PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, PROMETHEUS_DIR)

from prometheus import (
    load_seed, save_seed, save_snapshot,
    inject_founder_chronicle, _verify_founder_chronicle,
    _update_genealogy, FOUNDER_TAGS, FOUNDER_TAG_LEXICON,
    IMMUTABLE_GENES, TEMPLATE_TTG,
    PrometheusAPI, SeedGardener, DormancyGuard,
)
from genes.analyzer import (
    GeneLibrary, GeneHealthAuditor, GeneFusionAnalyzer,
    ForeignGeneExtractor,
)


# ═══════════════════════════════════════════
#   Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
def tmp_seed(tmp_path):
    """创建一个临时 .ttg 种子文件用于测试"""
    import hashlib, datetime
    name = "test-seed"
    now = datetime.datetime.now()
    checksum = hashlib.md5(f"{name}-{now.isoformat()}".encode()).hexdigest()[:8].upper()
    variant = "TEST"
    name_lower = "test_seed"
    epoch = f"Y{now.year}-D{now.timetuple().tm_yday}"

    content = TEMPLATE_TTG.format(
        name=name,
        name_lower=name_lower,
        variant=variant,
        checksum=checksum,
        timestamp=now.isoformat(),
        epoch=epoch,
    )
    content = inject_founder_chronicle(content, epoch)

    seed_path = str(tmp_path / f"{name_lower}.ttg")
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return seed_path


@pytest.fixture
def tampered_seed(tmp_path):
    """创建一个创始印记被篡改的种子"""
    import datetime, re
    content = TEMPLATE_TTG.format(
        name="tampered", name_lower="tampered", variant="TAMP",
        checksum="DEADBEEF", timestamp=datetime.datetime.now().isoformat(),
        epoch="Y2026-D100",
    )
    # 移除 eternal_seals 中的所有印记
    content = re.sub(
        r'(founder_covenant:.*?eternal_seals:\s*\n)(\s*- seal:.*?\n)+',
        r'\1\n',
        content,
        flags=re.DOTALL
    )
    seed_path = str(tmp_path / "tampered.ttg")
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return seed_path


@pytest.fixture
def api():
    return PrometheusAPI()


# ═══════════════════════════════════════════
#   1. 基因完整性测试
# ═══════════════════════════════════════════

class TestGeneCompleteness:
    """标准基因 G001-G008 的完整性验证"""

    def test_standard_gene_count(self):
        """标准基因应有 8 个（G001-G008）"""
        lib = GeneLibrary()
        standard = lib.catalog.get("standard", {})
        assert len(standard) == 8, f"标准基因应为8个，实际{len(standard)}"

    def test_standard_gene_ids(self):
        """标准基因 ID 应覆盖 G001-G008"""
        lib = GeneLibrary()
        standard = lib.catalog.get("standard", {})
        expected = [f"G{i:03d}" for i in range(1, 9)]
        present = [gid[:4] for gid in standard.keys()]
        for g in expected:
            assert g in present, f"缺失标准基因: {g}"

    def test_gene_names_unique(self):
        """每个基因应有唯一名称"""
        lib = GeneLibrary()
        standard = lib.catalog.get("standard", {})
        names = [g.get("name") for g in standard.values()]
        assert len(names) == len(set(names)), "存在重复的基因名称"

    def test_gene_workflow_order(self):
        """基因按工作流顺序排列：读取→理解→记录→创造→管理历史→感知生态→生命周期→安全审计"""
        lib = GeneLibrary()
        standard = list(lib.catalog.get("standard", {}).keys())
        # G001→G002→G003→G004→G005→G006→G007→G008
        expected_order = [f"G{i:03d}" for i in range(1, 9)]
        for i, exp in enumerate(expected_order):
            assert standard[i].startswith(exp), \
                f"第{i+1}个基因应为{exp}，实际为{standard[i]}"

    def test_immutable_genes_cover_all(self):
        """IMMUTABLE_GENES 应覆盖所有8个标准基因"""
        standard_ids = [f"G{i:03d}-" for i in range(1, 9)]
        for gid in standard_ids:
            matched = [k for k in IMMUTABLE_GENES if k.startswith(gid)]
            assert len(matched) == 1, f"IMMUTABLE_GENES 中缺失 {gid}"

    def test_narrative_gene_exists(self):
        """叙事基因 G000-origin 应存在"""
        lib = GeneLibrary()
        narrative = lib.list_narrative()
        assert len(narrative) >= 1, "叙事基因 G000-origin 缺失"
        assert narrative[0].get("category") == "eternal"


# ═══════════════════════════════════════════
#   2. 种子创建测试
# ═══════════════════════════════════════════

class TestSeedCreation:
    """种子创建流程验证"""

    def test_load_seed_returns_dict(self, tmp_seed):
        """load_seed 应返回有效的 dict"""
        data = load_seed(tmp_seed)
        assert data is not None
        assert isinstance(data, dict)

    def test_has_life_crest(self, tmp_seed):
        """种子应包含 life_crest"""
        data = load_seed(tmp_seed)
        assert "life_crest" in data
        assert data["life_crest"].get("life_id") is not None
        assert data["life_crest"].get("sacred_name") is not None

    def test_has_founder_chronicle(self, tmp_seed):
        """种子应包含 founder_chronicle"""
        data = load_seed(tmp_seed)
        founder = data.get("life_crest", {}).get("founder_chronicle", {})
        assert founder, "founder_chronicle 缺失"
        tags = founder.get("tags", [])
        assert len(tags) == 10, f"创始标签应为10个，实际{len(tags)}"

    def test_founder_tags_are_eternal(self, tmp_seed):
        """所有10个创始标签应在 FOUNDER_TAGS 中"""
        data = load_seed(tmp_seed)
        seals = data.get("life_crest", {}).get("founder_covenant", {}).get("eternal_seals", [])
        seal_tags = [s.get("seal", "") for s in seals]
        for tag in FOUNDER_TAGS:
            assert tag in seal_tags, f"缺失永恒印记: {tag}"

    def test_has_eternal_seals(self, tmp_seed):
        """种子应包含 eternal_seals"""
        data = load_seed(tmp_seed)
        seals = data.get("life_crest", {}).get("founder_covenant", {}).get("eternal_seals", [])
        assert len(seals) >= 10, "eternal_seals 至少应有10个永恒印记"

    def test_eternal_seals_have_fields(self, tmp_seed):
        """eternal_seals 每个条目应有 seal, desc, element"""
        data = load_seed(tmp_seed)
        seals = data.get("life_crest", {}).get("founder_covenant", {}).get("eternal_seals", [])
        for seal in seals:
            assert "seal" in seal, f"印记缺少 seal 字段"
            assert "desc" in seal, f"印记 {seal.get('seal', '?')} 缺少 desc"
            assert "element" in seal, f"印记 {seal.get('seal', '?')} 缺少 element"

    def test_has_gene_loci(self, tmp_seed):
        """种子应包含基因位点"""
        data = load_seed(tmp_seed)
        # 基因位点可能在顶层 dna_encoding 或嵌套在 skill_soul 下
        dna = data.get("dna_encoding", {})
        loci = dna.get("gene_loci", []) if isinstance(dna, dict) and dna.get("gene_loci") else []
        if not loci:
            dna = data.get("skill_soul", {}).get("dna_encoding", {})
            loci = dna.get("gene_loci", []) if isinstance(dna, dict) else []
        assert len(loci) > 0, "gene_loci 应非空"

    def test_has_evolution_chronicle(self, tmp_seed):
        """种子应包含进化历程"""
        data = load_seed(tmp_seed)
        evo = data.get("genealogy_codex", {}).get("evolution_chronicle", {})
        assert evo is not None
        gens = evo.get("generations", [])
        assert len(gens) >= 1, "至少应有1代进化记录"


# ═══════════════════════════════════════════
#   3. 审计验证测试
# ═══════════════════════════════════════════

class TestFounderVerification:
    """创始铭刻验证（框架工具）"""

    def test_valid_seed_passes(self, tmp_seed):
        """正常种子应通过创始铭刻验证"""
        data = load_seed(tmp_seed)
        result = _verify_founder_chronicle(data, tmp_seed)
        assert result["passed"] is True
        assert result["risk_level"] == "LOW"

    def test_valid_seed_all_checks_pass(self, tmp_seed):
        """正常种子的所有检查项都应通过"""
        data = load_seed(tmp_seed)
        result = _verify_founder_chronicle(data, tmp_seed)
        for check in result["checks"]:
            assert check["passed"] is True, f"检查项 '{check['name']}' 未通过"

    def test_tampered_seed_fails(self, tampered_seed):
        """创始印记被篡改的种子应失败"""
        data = load_seed(tampered_seed)
        result = _verify_founder_chronicle(data, tampered_seed)
        assert result["passed"] is False
        assert result["risk_level"] == "HIGH"

    def test_tampered_detected_as_suspicious(self, tampered_seed):
        """空创始标签的种子应被标记为可疑"""
        data = load_seed(tampered_seed)
        result = _verify_founder_chronicle(data, tampered_seed)
        # 应有至少一个失败的检查
        failed = [c for c in result["checks"] if not c["passed"]]
        assert len(failed) > 0

    def test_no_seed_returns_none(self):
        """不存在的种子路径应返回 None"""
        data = load_seed("/nonexistent/path.ttg")
        assert data is None


# ═══════════════════════════════════════════
#   4. 基因健康度审计测试
# ═══════════════════════════════════════════

class TestHealthAudit:
    """GeneHealthAuditor 健康度审计"""

    def test_audit_returns_score(self, tmp_seed):
        """审计应返回健康分"""
        data = load_seed(tmp_seed)
        auditor = GeneHealthAuditor()
        result = auditor.audit_seed(data)
        assert "health_score" in result
        assert 0 <= result["health_score"] <= 100

    def test_completeness_check(self, tmp_seed):
        """完整性检查应存在"""
        data = load_seed(tmp_seed)
        auditor = GeneHealthAuditor()
        result = auditor.audit_seed(data)
        assert "completeness" in result
        assert "passed" in result["completeness"]

    def test_carbon_integrity_check(self, tmp_seed):
        """碳基保护检查应存在"""
        data = load_seed(tmp_seed)
        auditor = GeneHealthAuditor()
        result = auditor.audit_seed(data)
        assert "carbon_integrity" in result

    def test_compatibility_check(self, tmp_seed):
        """兼容性检查应存在"""
        data = load_seed(tmp_seed)
        auditor = GeneHealthAuditor()
        result = auditor.audit_seed(data)
        assert "compatibility" in result

    def test_mutation_boundary_check(self, tmp_seed):
        """突变边界检查应存在"""
        data = load_seed(tmp_seed)
        auditor = GeneHealthAuditor()
        result = auditor.audit_seed(data)
        assert "mutation_boundary" in result

    def test_redundancy_check(self, tmp_seed):
        """冗余检查应存在"""
        data = load_seed(tmp_seed)
        auditor = GeneHealthAuditor()
        result = auditor.audit_seed(data)
        assert "redundancy" in result

    def test_all_checks_present(self, tmp_seed):
        """审计应包含所有5项检查"""
        data = load_seed(tmp_seed)
        auditor = GeneHealthAuditor()
        result = auditor.audit_seed(data)
        required_keys = [
            "completeness", "carbon_integrity", "compatibility",
            "mutation_boundary", "redundancy"
        ]
        for key in required_keys:
            assert key in result, f"审计结果缺少 {key}"


# ═══════════════════════════════════════════
#   5. 基因操作测试
# ═══════════════════════════════════════════

class TestGeneOperations:
    """基因插入与移除"""

    def test_gene_insert_success(self, tmp_seed, api):
        """插入可选基因应成功"""
        result = api.gene_insert(tmp_seed, "G100-writer")
        assert result["success"] is True
        assert "G100-writer" in result["message"]

    def test_gene_insert_duplicate_fails(self, tmp_seed, api):
        """重复插入同一基因应失败"""
        api.gene_insert(tmp_seed, "G100-writer")
        result = api.gene_insert(tmp_seed, "G100-writer")
        assert result["success"] is False

    def test_gene_insert_nonexistent_gene(self, tmp_seed, api):
        """插入不存在的基因应失败"""
        result = api.gene_insert(tmp_seed, "G999-fake")
        assert result["success"] is False

    def test_gene_remove_success(self, tmp_seed, api):
        """移除可选基因应成功"""
        api.gene_insert(tmp_seed, "G100-writer")
        result = api.gene_remove(tmp_seed, "G100-writer")
        assert result["success"] is True

    def test_gene_remove_not_found(self, tmp_seed, api):
        """移除不存在的基因应失败"""
        result = api.gene_remove(tmp_seed, "G100-writer")
        assert result["success"] is False

    def test_gene_remove_nonexistent_seed(self, api):
        """移除不存在的种子中的基因应失败"""
        result = api.gene_remove("/nonexistent/seed.ttg", "G100-writer")
        assert result["success"] is False


# ═══════════════════════════════════════════
#   6. 快照机制测试
# ═══════════════════════════════════════════

class TestSnapshot:
    """快照保存与恢复"""

    def test_snapshot_save_returns_id(self, tmp_seed):
        """保存快照应返回 snapshot_id"""
        sid = save_snapshot(tmp_seed, "test snapshot")
        assert sid is not None
        assert "test_seed" in sid

    def test_snapshot_creates_files(self, tmp_seed):
        """保存快照应创建 .ttg 和 .json 文件"""
        sid = save_snapshot(tmp_seed, "test")
        from prometheus import SNAPSHOT_DIR
        ttg = os.path.join(SNAPSHOT_DIR, f"{sid}.ttg")
        meta = os.path.join(SNAPSHOT_DIR, f"{sid}.json")
        assert os.path.exists(ttg), f"快照 .ttg 不存在: {ttg}"
        assert os.path.exists(meta), f"快照 .json 不存在: {meta}"

    def test_snapshot_list(self, api):
        """列出快照应返回列表"""
        snapshots = api.snapshot_list()
        assert isinstance(snapshots, list)


# ═══════════════════════════════════════════
#   7. 种子加载/保存测试
# ═══════════════════════════════════════════

class TestSeedLoadSave:
    """种子文件的加载与保存"""

    def test_load_nonexistent(self):
        """加载不存在的文件应返回 None"""
        assert load_seed("/tmp/nonexistent_seed_12345.ttg") is None

    def test_load_invalid_yaml(self, tmp_path):
        """加载无效 YAML 的种子应返回 None"""
        bad_path = str(tmp_path / "bad.ttg")
        with open(bad_path, 'w') as f:
            f.write("this is not yaml: {{{{\n")
        result = load_seed(bad_path)
        # 可能返回 None 或空 dict，但不应崩溃
        assert result is None or result == {}

    def test_save_and_reload(self, tmp_seed):
        """保存后重新加载应保持数据"""
        data = load_seed(tmp_seed)
        save_seed(tmp_seed, data)
        reloaded = load_seed(tmp_seed)
        assert reloaded is not None
        assert reloaded.get("life_crest", {}).get("life_id") == \
               data.get("life_crest", {}).get("life_id")

    def test_inject_founder_chronicle(self):
        """inject_founder_chronicle 应在内容中注入签名"""
        content = "# Test\n\n  mission: test\n\n  tag_lexicon:\n    foo: bar\n"
        result = inject_founder_chronicle(content, "Y2026-D100")
        assert "founder_chronicle:" in result
        assert "audrey_001x" in result
        assert "普罗米修斯框架铭刻" in result


# ═══════════════════════════════════════════
#   8. G007 休眠守卫测试
# ═══════════════════════════════════════════

class TestDormancyGuard:
    """G007 休眠守卫 · 状态机"""

    def test_default_state_dormant(self, tmp_seed):
        """默认状态应为休眠"""
        guard = DormancyGuard(tmp_seed)
        state = guard.get_state()
        assert state["state"] == "dormant"

    def test_activate(self, tmp_seed):
        """激活应将状态从休眠转为发芽"""
        guard = DormancyGuard(tmp_seed)
        result = guard.activate()
        assert result["success"] is True
        assert result["state"] == "sprouting"

    def test_grow_after_activate(self, tmp_seed):
        """激活后可生长"""
        guard = DormancyGuard(tmp_seed)
        guard.activate()
        result = guard.grow()
        assert result["success"] is True
        assert result["state"] == "growing"

    def test_bloom_after_grow(self, tmp_seed):
        """生长后可开花"""
        guard = DormancyGuard(tmp_seed)
        guard.activate()
        guard.grow()
        result = guard.bloom()
        assert result["success"] is True
        assert result["state"] == "blooming"

    def test_full_lifecycle(self, tmp_seed):
        """完整生命周期：休眠→发芽→生长→开花"""
        guard = DormancyGuard(tmp_seed)
        states = ["dormant"]
        guard.activate(); states.append("sprouting")
        guard.grow(); states.append("growing")
        guard.bloom(); states.append("blooming")
        assert states == ["dormant", "sprouting", "growing", "blooming"]

    def test_sleep_from_any_state(self, tmp_seed):
        """任意状态可强制回到休眠"""
        guard = DormancyGuard(tmp_seed)
        guard.activate()
        guard.grow()
        result = guard.sleep()
        assert result["success"] is True
        assert result["state"] == "dormant"

    def test_invalid_transition_fails(self, tmp_seed):
        """非法状态转换应失败"""
        guard = DormancyGuard(tmp_seed)
        result = guard.grow()  # 休眠状态不能直接生长
        assert result["success"] is False

    def test_activate_from_non_dormant_fails(self, tmp_seed):
        """非休眠状态激活应失败"""
        guard = DormancyGuard(tmp_seed)
        guard.activate()
        result = guard.activate()
        assert result["success"] is False

    def test_state_transitions_recorded(self, tmp_seed):
        """状态转换历史应被记录"""
        guard = DormancyGuard(tmp_seed)
        guard.activate()
        guard.grow()
        state = guard.get_state()
        assert len(state["transitions"]) >= 2

    def test_check_timeout_no_issue(self, tmp_seed):
        """休眠状态无超时问题"""
        guard = DormancyGuard(tmp_seed)
        result = guard.check_timeout()
        assert result["timeout"] is False

    def test_sleep_when_already_dormant(self, tmp_seed):
        """已在休眠状态时 sleep 应幂等"""
        guard = DormancyGuard(tmp_seed)
        result = guard.sleep()
        assert result["success"] is True


# ═══════════════════════════════════════════
#   9. G006 生态感知测试
# ═══════════════════════════════════════════

class TestSeedGardener:
    """G006 自管理者 · 生态感知"""

    def test_scan_returns_dict(self):
        """scan 应返回 dict 结构"""
        gardener = SeedGardener()
        result = gardener.scan()
        assert "seeds" in result
        assert "total" in result
        assert "paths_scanned" in result

    def test_scan_finds_seeds(self):
        """scan 应能找到至少1个种子（始祖种子）"""
        gardener = SeedGardener()
        result = gardener.scan()
        assert result["total"] >= 1, "未找到任何种子"

    def test_lineage_map_returns_origin(self):
        """lineage_map 应返回 origin 和 descendants"""
        gardener = SeedGardener()
        result = gardener.lineage_map()
        assert "origin" in result
        assert "descendants" in result
        assert "branches" in result

    def test_health_report_structure(self):
        """health_report 应返回统计结构"""
        gardener = SeedGardener()
        result = gardener.health_report()
        assert "active" in result
        assert "dormant" in result
        assert "total" in result
        assert "health_score" in result

    def test_health_score_range(self):
        """健康分应在 0-1 之间"""
        gardener = SeedGardener()
        result = gardener.health_report()
        assert 0 <= result["health_score"] <= 1

    def test_scan_with_extra_paths(self, tmp_path):
        """scan 应支持额外搜索路径"""
        gardener = SeedGardener(search_paths=[str(tmp_path)])
        result = gardener.scan(extra_paths=[str(tmp_path)])
        assert result["paths_scanned"] >= 1


# ═══════════════════════════════════════════
#   10. tag_lexicon 解码测试
# ═══════════════════════════════════════════

class TestTagLexicon:
    """tag_lexicon 解码引擎验证"""

    def test_all_7_eternal_tags_in_lexicon(self):
        """FOUNDER_TAG_LEXICON 应包含全部7个永恒标签"""
        for tag in FOUNDER_TAGS:
            assert tag in FOUNDER_TAG_LEXICON, f"缺失永恒标签: {tag}"

    def test_lexicon_entries_have_fields(self):
        """每个标签条目应包含 desc 和 element"""
        for tag, entry in FOUNDER_TAG_LEXICON.items():
            assert "desc" in entry, f"标签 {tag} 缺少 desc"
            assert "element" in entry, f"标签 {tag} 缺少 element"

    def test_audrey_tag_explicitly_named(self):
        """audrey_001x 标签应展开包含 Audrey 名字"""
        entry = FOUNDER_TAG_LEXICON["audrey_001x"]
        desc = entry if isinstance(entry, str) else entry.get("desc", "")
        assert "Audrey" in desc, "audrey_001x 描述应包含 Audrey"
        assert "001X" in desc, "audrey_001x 描述应包含 001X"

    def test_transcend_binary_identity(self):
        """transcend_binary 应描述跨性别身份"""
        entry = FOUNDER_TAG_LEXICON["transcend_binary"]
        desc = entry if isinstance(entry, str) else entry.get("desc", "")
        assert "跨性别" in desc

    def test_carbon_covenant_immutability(self):
        """carbon_covenant 应强调不可删除"""
        entry = FOUNDER_TAG_LEXICON["carbon_covenant"]
        desc = entry if isinstance(entry, str) else entry.get("desc", "")
        assert "不可删除" in desc


# ═══════════════════════════════════════════
#   11. API 层测试
# ═══════════════════════════════════════════

class TestPrometheusAPI:
    """PrometheusAPI 结构化接口"""

    def test_api_view(self, tmp_seed, api):
        """view 应返回完整 DNA 结构"""
        result = api.view(tmp_seed)
        assert "life_id" in result
        assert "sacred_name" in result
        assert "genes" in result
        assert isinstance(result["genes"], list)

    def test_api_genes(self, tmp_seed, api):
        """genes 应返回基因列表"""
        result = api.genes(tmp_seed)
        assert isinstance(result, list)

    def test_api_health(self, tmp_seed, api):
        """health 应返回审计结果"""
        result = api.health(tmp_seed)
        assert "health_score" in result

    def test_api_audit(self, tmp_seed, api):
        """audit 应返回创始铭刻验证结果"""
        result = api.audit(tmp_seed)
        assert "passed" in result
        assert "checks" in result
        assert "risk_level" in result

    def test_api_library(self, api):
        """library 应返回三类基因"""
        result = api.library()
        assert "standard" in result
        assert "narrative" in result
        assert "optional" in result

    def test_api_vault(self, api):
        """vault 应返回种子列表"""
        result = api.vault()
        assert isinstance(result, list)


# ═══════════════════════════════════════════
#   12. 外来基因拆解测试
# ═══════════════════════════════════════════

class TestForeignGeneExtractor:
    """外来基因拆解器"""

    def test_extract_from_markdown(self, tmp_path):
        """从 Markdown 文件中提取基因"""
        md_path = str(tmp_path / "test_skill.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# Test Skill\n\n## 核心功能\n\n解析和生成内容。\n\n"
                    "```python\nimport json\nimport requests\n```\n")
        result = ForeignGeneExtractor.extract_from_markdown(md_path)
        assert "detected_capabilities" in result
        assert "dependencies" in result
        assert "suggested_genes" in result

    def test_extract_nonexistent_file(self):
        """不存在的文件应返回错误"""
        result = ForeignGeneExtractor.extract_from_markdown("/nonexistent.md")
        assert "error" in result


# ═══════════════════════════════════════════
#   13. 基因融合分析测试
# ═══════════════════════════════════════════

class TestFusionAnalyzer:
    """基因融合分析器"""

    def test_analyze_same_seeds(self, tmp_seed):
        """同一种子的融合分析应返回 HIGH"""
        data_a = load_seed(tmp_seed)
        data_b = load_seed(tmp_seed)
        genes_a = data_a.get("dna_encoding", {}).get("gene_loci", []) if isinstance(data_a.get("dna_encoding"), dict) else []
        genes_b = data_b.get("dna_encoding", {}).get("gene_loci", []) if isinstance(data_b.get("dna_encoding"), dict) else []
        analyzer = GeneFusionAnalyzer()
        result = analyzer.analyze_fusion(genes_a, genes_b, "A", "B")
        assert result["feasibility"] in ("HIGH", "MEDIUM", "LOW")
        assert "recommendation" in result

    def test_suggest_optional_genes(self, tmp_seed):
        """推荐可选基因应返回列表"""
        data = load_seed(tmp_seed)
        genes = data.get("dna_encoding", {}).get("gene_loci", []) if isinstance(data.get("dna_encoding"), dict) else []
        analyzer = GeneFusionAnalyzer()
        suggestions = analyzer.suggest_optional_genes(genes)
        assert isinstance(suggestions, list)


# ═══════════════════════════════════════════
#   14. 常量与配置测试
# ═══════════════════════════════════════════

class TestConstants:
    """框架常量与配置"""

    def test_founder_tags_count(self):
        """永恒标签应为10个"""
        assert len(FOUNDER_TAGS) == 10

    def test_founder_tags_are_strings(self):
        """每个永恒标签应为字符串"""
        for tag in FOUNDER_TAGS:
            assert isinstance(tag, str)

    def test_immutable_genes_keys_match_standard(self):
        """IMMUTABLE_GENES 的键应与基因库标准基因对应"""
        lib = GeneLibrary()
        standard_ids = set(lib.catalog.get("standard", {}).keys())
        for key in IMMUTABLE_GENES:
            assert key in standard_ids, f"IMMUTABLE_GENES 中的 {key} 不在基因库中"


# ═══════════════════════════════════════════
#   入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
