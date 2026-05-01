#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

PROMETHEUS_HOME = os.path.expanduser("~/.hermes/tools/prometheus")
IMMUNE_DIR = os.path.join(PROMETHEUS_HOME, "immune_memory")

os.makedirs(IMMUNE_DIR, exist_ok=True)


@dataclass
class Antigen:
    """抗原 - 需要解决的任务或问题"""

    antigen_id: str
    name: str
    type: str
    description: str = ""
    features: dict[str, Any] = field(default_factory=dict)
    context: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat()

        if not self.antigen_id:
            content = f"{self.name}{self.type}{self.description}"
            self.antigen_id = hashlib.sha256(content.encode()).hexdigest()[:12]

    def fingerprint(self) -> str:
        """生成抗原指纹"""
        import json

        data = {
            "name": self.name,
            "type": self.type,
            "features": self.features,
            "context": self.context,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Antibody:
    """抗体 - 任务解决方案或能力"""

    antibody_id: str
    name: str
    target_antigen_id: str
    solution: str = ""
    steps: list[str] = field(default_factory=list)
    effectiveness: float = 0.0
    usage_count: int = 0
    last_used: str = ""
    created: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.datetime.now().isoformat()
        if not self.last_used:
            self.last_used = self.created

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MemoryCell:
    """记忆细胞 - 长期免疫记忆存储"""

    memory_id: str
    antigen: Antigen
    antibodies: list[Antibody]
    strength: float = 0.0
    activation_count: int = 0
    last_activated: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.last_activated:
            self.last_activated = datetime.datetime.now().isoformat()

    def activate(self):
        """激活记忆细胞，增强强度"""
        self.activation_count += 1
        self.last_activated = datetime.datetime.now().isoformat()
        self.strength = min(1.0, self.strength + 0.1)

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "antigen": self.antigen.to_dict(),
            "antibodies": [a.to_dict() for a in self.antibodies],
            "strength": self.strength,
            "activation_count": self.activation_count,
            "last_activated": self.last_activated,
            "tags": self.tags,
        }


