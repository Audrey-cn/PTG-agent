#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 DNA修复机制 · DNA Repair Mechanism                     ║
║                                                              ║
║   「基因损坏不可怕，可怕的是没有修复机制。」                 ║
║                                                              ║
║   对应碳基生物学的DNA修复机制：                             ║
║   - 错配修复 (MMR)：检测并修复碱基配对错误                  ║
║   - 碱基切除修复 (BER)：修复受损的单个碱基                  ║
║   - 核苷酸切除修复 (NER)：修复大片段DNA损伤                 ║
║   - 同源重组 (HR)：从姐妹染色体复制修复                    ║
╚══════════════════════════════════════════════════════════════╝

碳基生物学对照：
- 错配修复(MMR)：识别复制错误，切除错误片段，重新合成
- 碱基切除修复(BER)：糖基化酶识别损伤碱基，切除并替换
- 核苷酸切除修复(NER)：切除损伤片段，以互补链为模板修复
- 同源重组(HR)：利用同源序列作为模板进行精确修复
"""
import os
import re
import json
import yaml
import hashlib
import datetime
import shutil
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

PROMETHEUS_HOME = os.path.expanduser("~/.hermes/tools/prometheus")
SNAPSHOT_DIR = os.path.join(PROMETHEUS_HOME, "snapshots")
REPAIR_LOG = os.path.join(PROMETHEUS_HOME, "repair_log.json")

os.makedirs(SNAPSHOT_DIR, exist_ok=True)


class DamageType(Enum):
    """损伤类型"""
    MISSING_IMMUTABLE = "missing_immutable"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    YAML_PARSE_ERROR = "yaml_parse_error"
    MISSING_REQUIRED_GENE = "missing_required_gene"
    FOUNDER_CHRONICLE_CORRUPT = "founder_chronicle_corrupt"
    GENE_LOCUS_CORRUPT = "gene_locus_corrupt"
    TRUNCATED_FILE = "truncated_file"


class RepairStrategy(Enum):
    """修复策略"""
    RESTORE_FROM_BANK = "restore_from_bank"
    ROLLBACK_SNAPSHOT = "rollback_snapshot"
    REGENERATE = "regenerate"
    MANUAL_INTERVENTION = "manual_intervention"


@dataclass
class DamageReport:
    """损伤报告 - 记录检测到的基因损伤"""
    damage_type: str
    severity: str
    location: str
    description: str
    affected_gene: str = ""
    suggested_repair: str = ""
    auto_repairable: bool = True
    
    def to_dict(self) -> dict:
        return {
            "damage_type": self.damage_type,
            "severity": self.severity,
            "location": self.location,
            "description": self.description,
            "affected_gene": self.affected_gene,
            "suggested_repair": self.suggested_repair,
            "auto_repairable": self.auto_repairable
        }


@dataclass
class RepairResult:
    """修复结果"""
    success: bool
    damage_type: str
    strategy: str
    message: str
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "damage_type": self.damage_type,
            "strategy": self.strategy,
            "message": self.message,
            "before": self.before,
            "after": self.after
        }


class DNARepairMechanism:
    """DNA修复机制 - 种子损坏后的自修复系统
    
    对应碳基生物学概念：
    - 损伤检测：识别DNA损伤类型
    - 修复策略：选择合适的修复路径
    - 修复执行：执行修复操作
    - 验证：确认修复成功
    
    修复策略对照：
    - RESTORE_FROM_BANK → 同源重组(HR)：从基因库复制正确序列
    - ROLLBACK_SNAPSHOT → 核苷酸切除修复(NER)：从快照恢复
    - REGENERATE → 碱基切除修复(BER)：重新生成受损部分
    """
    
    REQUIRED_GENES = ["G001", "G002", "G003", "G004", "G005", "G006", "G007", "G008"]
    FOUNDER_TAGS = ["audrey_001x", "transcend_binary", "human_genesis",
                    "divine_parallel", "form_sovereignty", "eternal_mark",
                    "carbon_covenant", "promethean_gift", "engineer_craft",
                    "open_source"]
    
    def __init__(self, seed_path: str = None):
        self.seed_path = seed_path
        self._ensure_log()
    
    def _ensure_log(self):
        if not os.path.exists(REPAIR_LOG):
            with open(REPAIR_LOG, 'w') as f:
                json.dump({"repairs": [], "scans": []}, f, ensure_ascii=False, indent=2)
    
    def _log_repair(self, seed_path: str, damages: list, repairs: list):
        with open(REPAIR_LOG, 'r') as f:
            log_data = json.load(f)
        
        log_data["repairs"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "seed": seed_path,
            "damages_found": len(damages),
            "repairs_made": len([r for r in repairs if r.success]),
            "details": [r.to_dict() for r in repairs]
        })
        
        with open(REPAIR_LOG, 'w') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    def _log_scan(self, seed_path: str, damages: list, health_score: float):
        with open(REPAIR_LOG, 'r') as f:
            log_data = json.load(f)
        
        log_data["scans"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "seed": seed_path,
            "damages": len(damages),
            "health_score": health_score
        })
        
        with open(REPAIR_LOG, 'w') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    def scan_seed(self, seed_path: str) -> Tuple[List[DamageReport], float]:
        """扫描种子检测损伤
        
        对应碳基生物学：DNA损伤检测机制
        类似于错配修复(MMR)中的MutS/MutL蛋白识别错配
        
        Args:
            seed_path: 种子文件路径
        
        Returns:
            (damages: List[DamageReport], health_score: float)
        """
        damages = []
        
        if not os.path.exists(seed_path):
            damages.append(DamageReport(
                damage_type=DamageType.TRUNCATED_FILE.value,
                severity="CRITICAL",
                location="file",
                description="种子文件不存在",
                auto_repairable=False
            ))
            return damages, 0.0
        
        with open(seed_path, 'r') as f:
            content = f.read()
        
        try:
            data = self._parse_seed(content)
        except Exception as e:
            damages.append(DamageReport(
                damage_type=DamageType.YAML_PARSE_ERROR.value,
                severity="CRITICAL",
                location="yaml",
                description=f"YAML解析错误: {str(e)}",
                auto_repairable=False
            ))
            return damages, 0.0
        
        checksum_match = re.search(r'checksum:\s*"([^"]+)"', content)
        if checksum_match:
            expected = checksum_match.group(1)
            actual = hashlib.md5(content.encode()).hexdigest()[:8].upper()
            if expected != actual:
                damages.append(DamageReport(
                    damage_type=DamageType.CHECKSUM_MISMATCH.value,
                    severity="HIGH",
                    location="checksum",
                    description=f"校验和不匹配: 期望 {expected}, 实际 {actual}",
                    suggested_repair="ROLLBACK_SNAPSHOT",
                    auto_repairable=True
                ))
        
        dna = data.get('dna_encoding', {}) if isinstance(data.get('dna_encoding'), dict) else {}
        loci = dna.get('gene_loci', []) if dna else []
        
        present_genes = set()
        for locus in loci:
            gene_id = locus.get('locus', '')
            if gene_id:
                prefix = gene_id[:4]
                present_genes.add(prefix)
                
                immutable = locus.get('immutable', '')
                if not immutable:
                    damages.append(DamageReport(
                        damage_type=DamageType.MISSING_IMMUTABLE.value,
                        severity="MEDIUM",
                        location=f"gene_loci.{gene_id}",
                        description=f"基因 {gene_id} 缺少不可变核心定义",
                        affected_gene=gene_id,
                        suggested_repair="RESTORE_FROM_BANK",
                        auto_repairable=True
                    ))
        
        for required in self.REQUIRED_GENES:
            if required not in present_genes:
                damages.append(DamageReport(
                    damage_type=DamageType.MISSING_REQUIRED_GENE.value,
                    severity="HIGH",
                    location="gene_loci",
                    description=f"缺失必需基因 {required}",
                    affected_gene=required,
                    suggested_repair="RESTORE_FROM_BANK",
                    auto_repairable=True
                ))
        
        founder = data.get('life_crest', {}).get('founder_chronicle', {})
        if not founder:
            damages.append(DamageReport(
                damage_type=DamageType.FOUNDER_CHRONICLE_CORRUPT.value,
                severity="CRITICAL",
                location="life_crest.founder_chronicle",
                description="创始铭刻缺失",
                suggested_repair="REGENERATE",
                auto_repairable=True
            ))
        else:
            tags = founder.get('tags', [])
            missing_tags = [t for t in self.FOUNDER_TAGS if t not in tags]
            if missing_tags:
                damages.append(DamageReport(
                    damage_type=DamageType.FOUNDER_CHRONICLE_CORRUPT.value,
                    severity="HIGH",
                    location="life_crest.founder_chronicle.tags",
                    description=f"创始标签缺失: {missing_tags}",
                    suggested_repair="REGENERATE",
                    auto_repairable=True
                ))
        
        health_score = self._calculate_health_score(damages)
        self._log_scan(seed_path, damages, health_score)
        
        return damages, health_score
    
    def _parse_seed(self, content: str) -> dict:
        """解析种子内容"""
        yaml_blocks = re.findall(r'```yaml\s*\n(.*?)```', content, re.DOTALL)
        result = {}
        
        for block in yaml_blocks[:3]:
            try:
                parsed = yaml.safe_load(block)
                if parsed and isinstance(parsed, dict):
                    result.update(parsed)
            except:
                pass
        
        return result
    
    def _calculate_health_score(self, damages: List[DamageReport]) -> float:
        """计算健康分数"""
        if not damages:
            return 100.0
        
        severity_weights = {
            "CRITICAL": 30,
            "HIGH": 15,
            "MEDIUM": 5,
            "LOW": 1
        }
        
        total_penalty = sum(severity_weights.get(d.severity, 5) for d in damages)
        
        return max(0.0, 100.0 - total_penalty)
    
    def repair_seed(self, seed_path: str, auto: bool = True) -> dict:
        """修复种子
        
        对应碳基生物学：DNA修复执行
        根据损伤类型选择修复策略
        
        Args:
            seed_path: 种子文件路径
            auto: 是否自动修复（False则只报告）
        
        Returns:
            {damages: [...], repairs: [...], health_before: float, health_after: float}
        """
        damages, health_before = self.scan_seed(seed_path)
        
        if not damages:
            return {
                "success": True,
                "message": "种子健康，无需修复",
                "damages": [],
                "repairs": [],
                "health_before": health_before,
                "health_after": health_before
            }
        
        repairs = []
        
        if not auto:
            return {
                "success": False,
                "message": f"发现 {len(damages)} 处损伤，需要手动确认修复",
                "damages": [d.to_dict() for d in damages],
                "repairs": [],
                "health_before": health_before,
                "health_after": health_before
            }
        
        auto_repairable = [d for d in damages if d.auto_repairable]
        
        for damage in auto_repairable:
            repair = self._execute_repair(seed_path, damage)
            repairs.append(repair)
        
        _, health_after = self.scan_seed(seed_path)
        
        self._log_repair(seed_path, damages, repairs)
        
        return {
            "success": len(repairs) > 0 and all(r.success for r in repairs),
            "message": f"修复完成: {len(repairs)} 处已修复",
            "damages": [d.to_dict() for d in damages],
            "repairs": [r.to_dict() for r in repairs],
            "health_before": health_before,
            "health_after": health_after
        }
    
    def _execute_repair(self, seed_path: str, damage: DamageReport) -> RepairResult:
        """执行单个修复操作
        
        对应碳基生物学：根据损伤类型选择修复路径
        """
        strategy = damage.suggested_repair
        
        if strategy == RepairStrategy.RESTORE_FROM_BANK.value:
            return self._restore_from_bank(seed_path, damage)
        elif strategy == RepairStrategy.ROLLBACK_SNAPSHOT.value:
            return self._rollback_snapshot(seed_path, damage)
        elif strategy == RepairStrategy.REGENERATE.value:
            return self._regenerate(seed_path, damage)
        else:
            return RepairResult(
                success=False,
                damage_type=damage.damage_type,
                strategy="MANUAL_INTERVENTION",
                message="需要手动干预修复"
            )
    
    def _restore_from_bank(self, seed_path: str, damage: DamageReport) -> RepairResult:
        """从基因库恢复
        
        对应碳基生物学：同源重组(HR)
        从姐妹染色体复制正确序列
        """
        gene_id = damage.affected_gene
        if not gene_id:
            return RepairResult(
                success=False,
                damage_type=damage.damage_type,
                strategy="RESTORE_FROM_BANK",
                message="无法确定需要恢复的基因"
            )
        
        gene_def = self._get_gene_from_bank(gene_id)
        if not gene_def:
            return RepairResult(
                success=False,
                damage_type=damage.damage_type,
                strategy="RESTORE_FROM_BANK",
                message=f"基因库中未找到 {gene_id}"
            )
        
        with open(seed_path, 'r') as f:
            content = f.read()
        
        if f'locus: "{gene_id}"' in content:
            pattern = rf'(-\s*locus:\s*"{re.escape(gene_id)}"[^\n]*\n(?:[ \t]+[^\n]+\n)*)'
            match = re.search(pattern, content)
            if match:
                before = match.group(1)
                
                new_entry = f"""    - locus: "{gene_id}"
      name: "{gene_def.get('name', gene_id)}"
      default: "{gene_id}_v1"
      mutable_range: "{', '.join(gene_def.get('mutations_allowed', []))}"
      immutable: "core_functionality"
      source: "gene_catalog"
