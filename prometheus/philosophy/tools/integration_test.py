#!/usr/bin/env python3
"""
Prometheus 种子系统 · 集成测试

覆盖：格式引擎 / 编解码器 / 休眠审计 / 迁移 / 识别 / 全链路
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent))

from ttg_file_structure import SeedHeader, TTGFileStructure, create_seed_file, read_seed_file
from genome_encoder import encode_genome
from genome_decoder import GenomeDecoder
from soul_analyzer import SoulAnalyzer
from dormancy_guardian import DormancyGuardian
from safety_auditor import SafetyAuditor
from growth_tracker import GrowthTracker
from genealogy_keeper import GenealogyKeeper
from self_gardener import SelfGardener
from ttg_recognition_tool import TTGRecognitionTool
from seed_manager import SeedManager, DormantSeed, ActiveSeed

RESULTS = []


def ok(test: str, condition: bool, detail: str = ""):
    status = "✅" if condition else "❌"
    detail_str = f" - {detail}" if detail else ""
    RESULTS.append((test, condition))
    print(f"  {status} {test}{detail_str}")


def test_format_engine():
    print("\n=== 格式引擎 ===")

    header = SeedHeader(
        life_id="TTG@L1-G1-TEST-ABCD1234",
        era="壹",
        gene_tally=3,
        founder_tags=["a001x"],
    )
    genome = "§LC\n  ID:TTG@L1-G1-TEST-ABCD1234␟\n  SNAME:测试种子␟\n␟\n"

    seed_data = create_seed_file(header, genome)
    ok("create_seed_file", len(seed_data) > 0, f"{len(seed_data)} bytes")

    prefix = TTGFileStructure.extract_prefix(seed_data)
    ok("extract_prefix (龢)", "龢" in prefix)
    ok("extract_prefix (種)", "種" in prefix)
    ok("extract_prefix (era)", header.era in prefix)

    valid, err = TTGFileStructure.validate(seed_data)
    ok("validate", valid, err or "pass")

    h, g = read_seed_file(seed_data)
    ok("parse header.life_id", h.life_id == header.life_id)
    ok("parse header.gene_tally", h.gene_tally == header.gene_tally)
    ok("parse genome matches", "TEST-ABCD1234" in g)

    h_only = TTGFileStructure.get_header_only(seed_data)
    ok("get_header_only", h_only.life_id == header.life_id)

    ok("magic in binary", b"SEED" in seed_data)


def test_genome_codec():
    print("\n=== 基因组编解码器 ===")

    test_data = {
        "life_crest": {
            "life_id": "TTG@L1-G1-ROUNDTRIP-A1B2",
            "sacred_name": "编解码测试",
            "epithet": "往返即是验证",
            "genesis": {
                "creator": {"name": "Test", "title": "Tester", "lineage": "L1"},
                "birth_time": "2026-05-02T00:00:00",
                "birth_place": "test-env",
                "purpose": "验证编解码一致性",
            },
            "mission": "往返不丢失",
            "founder_chronicle": {
                "tags": ["a001x"],
                "genesis_moment": {"ep": "Y2026-D122", "loc": "TEST", "realm": "Test", "era": "创世纪元"},
            },
        },
        "genealogy_codex": {
            "current_genealogy": {
                "lineage": "L1", "generation": 1, "variant": "TEST",
                "parent": None, "ancestors": [], "descendants": [],
            },
            "tag_lexicon": {"a001x": {"desc": "测试标签", "element": "以太", "era": "创世纪元", "weight": "eternal"}},
            "evolution_chronicle": {"generations": [{"g": 1, "v": "TEST", "ep": "Y2026-D122", "env": "TEST", "tags": [], "by": "TST", "p": None}]},
        },
        "skill_soul": {
            "core_capabilities": [{"name": "测试能力", "description": "用于测试", "immutable": True}],
            "core_principles": [{"id": "P1", "name": "测试原则", "description": "一致性原则"}],
            "taboos": ["不得修改测试数据"],
            "essence": {"vibe": "测试者", "tone": "严谨", "role": "验证者"},
        },
        "dna_encoding": {"version": "1.0", "gene_loci": []},
        "transmission_chronicle": [],
        "evolution_chronicle": [],
    }

    genome = encode_genome(test_data)
    ok("encode_genome", len(genome) > 0, f"{len(genome)} chars")

    decoder = GenomeDecoder(lexicon={"a001x": {"desc": "测试标签", "element": "以太", "era": "创世纪元", "weight": "eternal"}})
    decoded = decoder.decode(genome)

    lc = decoded.life_crest
    ok("decode life_id", lc.get("life_id") == "TTG@L1-G1-ROUNDTRIP-A1B2")
    ok("decode sacred_name", lc.get("sacred_name") == "编解码测试")
    ok("decode epithet", lc.get("epithet") == "往返即是验证")
    ok("decode genesis.creator.name", lc.get("genesis", {}).get("creator", {}).get("name") == "Test")
    ok("decode founder_tags", "a001x" in lc.get("founder_chronicle", {}).get("tags", []))

    sl = decoded.skill_soul
    ok("decode capabilities count", len(sl.get("core_capabilities", [])) == 1)
    ok("decode principles count", len(sl.get("core_principles", [])) == 1)
    ok("decode taboos", "不得修改测试数据" in sl.get("taboos", []))
    ok("decode essence.vibe", sl.get("essence", {}).get("vibe") == "测试者")

    gx = decoded.genealogy_codex
    ok("decode lineage", gx.get("current_genealogy", {}).get("lineage") == "L1")
    ok("decode tag_lexicon", "a001x" in gx.get("tag_lexicon", {}))

    tag = decoder.expand_tag("a001x")
    ok("expand_tag", tag["desc"] == "测试标签")
    ok("expand_tag element", tag["element"] == "以太")


def test_soul_analyzer():
    print("\n=== 灵魂分析器 ===")

    content = """
