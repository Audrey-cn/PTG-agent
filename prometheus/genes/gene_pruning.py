#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import json
import os
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

PROMETHEUS_HOME = os.path.expanduser("~/.prometheus/tools/prometheus")
PRUNING_DIR = os.path.join(PROMETHEUS_HOME, "pruning")

os.makedirs(PRUNING_DIR, exist_ok=True)


class PruningStrategy(Enum):
    """剪枝策略"""

    MAGNITUDE_BASED = "magnitude"
    IMPORTANCE_BASED = "importance"
    ACTIVITY_BASED = "activity"
    USAGE_BASED = "usage"


@dataclass
class GeneNode:
    """基因节点 - 表达状态"""

    gene_id: str
    name: str
    is_active: bool = True
    is_essential: bool = False
    importance: float = 1.0
    activity_score: float = 0.0
    usage_count: int = 0
    last_used: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.last_used:
            self.last_used = datetime.datetime.now().isoformat()

    def activate(self):
        """激活基因"""
        self.is_active = True
        self.activity_score = min(1.0, self.activity_score + 0.1)
        self.last_used = datetime.datetime.now().isoformat()

    def deactivate(self):
        """禁用基因"""
        self.is_active = False
        self.activity_score = max(0.0, self.activity_score - 0.05)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GeneConnection:
    """基因连接 - 基因间关系"""

    from_gene: str
    to_gene: str
    strength: float = 0.5
    is_pruned: bool = False
    relation_type: str = "regulatory"

    def to_dict(self) -> dict:
        return asdict(self)