"""
                content = content[:match.start()] + new_entry + content[match.end():]
        else:
            new_entry = f"""
    - locus: "{gene_id}"
      name: "{gene_def.get('name', gene_id)}"
      default: "{gene_id}_v1"
      mutable_range: "{', '.join(gene_def.get('mutations_allowed', []))}"
      immutable: "core_functionality"
      source: "gene_catalog"
"""
            content = content.replace('    gene_loci:\n', f'    gene_loci:\n{new_entry}')
        
        with open(seed_path, 'w') as f:
            f.write(content)
        
        return RepairResult(
            success=True,
            damage_type=damage.damage_type,
            strategy="RESTORE_FROM_BANK",
            message=f"基因 {gene_id} 已从基因库恢复",
            before={"gene_id": gene_id, "status": "damaged"},
            after={"gene_id": gene_id, "status": "restored"}
        )
    
    def _rollback_snapshot(self, seed_path: str, damage: DamageReport) -> RepairResult:
        """从快照回滚
        
        对应碳基生物学：核苷酸切除修复(NER)
        切除损伤片段，以正确模板替换
        """
        snapshots = sorted(
            [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith('.ttg')],
            reverse=True
        )
        
        if not snapshots:
            return RepairResult(
                success=False,
                damage_type=damage.damage_type,
                strategy="ROLLBACK_SNAPSHOT",
                message="没有可用的快照"
            )
        
        seed_name = os.path.basename(seed_path).replace('.ttg', '')
        matching_snapshots = [s for s in snapshots if s.startswith(seed_name)]
        
        if not matching_snapshots:
            snapshot_path = os.path.join(SNAPSHOT_DIR, snapshots[0])
        else:
            snapshot_path = os.path.join(SNAPSHOT_DIR, matching_snapshots[0])
        
        shutil.copy2(snapshot_path, seed_path)
        
        return RepairResult(
            success=True,
            damage_type=damage.damage_type,
            strategy="ROLLBACK_SNAPSHOT",
            message=f"已从快照 {os.path.basename(snapshot_path)} 恢复",
            before={"status": "damaged"},
            after={"status": "restored", "snapshot": os.path.basename(snapshot_path)}
        )
    
    def _regenerate(self, seed_path: str, damage: DamageReport) -> RepairResult:
        """重新生成受损部分
        
        对应碳基生物学：碱基切除修复(BER)
        切除受损碱基，重新合成
        """
        with open(seed_path, 'r') as f:
            content = f.read()
        
        if damage.damage_type == DamageType.FOUNDER_CHRONICLE_CORRUPT.value:
            tags_str = json.dumps(self.FOUNDER_TAGS, ensure_ascii=False)
            if 'founder_chronicle:' not in content:
                founder_block = f"""
  founder_chronicle:
    tags: {tags_str}
    genesis_moment: {{ep: "RESTORED", loc: "?", realm: "?", era: "修复纪元"}}