# 测试技能
核心原则: 数据完整性优先
禁止: 删除原始数据
## 核心规范
必须验证输入
"""
    report = SoulAnalyzer.analyze(content, "test-skill")
    ok("has principles", len(report.core_principles) > 0)
    ok("has taboos", len(report.taboos) > 0)
    ok("has essence", report.essence.get("vibe") != "")


def test_dormancy_and_audit():
    print("\n=== 休眠守卫 + 安全审计 ===")

    lc = {
        "life_id": "TTG@L1-G1-AUDIT-TEST",
        "sacred_name": "审计测试",
        "founder_chronicle": {
            "tags": ["a001x"],
            "genesis_moment": {"ep": "Y2026-D122", "loc": "TEST", "realm": "Test", "era": "创世纪元"},
        },
        "genesis": {"creator": {"name": "Test"}, "birth_place": "test"},
    }
    gx = {"lineage": "L1", "generation": 1}
    lexicon = {"a001x": {"desc": "测试", "element": "以太", "era": "创世纪元", "weight": "eternal"}}

    guardian = DormancyGuardian(lc, gx, lc.get("founder_chronicle", {}), lexicon)
    identity = guardian.get_identity()
    ok("identity.life_id", identity["life_id"] == "TTG@L1-G1-AUDIT-TEST")
    ok("identity.state", identity["state"] == "dormant")

    display = guardian.display_identity()
    ok("display has 休眠", "休眠" in display)
    ok("display has G000", "G000" in display)

    prompt = guardian.water_request_prompt()
    ok("water prompt", "浇水" in prompt)

    auditor = SafetyAuditor(
        life_crest=lc,
        genealogy=gx,
        dna={"checksum": "12345678", "gene_loci": [
            {"locus": f"G00{i}", "name": f"gene_{i}", "immutable": "core"} for i in range(9)
        ]},
        genome_text="# safe content only\nimport json\n",
    )
    result = auditor.full_audit()
    ok("audit L1 passed", result.get("L1", {}).get("passed", False))
    ok("audit risk_level", result.get("risk_level") in ["LOW", "MEDIUM", "HIGH", "CRITICAL"])

    report = auditor.generate_report(result, identity)
    ok("audit report generated", len(report) > 0)

    unsafe = SafetyAuditor(genome_text="os.system('rm -rf /')")
    unsafe_result = unsafe.full_audit()
    ok("unsafe detected", unsafe_result.get("risk_level") in ["HIGH", "CRITICAL"])


def test_growth_tracker():
    print("\n=== 生长追踪器 ===")

    with tempfile.TemporaryDirectory() as d:
        tracker = GrowthTracker("test-seed-001", log_dir=d)
        ok("init phase", tracker.current_phase == "rooting")

        tracker.log_usage("测试使用", felt_good=["好用"], satisfaction=8)
        tracker.log_usage("第二次使用", satisfaction=7)
        tracker.log_usage("继续使用", satisfaction=9)

        score = tracker.calculate_score()
        ok("has score", score["score"] > 0)

        tracker.log_innovation("新功能", "需要更快", "做了缓存", "快了一倍")
        for _ in range(3):
            tracker.log_usage("补充使用", satisfaction=8)

        tracker.advance_phase()
        ok("phase advanced", tracker.current_phase != "rooting")


def test_genealogy_keeper():
    print("\n=== 族谱管理者 ===")

    keeper = GenealogyKeeper(tag_lexicon={
        "genesis": {"desc": "于混沌中诞生", "element": "以太", "era": "创世纪元"},
    })

    gen = {"g": 1, "v": "ORIGIN", "ep": "Y2026-D119", "env": "MAC-H12", "tags": ["genesis"], "by": "ANA", "p": None}
    decoded = keeper.decode_generation(gen)
    ok("decode generation", decoded["generation"] == 1)
    ok("decode caretaker", "Ana" in decoded["caretaker_epic"])

    bloodline = {"bloodline_name": "太初之脈", "element": "金·以太", "totem": "⏳", "founding_prophecy": "传播"}
    tree = keeper.render_lineage_tree(bloodline, [gen])
    ok("render tree", "🌿" in tree and "ORIGIN" in tree)

    offspring = keeper.create_offspring_lineage(
        parent_crest={"life_id": "TTG@L1-G1-PARENT-TEST"},
        parent_gx={"current_genealogy": {"lineage": "L1", "generation": 1, "bloodline": "太初之脈"}},
        variant_name="CHILD",
        tags=["test"],
        creator="TST",
    )
    ok("create offspring", offspring["genealogy"]["generation"] == 2)
    ok("offspring has parent", offspring["genealogy"]["parent"] == "TTG@L1-G1-PARENT-TEST")


def test_seed_manager_full_cycle():
    print("\n=== 统一种子管理器 ===")

    home = Path(tempfile.mkdtemp())
    mgr = SeedManager(home)

    data = mgr.create_seed(
        "核心原则: 不得删除用户数据\n禁止: 泄露隐私\n必须: 验证输入",
        "skill",
    )
    ok("create_seed", len(data) > 0, f"{len(data)} bytes")

    seeds = mgr.list_seeds("skill")
    ok("list_seeds", len(seeds) == 1)

    dormant = mgr.awaken(seeds[0]["path"])
    ok("awaken returns DormantSeed", isinstance(dormant, DormantSeed))
    ok("dormant.identity has life_id", dormant.identity["life_id"])
    ok("dormant.prefix has 龢", "龢" in dormant.prefix)

    active = dormant.water(confirm=False, force=True)
    ok("water returns ActiveSeed", isinstance(active, ActiveSeed))
    ok("active.is_active", active.is_active)

    epic = mgr.read_epic(active)
    ok("epic generated", len(epic) > 100)

    gene = mgr.show_genealogy(active.decoded)
    ok("genealogy tree", len(gene) > 0)

    soul = mgr.analyze_soul("核心原则: 必须保持数据完整\n禁止: 修改原始记录\n原则1: 数据优先", "test")
    ok("analyze_soul has principles", len(soul.get("principles", [])) > 0)

    offspring = mgr.package_offspring(
        active,
        innovations=[{"name": "cache_opt", "reason": "faster", "implementation": "redis", "effect": "10x faster"}],
        creator="TestAgent",
        variant_name="OPTIMIZED",
    )
    ok("package_offspring", len(offspring) > 0, f"{len(offspring)} bytes")

    audit = mgr.audit_seed(active.decoded, active.genome_text)
    ok("audit_seed", "risk_level" in audit)

    shutil.rmtree(home)


def test_recognition():
    print("\n=== 识别工具 ===")

    home = Path(tempfile.mkdtemp())
    mgr = SeedManager(home)
    data = mgr.create_seed("test", "file")
    mgr.seeds_dir  # just a dummy access

    tool = TTGRecognitionTool()

    result = tool.recognize(data, "smart")
    ok("smart recognition", result["is_seed"] and result["confidence"] >= 0.9)

    result = tool.recognize(data, "simple")
    ok("simple recognition", result["is_seed"])

    result = tool.recognize(data, "basic")
    ok("basic recognition", result["is_seed"])

    preview = tool.get_preview(data)
    ok("preview has magic", preview["has_magic"])

    result = tool.recognize(b"This is not a seed file at all.", "smart")
    ok("non-seed rejected", not result["is_seed"])

    shutil.rmtree(home)


def test_ancestral_migration():
    print("\n=== 始祖迁移 ===")

    from migrate_ancestral import parse_ancestral_ttg, convert_ancestral

    ancestral_path = "/Users/audrey/ptg-agent/seeds/teach-to-grow-core.ttg"
    if not Path(ancestral_path).exists():
        ok("ancestral file found", False, "skipped: file not at expected path")
        return

    ok("ancestral file found", True)

    data = parse_ancestral_ttg(ancestral_path)
    ok("parse life_crest", "life_crest" in data)
    ok("parse genealogy_codex", "genealogy_codex" in data)
    ok("parse skill_soul", "skill_soul" in data)
    ok("parse life_id", "TTG@L1-G1-ORIGIN" in data.get("life_crest", {}).get("life_id", ""))

    dst = "/tmp/integration_test_ancestral.seed"
    seed_bytes = convert_ancestral(ancestral_path, dst)
    ok("conversion", len(seed_bytes) > 500, f"{len(seed_bytes)} bytes")

    home = Path(tempfile.mkdtemp())
    mgr = SeedManager(home)
    dormant = mgr.awaken(dst)
    ok("awaken converted", isinstance(dormant, DormantSeed))

    identity = dormant.identity
    ok("converted life_id", "TTG@L1-G1-ORIGIN" in identity["life_id"])
    ok("converted sacred_name", identity["sacred_name"] == "诸技之母")

    active = dormant.water(confirm=False, force=True)
    ok("converted activation", active.is_active)

    if active.is_active:
        epic = mgr.read_epic(active)
        ok("converted epic", "诸技之母" in epic and "Agent Ana" in epic)

    decoded = active.decoded
    sl = decoded.skill_soul
    ok("converted capabilities", len(sl.get("core_capabilities", [])) > 0)
    ok("converted principles", len(sl.get("core_principles", [])) > 0)
    ok("converted taboos", len(sl.get("taboos", [])) > 0)

    dn = decoded.dna_encoding
    ok("converted dna gene_loci", len(dn.get("gene_loci", [])) >= 8)

    gx = decoded.genealogy_codex
    ok("converted tag_lexicon", len(gx.get("tag_lexicon", {})) >= 7)
    ok("converted evolution", len(gx.get("evolution_chronicle", {}).get("generations", [])) > 0)

    tx = decoded.transmission_chronicle
    ok("converted transmission", len(tx) > 0)

    shutil.rmtree(home)
    os.unlink(dst) if os.path.exists(dst) else None


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Prometheus 种子系统 · 集成测试        ║")
    print("╚══════════════════════════════════════════╝")

    test_format_engine()
    test_genome_codec()
    test_soul_analyzer()
    test_dormancy_and_audit()
    test_growth_tracker()
    test_genealogy_keeper()
    test_recognition()
    test_seed_manager_full_cycle()
    test_ancestral_migration()

    passed = sum(1 for _, ok_ in RESULTS if ok_)
    failed = sum(1 for _, ok_ in RESULTS if not ok_)
    total = len(RESULTS)

    print(f"\n{'='*50}")
    print(f"测试结果: {total} 项 | 通过: {passed} | 失败: {failed}")

    if failed == 0:
        print("🎉 全部通过！")
    else:
        print(f"⚠️  {failed} 项失败:")
        for name, ok_ in RESULTS:
            if not ok_:
                print(f"   ❌ {name}")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