class GeneExpressionPruner:
    """基因表达剪枝器"""

    def __init__(self):
        self.nodes: dict[str, GeneNode] = {}
        self.connections: list[GeneConnection] = []
        self.essential_genes: set[str] = set()
        self._init_default_network()

    def _init_default_network(self):
        """初始化默认网络"""
        standard_genes = [
            ("G001-parser", "TTG解析器", "foundation", True),
            ("G002-analyzer", "技能分析器", "foundation", True),
            ("G003-tracker", "生长追踪器", "growth", False),
            ("G004-packer", "种子打包器", "reproduction", True),
            ("G005-genealogist", "族谱学者", "memory", True),
            ("G006-gardener", "自管理者", "ecosystem", False),
            ("G007-dormancy", "休眠守卫", "safety", True),
            ("G008-auditor", "安全审计器", "safety", True),
        ]

        for gene_id, name, category, essential in standard_genes:
            self.add_gene(
                GeneNode(
                    gene_id=gene_id,
                    name=name,
                    category=category,
                    is_essential=essential,
                    importance=0.9 if essential else 0.5,
                )
            )

    def add_gene(self, node: GeneNode):
        """添加基因节点"""
        self.nodes[node.gene_id] = node
        if node.is_essential:
            self.essential_genes.add(node.gene_id)

    def add_connection(
        self, from_gene: str, to_gene: str, strength: float = 0.5, relation_type: str = "regulatory"
    ):
        """添加基因连接"""
        self.connections.append(
            GeneConnection(
                from_gene=from_gene, to_gene=to_gene, strength=strength, relation_type=relation_type
            )
        )

    def get_active_genes(self) -> list[GeneNode]:
        """获取当前活跃基因"""
        return [node for node in self.nodes.values() if node.is_active]

    def get_pruned_genes(self) -> list[GeneNode]:
        """获取被剪枝的基因"""
        return [node for node in self.nodes.values() if not node.is_active]

    def prune_by_magnitude(self, threshold: float = 0.3) -> int:
        """按重要性剪枝"""
        pruned_count = 0
        for _gene_id, node in self.nodes.items():
            if not node.is_essential and node.importance < threshold and node.is_active:
                node.deactivate()
                pruned_count += 1
        return pruned_count

    def prune_by_usage(self, min_usage: int = 3) -> int:
        """按使用次数剪枝"""
        pruned_count = 0
        for _gene_id, node in self.nodes.items():
            if not node.is_essential and node.usage_count < min_usage and node.is_active:
                node.deactivate()
                pruned_count += 1
        return pruned_count

    def prune_by_activity(self, inactivity_threshold: int = 10) -> int:
        """按活跃度剪枝"""
        pruned_count = 0
        now = datetime.datetime.now()

        for _gene_id, node in self.nodes.items():
            try:
                last = datetime.datetime.fromisoformat(node.last_used)
                days_inactive = (now - last).days

                if (
                    not node.is_essential
                    and days_inactive > inactivity_threshold
                    and node.is_active
                ):
                    node.deactivate()
                    pruned_count += 1
            except:
                continue

        return pruned_count

    def targeted_prune(self, gene_ids: list[str]) -> int:
        """定向剪枝"""
        pruned_count = 0
        for gene_id in gene_ids:
            if gene_id in self.nodes and not self.nodes[gene_id].is_essential:
                self.nodes[gene_id].deactivate()
                pruned_count += 1
        return pruned_count

    def activate_gene(self, gene_id: str) -> bool:
        """激活基因"""
        if gene_id in self.nodes:
            self.nodes[gene_id].activate()
            self.nodes[gene_id].usage_count += 1
            return True
        return False

    def reactivate_gene(self, gene_id: str) -> bool:
        """重新激活已剪枝的基因"""
        if gene_id in self.nodes and not self.nodes[gene_id].is_active:
            self.nodes[gene_id].activate()
            return True
        return False

    def specialize_for_task(self, task_type: str) -> list[GeneNode]:
        """为特定任务特化基因表达（细胞分化）

        对应碳基生物学：细胞分化为特定细胞类型
        """
        specialization_rules = {
            "creative": ["G002-analyzer", "G004-packer"],
            "analytical": ["G001-parser", "G002-analyzer", "G008-auditor"],
            "safe": ["G007-dormancy", "G008-auditor"],
            "reproduction": ["G003-tracker", "G004-packer", "G005-genealogist"],
            "social": ["G006-gardener", "G002-analyzer"],
        }

        keep_genes = specialization_rules.get(task_type, ["G001-parser"])

        pruned_count = 0
        for gene_id, node in self.nodes.items():
            if not node.is_essential and gene_id not in keep_genes:
                node.deactivate()
                pruned_count += 1

        return self.get_active_genes()

    def get_network_summary(self) -> dict[str, Any]:
        """获取网络摘要"""
        active = self.get_active_genes()
        pruned = self.get_pruned_genes()

        total_importance = sum(node.importance for node in self.nodes.values())

        category_counts = {}
        for node in self.nodes.values():
            cat = node.category or "unknown"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_genes": len(self.nodes),
            "active_genes": len(active),
            "pruned_genes": len(pruned),
            "essential_genes": len(self.essential_genes),
            "total_importance": total_importance,
            "category_distribution": category_counts,
            "efficiency": len(active) / max(len(self.nodes), 1),
        }

    def save_network(self, filepath: str = None):
        """保存网络"""
        if not filepath:
            filepath = os.path.join(PRUNING_DIR, "gene_network.json")

        data = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "connections": [c.to_dict() for c in self.connections],
            "essential_genes": list(self.essential_genes),
            "summary": self.get_network_summary(),
            "saved_at": datetime.datetime.now().isoformat(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_network(self, filepath: str = None):
        """加载网络"""
        if not filepath:
            filepath = os.path.join(PRUNING_DIR, "gene_network.json")

        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            for node_id, node_data in data.get("nodes", {}).items():
                self.nodes[node_id] = GeneNode(**node_data)

            self.connections = [GeneConnection(**c) for c in data.get("connections", [])]
            self.essential_genes = set(data.get("essential_genes", []))


def print_pruning_dashboard(pruner: GeneExpressionPruner):
    """打印剪枝仪表盘"""
    summary = pruner.get_network_summary()
    active = pruner.get_active_genes()

    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║   ✂️  基因表达剪枝 · Gene Expression Pruning Dashboard    ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║   总基因数: {summary['total_genes']}")
    print(f"║   活跃基因: {summary['active_genes']}  [剪枝: {summary['pruned_genes']}]")
    print(f"║   必需基因: {summary['essential_genes']}")
    print(f"║   效率: {summary['efficiency'] * 100:.1f}%")
    print("║                                                              ║")
    print("║   🟢 活跃基因列表:")

    for node in sorted(active, key=lambda n: -n.importance):
        ess = "⭐" if node.is_essential else "  "
        importance_bar = "█" * int(node.importance * 10)
        print(f"║     {ess} {node.gene_id:20} {node.name:20} {importance_bar}")

    print("╚══════════════════════════════════════════════════════════════╝\n")


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
✂️  基因表达剪枝 · Gene Expression Pruning

用法:
    python gene_pruning.py dashboard     # 显示仪表盘
    python gene_pruning.py prune <策略> # 执行剪枝
    python gene_pruning.py activate <基因ID> # 激活基因
    python gene_pruning.py specialize <任务类型> # 任务特化
    python gene_pruning.py save/load    # 保存/加载网络
""")
        return

    pruner = GeneExpressionPruner()
    action = sys.argv[1]

    if action == "dashboard":
        print_pruning_dashboard(pruner)

    elif action == "prune" and len(sys.argv) > 2:
        strategy = sys.argv[2]

        if strategy == "magnitude":
            count = pruner.prune_by_magnitude()
            print(f"\n✂️ 按重要性剪枝了 {count} 个基因")
        elif strategy == "usage":
            count = pruner.prune_by_usage()
            print(f"\n✂️ 按使用次数剪枝了 {count} 个基因")
        elif strategy == "activity":
            count = pruner.prune_by_activity()
            print(f"\n✂️ 按活跃度剪枝了 {count} 个基因")

        print_pruning_dashboard(pruner)

    elif action == "activate" and len(sys.argv) > 2:
        gene_id = sys.argv[2]
        if pruner.activate_gene(gene_id):
            print(f"\n✅ 基因 {gene_id} 已激活!")
        else:
            print(f"\n❌ 基因 {gene_id} 不存在!")

    elif action == "specialize" and len(sys.argv) > 2:
        task_type = sys.argv[2]
        active = pruner.specialize_for_task(task_type)
        print(f"\n🧬 为 {task_type} 任务特化基因表达")
        print(f"   保留了 {len(active)} 个基因")
        print_pruning_dashboard(pruner)

    elif action == "save":
        pruner.save_network()
        print("\n💾 基因网络已保存!")

    elif action == "load":
        pruner.load_network()
        print("\n📂 基因网络已加载!")


if __name__ == "__main__":
    main()