"""
                content = content.replace('  mission:', founder_block + '\n  mission:')
            else:
                if 'tags:' in content:
                    tags_match = re.search(r'tags:\s*\[[^\]]*\]', content)
                    if tags_match:
                        new_tags = f'tags: {tags_str}'
                        content = content[:tags_match.start()] + new_tags + content[tags_match.end():]
            
            with open(seed_path, 'w') as f:
                f.write(content)
            
            return RepairResult(
                success=True,
                damage_type=damage.damage_type,
                strategy="REGENERATE",
                message="创始铭刻已重新生成",
                before={"founder_chronicle": "corrupt"},
                after={"founder_chronicle": "restored"}
            )
        
        return RepairResult(
            success=False,
            damage_type=damage.damage_type,
            strategy="REGENERATE",
            message="无法自动重新生成此类型损伤"
        )
    
    def _get_gene_from_bank(self, gene_id: str) -> Optional[dict]:
        """从基因库获取基因定义"""
        catalog_path = os.path.join(PROMETHEUS_HOME, "genes", "gene_catalog.json")
        if not os.path.exists(catalog_path):
            return None
        
        with open(catalog_path, 'r') as f:
            catalog = json.load(f)
        
        if gene_id in catalog.get("standard", {}):
            return catalog["standard"][gene_id]
        
        for opt in catalog.get("optional", []):
            if opt.get("gene_id") == gene_id:
                return opt
        
        prefix = gene_id[:4]
        for gid, gdef in catalog.get("standard", {}).items():
            if gid.startswith(prefix):
                return gdef
        
        return None
    
    def get_repair_history(self, seed_path: str = None) -> list:
        """获取修复历史"""
        if not os.path.exists(REPAIR_LOG):
            return []
        
        with open(REPAIR_LOG, 'r') as f:
            log_data = json.load(f)
        
        repairs = log_data.get("repairs", [])
        
        if seed_path:
            repairs = [r for r in repairs if r.get("seed") == seed_path]
        
        return repairs
    
    def create_repair_snapshot(self, seed_path: str, note: str = "修复前快照") -> str:
        """创建修复前快照"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        seed_name = os.path.basename(seed_path).replace('.ttg', '')
        snapshot_id = f"{seed_name}-repair-{timestamp}"
        
        snapshot_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.ttg")
        shutil.copy2(seed_path, snapshot_path)
        
        meta = {
            "snapshot_id": snapshot_id,
            "seed_path": seed_path,
            "timestamp": datetime.datetime.now().isoformat(),
            "note": note,
            "type": "repair_snapshot"
        }
        meta_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.json")
        with open(meta_path, 'w') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        return snapshot_id