class ImmuneSystem:
    """免疫系统 - 适应性免疫记忆系统"""

    def __init__(self):
        self.memory_cells: dict[str, MemoryCell] = {}
        self.primary_response = {}
        self._load_memory()

    def _get_memory_file(self) -> str:
        return os.path.join(IMMUNE_DIR, "memory_bank.json")

    def _load_memory(self):
        memory_file = self._get_memory_file()
        if os.path.exists(memory_file):
            try:
                with open(memory_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for mem_id, mem_data in data.get("memory_cells", {}).items():
                        antigen = Antigen(**mem_data["antigen"])
                        antibodies = [Antibody(**a) for a in mem_data["antibodies"]]
                        mem_cell = MemoryCell(
                            memory_id=mem_id,
                            antigen=antigen,
                            antibodies=antibodies,
                            strength=mem_data.get("strength", 0.0),
                            activation_count=mem_data.get("activation_count", 0),
                            last_activated=mem_data.get("last_activated", ""),
                            tags=mem_data.get("tags", []),
                        )
                        self.memory_cells[mem_id] = mem_cell
            except:
                pass

    def _save_memory(self):
        memory_file = self._get_memory_file()
        data = {
            "last_updated": datetime.datetime.now().isoformat(),
            "memory_cells": {k: v.to_dict() for k, v in self.memory_cells.items()},
        }
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def present_antigen(
        self,
        name: str,
        type: str,
        description: str = "",
        features: dict[str, Any] = None,
        context: str = "",
    ) -> Antigen:
        """呈递抗原 - 提出需要解决的任务"""
        features = features or {}

        antigen = Antigen(
            antigen_id="",
            name=name,
            type=type,
            description=description,
            features=features,
            context=context,
        )

        return antigen

    def recognize_antigen(self, antigen: Antigen) -> list[tuple[MemoryCell, float]]:
        """识别抗原 - 寻找匹配的记忆细胞（抗原提呈）

        对应碳基生物学：抗原提呈细胞识别抗原
        """
        matches = []

        for _mem_id, mem_cell in self.memory_cells.items():
            similarity = self._calculate_similarity(antigen, mem_cell.antigen)
            if similarity > 0.3:
                matches.append((mem_cell, similarity))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def _calculate_similarity(self, a1: Antigen, a2: Antigen) -> float:
        """计算抗原相似度"""
        score = 0.0

        if a1.type == a2.type:
            score += 0.3

        common_features = set(a1.features.keys()) & set(a2.features.keys())
        if common_features:
            score += 0.2 * (len(common_features) / max(len(a1.features), len(a2.features), 1))

        import difflib

        name_sim = difflib.SequenceMatcher(None, a1.name, a2.name).ratio()
        score += name_sim * 0.3

        desc_sim = difflib.SequenceMatcher(None, a1.description, a2.description).ratio()
        score += desc_sim * 0.2

        return min(1.0, score)

    def generate_antibody(
        self, antigen: Antigen, solution: str, steps: list[str] = None
    ) -> Antibody:
        """生成抗体 - 创建任务解决方案"""
        steps = steps or []

        antibody = Antibody(
            antibody_id=f"AB_{hashlib.sha256(solution.encode()).hexdigest()[:8]}",
            name=f"Antibody-{antigen.name}",
            target_antigen_id=antigen.antigen_id,
            solution=solution,
            steps=steps,
            effectiveness=0.5,
        )

        return antibody

    def store_memory(
        self, antigen: Antigen, antibody: Antibody, tags: list[str] = None
    ) -> MemoryCell:
        """存储记忆 - 创建记忆细胞（长期记忆）"""
        tags = tags or []

        memory_id = f"MEM_{antigen.antigen_id}"

        memory_cell = MemoryCell(
            memory_id=memory_id, antigen=antigen, antibodies=[antibody], strength=0.5, tags=tags
        )

        self.memory_cells[memory_id] = memory_cell
        self._save_memory()

        return memory_cell

    def recall_memory(self, antigen: Antigen) -> MemoryCell | None:
        """召回记忆 - 快速应答（免疫记忆快速反应）"""
        matches = self.recognize_antigen(antigen)

        if not matches:
            return None

        best_match, similarity = matches[0]

        if similarity >= 0.6:
            best_match.activate()
            self._save_memory()
            return best_match

        return None

    def clonal_selection(self, antigen: Antigen, antibodies: list[Antibody]) -> Antibody:
        """克隆选择 - 选择最优抗体（克隆选择学说）

        对应碳基生物学：克隆选择，增殖最优B细胞
        """
        if not antibodies:
            return None

        best_ab = max(antibodies, key=lambda a: a.effectiveness * (a.usage_count + 1))

        best_ab.effectiveness = min(1.0, best_ab.effectiveness + 0.1)
        best_ab.usage_count += 1
        best_ab.last_used = datetime.datetime.now().isoformat()

        return best_ab

    def response(self, antigen: Antigen) -> dict[str, Any]:
        """免疫应答 - 完整的免疫反应流程"""
        result = {
            "antigen": antigen.to_dict(),
            "memory_hit": False,
            "best_solution": None,
            "needs_new_antibody": False,
        }

        memory_hit = self.recall_memory(antigen)

        if memory_hit:
            result["memory_hit"] = True
            result["memory_strength"] = memory_hit.strength
            result["best_solution"] = memory_hit.antibodies[0].to_dict()
            result["response_type"] = "Secondary Response (Fast)"
        else:
            result["needs_new_antibody"] = True
            result["response_type"] = "Primary Response (Slow)"

        return result

    def vaccinate(self, name: str, type: str, solution: str, description: str = "") -> MemoryCell:
        """疫苗接种 - 预先接种知识（主动免疫）"""
        antigen = self.present_antigen(name, type, description)
        antibody = self.generate_antibody(antigen, solution)
        memory_cell = self.store_memory(antigen, antibody, ["vaccine", type])
        return memory_cell

    def list_antigens(self, type: str = None) -> list[Antigen]:
        """列出所有抗原"""
        antigens = [cell.antigen for cell in self.memory_cells.values()]
        if type:
            antigens = [a for a in antigens if a.type == type]
        return antigens

    def forget_antigen(self, antigen_id: str) -> bool:
        """遗忘抗原（免疫遗忘）"""
        for mem_id, mem_cell in list(self.memory_cells.items()):
            if mem_cell.antigen.antigen_id == antigen_id:
                del self.memory_cells[mem_id]
                self._save_memory()
                return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """获取免疫系统统计"""
        return {
            "total_memories": len(self.memory_cells),
            "total_antibodies": sum(len(c.antibodies) for c in self.memory_cells.values()),
            "type_distribution": self._get_type_distribution(),
            "activation_count": sum(c.activation_count for c in self.memory_cells.values()),
        }

    def _get_type_distribution(self) -> dict[str, int]:
        dist = {}
        for cell in self.memory_cells.values():
            type_name = cell.antigen.type
            dist[type_name] = dist.get(type_name, 0) + 1
        return dist


def print_immune_response(result: dict[str, Any]):
    """打印免疫应答可视化"""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║   🦠 免疫应答 · Immune Response                          ║")
    print("╠══════════════════════════════════════════════════════════════╣")

    if result.get("memory_hit"):
        print("║   ⚡ 记忆命中！快速次级应答！                              ║")
        print(f"║   记忆强度: {result.get('memory_strength', 0):.2f}")
    else:
        print("║   🆕 初次免疫应答！需要生成新抗体...                       ║")

    if result.get("best_solution"):
        print(f"║   推荐方案: {result['best_solution']['name']}")

    print(f"║   应答类型: {result.get('response_type')}")
    print("╚══════════════════════════════════════════════════════════════╝\n")


def print_immune_stats(immune: ImmuneSystem):
    """打印免疫系统统计"""
    stats = immune.get_stats()
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║   📊 免疫记忆库 · Immune Memory Bank                     ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║   记忆细胞总数: {stats['total_memories']}")
    print(f"║   抗体总数:     {stats['total_antibodies']}")
    print(f"║   激活次数:     {stats['activation_count']}")
    print("║                                                              ║")

    print("║   抗原类型分布:")
    for type_name, count in stats.get("type_distribution", {}).items():
        print(f"║     {type_name:20} {count}个")

    print("╚══════════════════════════════════════════════════════════════╝\n")


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🦠 免疫记忆系统 · Immune Memory System

用法:
    python immune_memory.py vaccinate <名称> <类型> <方案>  # 接种疫苗
    python immune_memory.py recall <查询>              # 召回记忆
    python immune_memory.py list                        # 列出所有记忆
    python immune_memory.py stats                       # 显示统计
    python immune_memory.py test                        # 测试系统
""")
        return

    immune = ImmuneSystem()
    action = sys.argv[1]

    if action == "vaccinate" and len(sys.argv) > 4:
        name = sys.argv[2]
        type = sys.argv[3]
        solution = " ".join(sys.argv[4:])
        mem = immune.vaccinate(name, type, solution)
        print(f"\n💉 疫苗接种成功! 记忆细胞ID: {mem.memory_id}\n")

    elif action == "recall" and len(sys.argv) > 2:
        query = sys.argv[2]
        antigen = immune.present_antigen(query, "query", query)
        result = immune.response(antigen)
        print_immune_response(result)

    elif action == "list":
        antigens = immune.list_antigens()
        print(f"\n📚 免疫记忆库 ({len(antigens)} 个记忆:")
        for a in antigens:
            print(f"  [{a.timestamp[:19]}] {a.type:15} {a.name}")

    elif action == "stats":
        print_immune_stats(immune)

    elif action == "test":
        print("\n🧪 测试免疫系统...")
        immune.vaccinate("数学问题", "math", "步骤:1.分析问题 2.推导公式 3.计算结果")
        immune.vaccinate("代码编写", "coding", "步骤:1.需求分析 2.架构设计 3.编写代码 4.测试")

        test_antigen = immune.present_antigen("解数学方程", "math", "需要解二元一次方程")
        result = immune.response(test_antigen)
        print_immune_response(result)

        print_immune_stats(immune)


if __name__ == "__main__":
    main()
