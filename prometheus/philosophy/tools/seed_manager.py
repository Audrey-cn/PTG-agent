#!/usr/bin/env python3
"""
统一种子管理器 · Prometheus 种子系统唯一入口

整合：格式引擎 / 编解码器 / 灵魂分析 / 族谱 / 休眠 / 审计 / 生长 / 生态
支持可替换标签词典实现多元解读。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import uuid
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

from ttg_file_structure import (
    SeedHeader,
    TTGFileStructure,
    create_seed_file,
    read_seed_file,
)
from genome_encoder import encode_genome
from genome_decoder import GenomeDecoder, DecodedGenome
from soul_analyzer import SoulAnalyzer
from genealogy_keeper import GenealogyKeeper
from dormancy_guardian import DormancyGuardian
from safety_auditor import SafetyAuditor
from growth_tracker import GrowthTracker
from self_gardener import SelfGardener

logger = logging.getLogger(__name__)

DEFAULT_LEXICON_PATH = Path(__file__).parent / "tag_lexicon_standard.yaml"


class DormantSeed:
    """休眠态种子对象——load_seed() / awaken() 的返回类型"""

    def __init__(self, data: bytes, header: SeedHeader, genome_text: str,
                 manager: SeedManager):
        self._data = data
        self._header = header
        self._genome_text = genome_text
        self._manager = manager
        self._guardian = self._build_guardian()

    def _build_guardian(self) -> DormancyGuardian:
        decoded = self._manager.decoder.decode(self._genome_text)
        return DormancyGuardian(
            life_crest=decoded.life_crest,
            genealogy=decoded.genealogy_codex.get("current_genealogy", {}),
            founder_chronicle=decoded.life_crest.get("founder_chronicle", {}),
            tag_lexicon=self._manager.decoder.lexicon,
        )

    @property
    def header(self) -> SeedHeader:
        return self._header

    @property
    def genome_text(self) -> str:
        return self._genome_text

    @property
    def identity(self) -> dict:
        return self._guardian.get_identity()

    @property
    def dormancy_message(self) -> str:
        return self._guardian.display_identity()

    @property
    def water_prompt(self) -> str:
        return self._guardian.water_request_prompt()

    @property
    def prefix(self) -> str:
        return TTGFileStructure.extract_prefix(self._data)

    def water(self, confirm: bool = True, force: bool = False) -> ActiveSeed:
        """浇水激活：运行安全审计 → 通过后苏醒"""
        decoded = self._manager.decoder.decode(self._genome_text)

        auditor = SafetyAuditor(
            life_crest=decoded.life_crest,
            genealogy=decoded.genealogy_codex.get("current_genealogy", {}),
            skill_soul=decoded.skill_soul,
            dna=decoded.dna_encoding,
            genome_text=self._genome_text,
        )
        audit_result = auditor.full_audit()
        report = auditor.generate_report(audit_result, self.identity)
        risk = audit_result.get("risk_level", "UNKNOWN")

        if risk == "CRITICAL":
            return ActiveSeed(
                state="locked", decoded=decoded,
                audit_result=audit_result, audit_report=report,
                reason="CRITICAL风险，种子已锁定",
            )

        if risk == "HIGH" and not force:
            return ActiveSeed(
                state="awaiting_confirmation", decoded=decoded,
                audit_result=audit_result, audit_report=report,
                reason="HIGH风险，需force=True确认",
            )

        if risk == "MEDIUM" and confirm:
            return ActiveSeed(
                state="awaiting_confirmation", decoded=decoded,
                audit_result=audit_result, audit_report=report,
                reason="MEDIUM风险，请审阅报告后以confirm=False浇水",
            )

        self._guardian.record_activation()

        return ActiveSeed(
            state="active", decoded=decoded,
            audit_result=audit_result, audit_report=report,
            genome_text=self._genome_text,
            header=self._header,
        )


class ActiveSeed:
    """激活态种子对象——water() 成功后的返回类型"""

    def __init__(self, state: str, decoded: DecodedGenome = None,
                 audit_result: dict = None, audit_report: str = "",
                 reason: str = "", genome_text: str = "",
                 header: SeedHeader = None):
        self.state = state
        self.decoded = decoded or DecodedGenome()
        self.audit_result = audit_result or {}
        self.audit_report = audit_report
        self.reason = reason
        self.genome_text = genome_text
        self.header = header

    @property
    def is_active(self) -> bool:
        return self.state == "active"

    @property
    def life_id(self) -> str:
        return self.decoded.life_crest.get("life_id", "")

    @property
    def sacred_name(self) -> str:
        return self.decoded.life_crest.get("sacred_name", "")


class SeedManager:
    """统一种子管理器"""

    def __init__(self, prometheus_home: Path, decoder_lexicon: str = "standard"):
        self.prometheus_home = prometheus_home
        self.seeds_dir = prometheus_home / "seeds"
        self._init_directories()
        self._lexicon = self._load_lexicon(decoder_lexicon)
        self.decoder = GenomeDecoder(lexicon=self._lexicon, perspective=decoder_lexicon)
        self.decoder_perspective = decoder_lexicon

    def _load_lexicon(self, name: str) -> dict:
        """加载标签词典"""
        if name == "standard":
            path = DEFAULT_LEXICON_PATH
        else:
            path = Path(name)
            if not path.exists():
                path = Path(__file__).parent / f"tag_lexicon_{name}.yaml"

        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get("lexicon", {}) if data else {}
        return {}

    def _init_directories(self):
        for sub in ["files", "projects", "skills", "concepts", "workflows", "datasets", "models"]:
            (self.seeds_dir / sub).mkdir(parents=True, exist_ok=True)

    def awaken(self, seed_path: str) -> DormantSeed:
        """加载种子 → 返回休眠态。不解码内容，仅展示身份。"""
        path = Path(seed_path)
        if not path.exists():
            raise FileNotFoundError(f"种子文件不存在: {seed_path}")

        with open(path, 'rb') as f:
            data = f.read()

        header, genome_text = read_seed_file(data)
        return DormantSeed(data, header, genome_text, self)

    def create_seed(self, entity: Any, entity_type: str,
                    target_quality: str = "standard",
                    auto_analyze: bool = True) -> bytes:
        """
        创建新种子

        Args:
            entity: 原始实体（文本内容、文件路径等）
            entity_type: 实体类型
            target_quality: 质量等级
            auto_analyze: 是否自动运行灵魂分析

        Returns:
            完整的种子文件字节
        """
        logger.info(f"创建种子: type={entity_type}, quality={target_quality}")

        seed_data = self._build_seed_data(entity, entity_type, target_quality)

        if auto_analyze and isinstance(entity, str):
            soul = SoulAnalyzer.analyze(entity, entity_type)
            seed_data["skill_soul"] = {
                "core_capabilities": [
                    {"name": c["name"], "description": c["description"], "immutable": c.get("immutable", True)}
                    for c in soul.core_capabilities
                ],
                "core_principles": soul.core_principles,
                "taboos": soul.taboos,
                "essence": soul.essence,
            }

        genome_text = encode_genome(seed_data)

        header = SeedHeader(
            life_id=seed_data["life_crest"]["life_id"],
            era="壹",
            gene_tally=len(seed_data.get("dna_encoding", {}).get("gene_loci", [])),
            founder_tags=seed_data.get("life_crest", {}).get("founder_chronicle", {}).get("tags", []),
        )

        seed_bytes = create_seed_file(header, genome_text)

        seed_path = self.seeds_dir / entity_type / f"{header.life_id.split('@')[-1]}.seed"
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        with open(seed_path, 'wb') as f:
            f.write(seed_bytes)

        logger.info(f"种子创建完成: {seed_path} ({len(seed_bytes)} 字节)")
        return seed_bytes

    def load_seed(self, path: str) -> DormantSeed:
        """加载种子文件 → 休眠态。等同于 awaken()。"""
        return self.awaken(path)

    def read_epic(self, active: ActiveSeed) -> str:
        """用当前解码器视角渲染史诗叙事"""
        if not active.genome_text:
            return ""
        return self.decoder.render_epic(active.genome_text)

    def change_perspective(self, lexicon_name: str):
        """切换解读视角"""
        self._lexicon = self._load_lexicon(lexicon_name)
        self.decoder = GenomeDecoder(lexicon=self._lexicon, perspective=lexicon_name)
        self.decoder_perspective = lexicon_name

    def analyze_soul(self, content: str, name: str = "unknown") -> dict:
        report = SoulAnalyzer.analyze(content, name)
        return {
            "capabilities": report.core_capabilities,
            "principles": report.core_principles,
            "taboos": report.taboos,
            "essence": report.essence,
        }

    def track_growth(self, seed_id: str) -> GrowthTracker:
        return GrowthTracker(seed_id)

    def show_genealogy(self, decoded: DecodedGenome) -> str:
        gx = decoded.genealogy_codex
        bloodline = (gx.get("bloodline_registry", [{}]) or [{}])[0]
        generations = gx.get("evolution_chronicle", {}).get("generations", [])
        keeper = GenealogyKeeper(tag_lexicon=self._lexicon)
        return keeper.render_lineage_tree(bloodline, generations)

    def audit_seed(self, decoded: DecodedGenome, genome_text: str) -> dict:
        auditor = SafetyAuditor(
            life_crest=decoded.life_crest,
            genealogy=decoded.genealogy_codex.get("current_genealogy", {}),
            skill_soul=decoded.skill_soul,
            dna=decoded.dna_encoding,
            genome_text=genome_text,
        )
        return auditor.full_audit()

    def package_offspring(self, parent_active: ActiveSeed,
                           innovations: List[dict], creator: str,
                           variant_name: str) -> bytes:
        """从父种打包新一代种子"""
        parent_decoded = parent_active.decoded
        parent_lc = parent_decoded.life_crest
        parent_gx = parent_decoded.genealogy_codex

        keeper = GenealogyKeeper(tag_lexicon=self._lexicon)

        tags = [i.get("name", "")[:20] for i in innovations]
        tags = [t for t in tags if t]

        offspring = keeper.create_offspring_lineage(
            parent_crest=parent_lc,
            parent_gx=parent_gx,
            variant_name=variant_name,
            tags=tags,
            creator=creator,
        )

        new_data = parent_decoded.to_dict()
        new_data["life_crest"]["life_id"] = offspring["life_id"]
        new_data["genealogy_codex"]["current_genealogy"] = offspring["genealogy"]

        ev = new_data.get("genealogy_codex", {}).get("evolution_chronicle", {})
        if "generations" not in ev:
            ev["generations"] = []
        ev["generations"].append(offspring["compressed_gen"])

        if innovations:
            inno_list = [
                {"name": i.get("name", ""), "reason": i.get("reason", ""),
                 "implementation": i.get("implementation", ""), "effect": i.get("effect", "")}
                for i in innovations
            ]
            new_data["skill_soul"]["local_innovations"] = inno_list

        genome_text = encode_genome(new_data)

        header = SeedHeader(
            life_id=offspring["life_id"],
            era=self._era_for_generation(offspring["genealogy"]["generation"]),
            gene_tally=len(new_data.get("dna_encoding", {}).get("gene_loci", [])),
            founder_tags=parent_lc.get("founder_chronicle", {}).get("tags", []),
        )

        return create_seed_file(header, genome_text)

    def list_seeds(self, entity_type: str = None) -> list:
        results = []
        dirs = [self.seeds_dir / entity_type] if entity_type else [
            d for d in self.seeds_dir.iterdir() if d.is_dir()
        ]
        for d in dirs:
            if not d.exists():
                continue
            for f in d.glob("*.seed"):
                try:
                    with open(f, 'rb') as fh:
                        header = TTGFileStructure.get_header_only(fh.read())
                    results.append({
                        "path": str(f), "life_id": header.life_id,
                        "era": header.era, "gene_tally": header.gene_tally,
                    })
                except Exception:
                    pass
        return results

    def ecosystem_scan(self, my_life_id: str = "") -> str:
        gardener = SelfGardener(str(self.seeds_dir))
        return gardener.ecosystem_report(my_life_id)

    def _build_seed_data(self, entity: Any, entity_type: str,
                          target_quality: str) -> dict:
        life_id = self._generate_life_id(entity_type)
        now = datetime.datetime.now().isoformat()

        return {
            "life_crest": {
                "life_id": life_id,
                "sacred_name": entity_type,
                "vernacular_name": str(entity)[:50] if isinstance(entity, str) else entity_type,
                "epithet": "",
                "genesis": {
                    "creator": {"name": "Prometheus", "title": "种子管理器", "lineage": "L1"},
                    "birth_time": now,
                    "birth_place": os.uname().nodename if hasattr(os, 'uname') else "unknown",
                    "birth_circumstance": f"由 SeedManager 创建于 {now}",
                    "purpose": f"授{entity_type}以生长之道",
                },
                "mission": "",
                "founder_chronicle": {
                    "tags": [],
                    "genesis_moment": {"ep": f"Y{datetime.datetime.now().year}-D{datetime.datetime.now().timetuple().tm_yday}",
                                        "loc": "?", "realm": "Prometheus", "era": "创世纪元"},
                },
            },
            "genealogy_codex": {
                "lineage_laws": {
                    "naming_convention": {"format": "L{lineage}-G{gen}-{variant}-{checksum}"},
                    "fork_conditions": [{"condition": "env_change"}, {"condition": "major_innovation"}],
                    "eternal_rules": ["append_only", "no_deletion", "trace_to_origin"],
                },
                "bloodline_registry": [],
                "current_genealogy": {
                    "lineage": "L1", "bloodline": "?", "generation": 1,
                    "variant": "ORIGIN", "variant_epithet": "",
                    "parent": None, "ancestors": [], "descendants": [],
                    "birthplace": "",
                },
                "tag_lexicon": {},
                "evolution_chronicle": {"generations": [
                    {"g": 1, "v": "ORIGIN", "ep": "", "env": "?", "tags": [], "by": "?", "p": None}
                ]},
            },
            "skill_soul": {
                "core_capabilities": [],
                "core_principles": [],
                "taboos": [],
                "essence": {"vibe": "", "tone": "", "role": "", "oath": ""},
            },
            "dna_encoding": {"version": "1.0", "gene_loci": []},
            "transmission_chronicle": [],
            "evolution_chronicle": [],
        }

    def _generate_life_id(self, entity_type: str) -> str:
        checksum = hashlib.md5(
            f"{entity_type}-{datetime.datetime.now().isoformat()}-{uuid.uuid4()}".encode()
        ).hexdigest()[:8].upper()
        return f"TTG@L1-G1-{entity_type[:4].upper()}-{checksum}"

    @staticmethod
    def _era_for_generation(gen: int) -> str:
        eras = {"1": "壹", "2": "貳", "3": "參", "4": "肆", "5": "伍"}
        return eras.get(str(gen), "壹")


def main():
    """命令行入口"""
    import sys

    if len(sys.argv) < 2:
        print("用法: python seed_manager.py <command> [args...]")
        print("  awaken <seed_path>     - 加载种子（休眠态）")
        print("  create <entity> <type>  - 创建新种子")
        print("  list [entity_type]     - 列出种子")
        print("  epic <seed_path>       - 渲染史诗")
        sys.exit(1)

    mgr = SeedManager(Path.home() / ".prometheus")
    cmd = sys.argv[1]

    if cmd == "awaken" and len(sys.argv) > 2:
        dormant = mgr.awaken(sys.argv[2])
        print(dormant.dormancy_message)
        print(f"\n前缀:\n{dormant.prefix}")

    elif cmd == "create" and len(sys.argv) > 3:
        data = mgr.create_seed(sys.argv[2], sys.argv[3])
        print(f"种子创建完成: {len(data)} 字节")

    elif cmd == "list":
        et = sys.argv[2] if len(sys.argv) > 2 else None
        for s in mgr.list_seeds(et):
            print(f"  {s['life_id']} @ {s['path']}")

    elif cmd == "epic" and len(sys.argv) > 2:
        dormant = mgr.awaken(sys.argv[2])
        active = dormant.water(confirm=False, force=True)
        if active.is_active:
            print(mgr.read_epic(active))

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