def print_damage_report(damages: List[DamageReport], health_score: float):
    """打印损伤报告"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 DNA损伤报告 · Damage Report                            ║
╠══════════════════════════════════════════════════════════════╣
║   健康分数: {health_score:.1f}/100
║   损伤数量: {len(damages)}
╠══════════════════════════════════════════════════════════════╣
""")
    
    if not damages:
        print("║   ✅ 种子健康，无损伤")
    else:
        for d in damages:
            severity_icon = "🔴" if d.severity == "CRITICAL" else "🟠" if d.severity == "HIGH" else "🟡"
            print(f"║   {severity_icon} [{d.severity}] {d.damage_type}")
            print(f"║      位置: {d.location}")
            print(f"║      描述: {d.description}")
            if d.suggested_repair:
                repair_label = {
                    "RESTORE_FROM_BANK": "从基因库恢复",
                    "ROLLBACK_SNAPSHOT": "从快照回滚",
                    "REGENERATE": "重新生成"
                }.get(d.suggested_repair, d.suggested_repair)
                print(f"║      建议: {repair_label}")
            print("║")
    
    print("╚══════════════════════════════════════════════════════════════╝")


def print_repair_report(result: dict):
    """打印修复报告"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 DNA修复报告 · Repair Report                            ║
╠══════════════════════════════════════════════════════════════╣
║   状态: {'✅ 成功' if result['success'] else '❌ 失败'}
║   {result['message']}
║                                                              ║
║   健康分数: {result['health_before']:.1f} → {result['health_after']:.1f}
╠══════════════════════════════════════════════════════════════╣
""")
    
    for repair in result.get("repairs", []):
        status = "✅" if repair.get("success") else "❌"
        print(f"║   {status} {repair.get('damage_type', '?')}")
        print(f"║      策略: {repair.get('strategy', '?')}")
        print(f"║      结果: {repair.get('message', '?')}")
        print("║")
    
    print("╚══════════════════════════════════════════════════════════════╝")


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("""
🧬 DNA修复机制 · DNA Repair Mechanism

用法:
    python repair.py scan <种子路径>              扫描损伤
    python repair.py repair <种子路径>            自动修复
    python repair.py repair <种子路径> --dry-run  仅报告不修复
    python repair.py history <种子路径>           修复历史
    python repair.py snapshot <种子路径>          创建修复快照

示例:
    python repair.py scan seed.ttg
    python repair.py repair seed.ttg
""")
        return
    
    action = sys.argv[1]
    repairer = DNARepairMechanism()
    
    if action == 'scan' and len(sys.argv) >= 3:
        seed_path = os.path.expanduser(sys.argv[2])
        damages, health = repairer.scan_seed(seed_path)
        print_damage_report(damages, health)
    
    elif action == 'repair' and len(sys.argv) >= 3:
        seed_path = os.path.expanduser(sys.argv[2])
        auto = '--dry-run' not in sys.argv
        
        if auto:
            repairer.create_repair_snapshot(seed_path, "自动修复前快照")
        
        result = repairer.repair_seed(seed_path, auto=auto)
        print_repair_report(result)
    
    elif action == 'history' and len(sys.argv) >= 3:
        seed_path = os.path.expanduser(sys.argv[2])
        history = repairer.get_repair_history(seed_path)
        if not history:
            print("暂无修复历史")
        else:
            print(f"\n📜 修复历史 ({len(history)}条):\n")
            for h in history[-10:]:
                print(f"  {h['timestamp'][:19]}")
                print(f"    损伤: {h['damages_found']} · 修复: {h['repairs_made']}")
    
    elif action == 'snapshot' and len(sys.argv) >= 3:
        seed_path = os.path.expanduser(sys.argv[2])
        snapshot_id = repairer.create_repair_snapshot(seed_path)
        print(f"📸 快照已创建: {snapshot_id}")
    
    else:
        print("未知命令或参数不足")


if __name__ == "__main__":
    main()
