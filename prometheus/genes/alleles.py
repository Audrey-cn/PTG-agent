#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 等位基因系统 · Allele System                           ║
║                                                              ║
║   「同一基因位点，多种表达形态。」                           ║
║                                                              ║
║   对应碳基生物学的等位基因概念：                            ║
║   - 等位基因 (Allele)：同一基因的不同版本                   ║
║   - 显性/隐性：版本间的优先级关系                           ║
║   - 纯合子/杂合子：单版本 vs 多版本共存                     ║
╚══════════════════════════════════════════════════════════════╝

碳基生物学对照：
- 等位基因：位于同源染色体相同位置，控制同一性状的不同形式
- 显性等位：杂合状态下表现出的性状 (dominant)
- 隐性等位：杂合状态下被掩盖的性状 (recessive)
- 共显性：两个等位基因同时表达 (codominant)
"""
import os
import re
import json
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

PROMETHEUS_HOME = os.path.expanduser("~/.hermes/tools/prometheus")
ALLELES_DIR = os.path.join(PROMETHEUS_HOME, "genes", "alleles")
ALLELES_CATALOG = os.path.join(ALLELES_DIR, "alleles_catalog.json")

os.makedirs(ALLELES_DIR, exist_ok=True)


class AlleleType(Enum):
    """等位基因类型 - 对应碳基生物学的显性/隐性/共显性"""
    DOMINANT = "dominant"
    RECESSIVE = "recessive"
    CODOMINANT = "codominant"


@dataclass
class Allele:
    """等位基因 - 同一基因位点的不同版本
    
    对应碳基生物学概念：
    - allele_id: 等位基因标识 (如 v1, v2-fast, v3-strict)
    - allele_type: 显性/隐性/共显性
    - expression_priority: 表达优先级 (显性高优先)
    """
    allele_id: str
    name: str
    description: str = ""
    allele_type: str = "dominant"
    expression_priority: int = 1
    is_default: bool = False
    config: dict = field(default_factory=dict)
    created: str = ""
    
    def __post_init__(self):
        if not self.created:
            self.created = datetime.datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Allele':
        return cls(
            allele_id=data.get('allele_id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            allele_type=data.get('allele_type', 'dominant'),
            expression_priority=data.get('expression_priority', 1),
            is_default=data.get('is_default', False),
            config=data.get('config', {}),
            created=data.get('created', '')
        )


@dataclass
class AllelicLocus:
    """等位基因位点 - 管理一个基因位点的所有等位版本
    
    对应碳基生物学概念：
    - 基因位点可以有多个等位基因
    - 个体在每个位点上有两个等位基因（二倍体）
    - 表现型由等位基因的组合决定
    """
    gene_id: str
    gene_name: str
    alleles: List[Allele] = field(default_factory=list)
    active_allele: str = ""
    last_switched: str = ""
    switch_history: List[dict] = field(default_factory=list)
    
    def get_active_allele(self) -> Optional[Allele]:
        """获取当前激活的等位基因"""
        for a in self.alleles:
            if a.allele_id == self.active_allele:
                return a
        if self.alleles:
            default = next((a for a in self.alleles if a.is_default), None)
            return default or self.alleles[0]
        return None
    
    def get_default_allele(self) -> Optional[Allele]:
        """获取默认等位基因"""
        for a in self.alleles:
            if a.is_default:
                return a
        return self.alleles[0] if self.alleles else None
    
    def to_dict(self) -> dict:
        return {
            "gene_id": self.gene_id,
            "gene_name": self.gene_name,
            "alleles": [a.to_dict() for a in self.alleles],
            "active_allele": self.active_allele,
            "last_switched": self.last_switched,
            "switch_history": self.switch_history
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AllelicLocus':
        alleles = [Allele.from_dict(a) for a in data.get('alleles', [])]
        return cls(
            gene_id=data.get('gene_id', ''),
            gene_name=data.get('gene_name', ''),
            alleles=alleles,
            active_allele=data.get('active_allele', ''),
            last_switched=data.get('last_switched', ''),
            switch_history=data.get('switch_history', [])
        )


class AlleleManager:
    """等位基因管理器 - 管理基因的多版本切换
    
    核心功能：
    - register_allele(): 注册新的等位基因版本
    - switch_allele(): 切换激活的等位基因
    - get_active_allele(): 获取当前激活版本
    - list_alleles(): 列出所有可用版本
    """
    
    def __init__(self):
        self._ensure_catalog()
    
    def _ensure_catalog(self):
        if not os.path.exists(ALLELES_CATALOG):
            with open(ALLELES_CATALOG, 'w') as f:
                json.dump({"loci": {}}, f, ensure_ascii=False, indent=2)
    
    def _load_catalog(self) -> dict:
        with open(ALLELES_CATALOG, 'r') as f:
            return json.load(f)
    
    def _save_catalog(self, catalog: dict):
        with open(ALLELES_CATALOG, 'w') as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
    
    def register_allele(self, gene_id: str, gene_name: str, allele: Allele) -> dict:
        """注册新的等位基因版本
        
        Args:
            gene_id: 基因ID (如 G001-parser)
            gene_name: 基因名称
            allele: 等位基因定义
        
        Returns:
            {success: bool, message: str, allele_id: str}
        """
        catalog = self._load_catalog()
        
        if gene_id not in catalog["loci"]:
            catalog["loci"][gene_id] = AllelicLocus(
                gene_id=gene_id,
                gene_name=gene_name
            ).to_dict()
        
        locus_data = catalog["loci"][gene_id]
        locus = AllelicLocus.from_dict(locus_data)
        
        for existing in locus.alleles:
            if existing.allele_id == allele.allele_id:
                return {
                    "success": False,
                    "message": f"等位基因 {allele.allele_id} 已存在于 {gene_id}"
                }
        
        if allele.is_default:
            for a in locus.alleles:
                a.is_default = False
        
        locus.alleles.append(allele)
        
        if not locus.active_allele or allele.is_default:
            locus.active_allele = allele.allele_id
        
        catalog["loci"][gene_id] = locus.to_dict()
        self._save_catalog(catalog)
        
        return {
            "success": True,
            "message": f"等位基因 {allele.allele_id} 已注册到 {gene_id}",
            "gene_id": gene_id,
            "allele_id": allele.allele_id,
            "total_alleles": len(locus.alleles)
        }
    
    def switch_allele(self, seed_path: str, gene_id: str, allele_id: str, 
                      reason: str = "") -> dict:
        """切换种子的等位基因版本
        
        对应碳基生物学：基因表达的版本切换
        类似于可变剪接或启动子切换
        
        Args:
            seed_path: 种子文件路径
            gene_id: 基因ID
            allele_id: 目标等位基因ID
            reason: 切换原因
        
        Returns:
            {success: bool, message: str, from_allele: str, to_allele: str}
        """
        catalog = self._load_catalog()
        
        if gene_id not in catalog["loci"]:
            return {"success": False, "message": f"基因 {gene_id} 没有注册的等位基因"}
        
        locus = AllelicLocus.from_dict(catalog["loci"][gene_id])
        
        target_allele = None
        for a in locus.alleles:
            if a.allele_id == allele_id:
                target_allele = a
                break
        
        if not target_allele:
            return {"success": False, "message": f"等位基因 {allele_id} 不存在于 {gene_id}"}
        
        from_allele = locus.active_allele
        locus.active_allele = allele_id
        locus.last_switched = datetime.datetime.now().isoformat()
        locus.switch_history.append({
            "from": from_allele,
            "to": allele_id,
            "time": locus.last_switched,
            "reason": reason
        })
        
        catalog["loci"][gene_id] = locus.to_dict()
        self._save_catalog(catalog)
        
        if seed_path and os.path.exists(seed_path):
            self._update_seed_allele(seed_path, gene_id, allele_id, target_allele)
        
        return {
            "success": True,
            "message": f"{gene_id} 等位基因已切换: {from_allele} → {allele_id}",
            "gene_id": gene_id,
            "from_allele": from_allele,
            "to_allele": allele_id,
            "allele_info": target_allele.to_dict()
        }
    
    def _update_seed_allele(self, seed_path: str, gene_id: str, 
                            allele_id: str, allele: Allele):
        """更新种子文件中的等位基因配置"""
        with open(seed_path, 'r') as f:
            content = f.read()
        
        pattern = rf'(-\s*locus:\s*"{re.escape(gene_id)}"[^\n]*\n)((?:[ \t]+[^\n]+\n)*)'
        
        def update_allele_field(m):
            locus_line = m.group(1)
            gene_block = m.group(2)
            
            gene_block = re.sub(r'^[ \t]+active_allele:.*$\n?', '', gene_block, flags=re.MULTILINE)
            gene_block = re.sub(r'^[ \t]+allele_config:.*$\n?', '', gene_block, flags=re.MULTILINE)
            
            allele_config_str = ""
            if allele.config:
                config_lines = []
                for k, v in allele.config.items():
                    if isinstance(v, str):
                        config_lines.append(f'          {k}: "{v}"')
                    else:
                        config_lines.append(f'          {k}: {v}')
                allele_config_str = "\n      allele_config:\n" + "\n".join(config_lines) + "\n"
            
            new_fields = f'      active_allele: "{allele_id}"\n{allele_config_str}'
            
            return locus_line + new_fields + gene_block
        
        content = re.sub(pattern, update_allele_field, content)
        
        with open(seed_path, 'w') as f:
            f.write(content)
    
    def get_active_allele(self, gene_id: str) -> dict:
        """获取基因当前激活的等位基因"""
        catalog = self._load_catalog()
        
        if gene_id not in catalog["loci"]:
            return {"error": f"基因 {gene_id} 没有注册的等位基因"}
        
        locus = AllelicLocus.from_dict(catalog["loci"][gene_id])
        active = locus.get_active_allele()
        
        return {
            "gene_id": gene_id,
            "gene_name": locus.gene_name,
            "active_allele": active.to_dict() if active else None,
            "total_alleles": len(locus.alleles)
        }
    
    def list_alleles(self, gene_id: str = None) -> dict:
        """列出所有等位基因"""
        catalog = self._load_catalog()
        
        if gene_id:
            if gene_id not in catalog["loci"]:
                return {"error": f"基因 {gene_id} 没有注册的等位基因"}
            
            locus = AllelicLocus.from_dict(catalog["loci"][gene_id])
            return {
                "gene_id": gene_id,
                "gene_name": locus.gene_name,
                "active_allele": locus.active_allele,
                "alleles": [a.to_dict() for a in locus.alleles]
            }
        
        result = {}
        for gid, locus_data in catalog["loci"].items():
            locus = AllelicLocus.from_dict(locus_data)
            result[gid] = {
                "gene_name": locus.gene_name,
                "active_allele": locus.active_allele,
                "allele_count": len(locus.alleles),
                "alleles": [a.allele_id for a in locus.alleles]
            }
        
        return result
    
    def remove_allele(self, gene_id: str, allele_id: str) -> dict:
        """移除等位基因版本"""
        catalog = self._load_catalog()
        
        if gene_id not in catalog["loci"]:
            return {"success": False, "message": f"基因 {gene_id} 没有注册的等位基因"}
        
        locus = AllelicLocus.from_dict(catalog["loci"][gene_id])
        
        original_count = len(locus.alleles)
        locus.alleles = [a for a in locus.alleles if a.allele_id != allele_id]
        
        if len(locus.alleles) == original_count:
            return {"success": False, "message": f"等位基因 {allele_id} 不存在"}
        
        if locus.active_allele == allele_id:
            default = locus.get_default_allele()
            locus.active_allele = default.allele_id if default else ""
        
        catalog["loci"][gene_id] = locus.to_dict()
        self._save_catalog(catalog)
        
        return {
            "success": True,
            "message": f"等位基因 {allele_id} 已从 {gene_id} 移除",
            "remaining_alleles": len(locus.alleles)
        }
    
    def get_switch_history(self, gene_id: str) -> list:
        """获取等位基因切换历史"""
        catalog = self._load_catalog()
        
        if gene_id not in catalog["loci"]:
            return []
        
        locus = AllelicLocus.from_dict(catalog["loci"][gene_id])
        return locus.switch_history


def init_standard_alleles():
    """初始化标准基因的等位基因版本"""
    manager = AlleleManager()
    
    standard_alleles = [
        {
            "gene_id": "G001-parser",
            "gene_name": "TTG解析器",
            "alleles": [
                Allele(allele_id="v1-standard", name="标准解析器", 
                       description="完整解析，支持所有字段", is_default=True),
                Allele(allele_id="v2-fast", name="快速解析器",
                       description="跳过非必要字段，提升速度", allele_type="dominant"),
                Allele(allele_id="v3-strict", name="严格解析器",
                       description="完整校验，适合生产环境", allele_type="recessive"),
            ]
        },
        {
            "gene_id": "G002-analyzer",
            "gene_name": "技能分析器",
            "alleles": [
                Allele(allele_id="v1-standard", name="标准分析器",
                       description="平衡深度与速度", is_default=True),
                Allele(allele_id="v2-deep", name="深度分析器",
                       description="更深入的分析，耗时更长", allele_type="recessive"),
                Allele(allele_id="v3-quick", name="快速分析器",
                       description="快速扫描，适合批量处理", allele_type="dominant"),
            ]
        },
        {
            "gene_id": "G008-auditor",
            "gene_name": "安全审计器",
            "alleles": [
                Allele(allele_id="v1-standard", name="标准审计器",
                       description="四层纵深防御审计", is_default=True),
                Allele(allele_id="v2-light", name="轻量审计器",
                       description="快速审计，跳过部分检查", allele_type="dominant"),
                Allele(allele_id="v3-paranoid", name="严格审计器",
                       description="最严格的审计，所有检查", allele_type="recessive"),
            ]
        }
    ]
    
    for gene_def in standard_alleles:
        for allele in gene_def["alleles"]:
            manager.register_allele(gene_def["gene_id"], gene_def["gene_name"], allele)
    
    return {"initialized": len(standard_alleles), "genes": [g["gene_id"] for g in standard_alleles]}


def print_alleles_report(alleles_data: dict):
    """打印等位基因报告"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 等位基因报告 · Allele Report                           ║
╠══════════════════════════════════════════════════════════════╣
""")
    
    if "error" in alleles_data:
        print(f"║   ❌ {alleles_data['error']}")
        print("╚══════════════════════════════════════════════════════════════╝")
        return
    
    if "gene_id" in alleles_data:
        print(f"║   基因: {alleles_data['gene_id']} · {alleles_data.get('gene_name', '?')}")
        print(f"║   当前激活: {alleles_data.get('active_allele', '?')}")
        print("║")
        print("║   可用等位基因:")
        
        for allele in alleles_data.get("alleles", []):
            active_marker = "→" if allele["allele_id"] == alleles_data.get("active_allele") else " "
            default_marker = "◆" if allele.get("is_default") else " "
            type_label = allele.get("allele_type", "dominant")[:1].upper()
            
            print(f"║   {active_marker} {default_marker} [{type_label}] {allele['allele_id']:<15} {allele['name']}")
            if allele.get("description"):
                print(f"║       {allele['description']}")
        
        print("║")
        print("║   图例: → 当前激活  ◆ 默认  [D]显性 [R]隐性 [C]共显性")
    
    else:
        for gene_id, info in alleles_data.items():
            if isinstance(info, dict) and "gene_name" in info:
                active = info.get("active_allele", "?")
                count = info.get("allele_count", 0)
                print(f"║   {gene_id:<18} {info['gene_name']:<12} 激活:{active} ({count}个等位)")
    
    print("╚══════════════════════════════════════════════════════════════╝")


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("""
🧬 等位基因系统 · Allele System

用法:
    python alleles.py init                        初始化标准等位基因
    python alleles.py list [基因ID]               列出等位基因
    python alleles.py show <基因ID>               查看基因的等位详情
    python alleles.py switch <种子> <基因ID> <等位ID>  切换等位基因
    python alleles.py register <基因ID> <等位JSON>     注册新等位基因
    python alleles.py history <基因ID>            查看切换历史

示例:
    python alleles.py init
    python alleles.py list G001-parser
    python alleles.py switch seed.ttg G001-parser v2-fast
""")
        return
    
    action = sys.argv[1]
    manager = AlleleManager()
    
    if action == 'init':
        result = init_standard_alleles()
        print(f"✅ 已初始化 {result['initialized']} 个基因的等位基因")
        print(f"   基因: {', '.join(result['genes'])}")
    
    elif action == 'list':
        gene_id = sys.argv[2] if len(sys.argv) > 2 else None
        result = manager.list_alleles(gene_id)
        print_alleles_report(result)
    
    elif action == 'show' and len(sys.argv) >= 3:
        gene_id = sys.argv[2]
        result = manager.get_active_allele(gene_id)
        if "error" in result:
            print("❌", result["error"])
        else:
            print(f"\n🧬 {gene_id} · {result['gene_name']}")
            print(f"   当前激活: {result['active_allele']['allele_id'] if result['active_allele'] else '无'}")
            if result['active_allele']:
                print(f"   名称: {result['active_allele']['name']}")
                print(f"   描述: {result['active_allele'].get('description', '')}")
    
    elif action == 'switch' and len(sys.argv) >= 5:
        seed_path = os.path.expanduser(sys.argv[2])
        gene_id = sys.argv[3]
        allele_id = sys.argv[4]
        reason = sys.argv[5] if len(sys.argv) > 5 else ""
        result = manager.switch_allele(seed_path, gene_id, allele_id, reason)
        print("✅" if result["success"] else "❌", result["message"])
    
    elif action == 'register' and len(sys.argv) >= 4:
        gene_id = sys.argv[2]
        allele_json = sys.argv[3]
        try:
            allele_data = json.loads(allele_json)
            allele = Allele.from_dict(allele_data)
            result = manager.register_allele(gene_id, "", allele)
            print("✅" if result["success"] else "❌", result["message"])
        except json.JSONDecodeError:
            print("❌ 无效的JSON格式")
    
    elif action == 'history' and len(sys.argv) >= 3:
        gene_id = sys.argv[2]
        history = manager.get_switch_history(gene_id)
        if not history:
            print("暂无切换历史")
        else:
            print(f"\n📜 {gene_id} 等位基因切换历史 ({len(history)}条):\n")
            for h in history[-10:]:
                print(f"  {h['time'][:19]}  {h['from']} → {h['to']}")
                if h.get('reason'):
                    print(f"    原因: {h['reason']}")
    
    else:
        print("未知命令或参数不足")


if __name__ == "__main__":
    main()
