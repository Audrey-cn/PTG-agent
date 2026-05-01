#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import json
import os
import random
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

PROMETHEUS_HOME = os.path.expanduser("~/.hermes/tools/prometheus")
RECOMBINATION_DIR = os.path.join(PROMETHEUS_HOME, "recombination")

os.makedirs(RECOMBINATION_DIR, exist_ok=True)


class RecombinationType(Enum):
    """重组类型"""

    HOMOLOGOUS = "homologous"
    VDJ = "VDJ"
    SHUFFLING = "shuffling"
    FUSION = "fusion"


@dataclass
class GeneModule:
    """基因模块 - 可重组的独立单元"""

    module_id: str
    name: str
    category: str
    functionality: list[str] = field(default_factory=list)
    is_compatible_with: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    weight: float = 1.0
    version: str = "1.0"
    created: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GenomeConfiguration:
    """基因组配置 - 模块组合"""

    config_id: str
    name: str
    modules: list[str]
    task_type: str
    fitness: float = 0.0
    tested: bool = False
    created: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class RecombinationEngine:
    """重组引擎 - 模块化重组系统"""

    def __init__(self):
        self.modules: dict[str, GeneModule] = {}
        self.configurations: dict[str, GenomeConfiguration] = {}
        self._init_standard_modules()
        self._init_presets()

    def _init_standard_modules(self):
        """初始化标准模块"""
        modules = [
            GeneModule(
                module_id="core-parser",
                name="核心解析模块",
                category="core",
                functionality=["parse_seed", "read_config"],
                dependencies=["core-utils"],
                weight=1.0,
            ),
            GeneModule(
                module_id="core-analysis",
                name="核心分析模块",
                category="core",
                functionality=["analyze_skill", "extract_features"],
                dependencies=["core-parser"],
                weight=1.0,
            ),
            GeneModule(
                module_id="creative-writer",
                name="创意写作模块",
                category="creative",
                functionality=["write_content", "generate_ideas"],
                dependencies=["core-analysis"],
                weight=0.8,
            ),
            GeneModule(
                module_id="visual-creator",
                name="视觉创作模块",
                category="creative",
                functionality=["generate_images", "design_graphics"],
                dependencies=["creative-writer"],
                weight=0.7,
            ),
            GeneModule(
                module_id="security-audit",
                name="安全审计模块",
                category="safety",
                functionality=["audit_seed", "check_safety"],
                dependencies=["core-analysis"],
                weight=1.0,
            ),
            GeneModule(
                module_id="growth-tracker",
                name="生长追踪模块",
                category="growth",
                functionality=["track_progress", "log_metrics"],
                dependencies=["core-utils"],
                weight=0.6,
            ),
            GeneModule(
                module_id="knowledge-graph",
                name="知识图谱模块",
                category="memory",
                functionality=["query_knowledge", "link_ideas"],
                dependencies=["core-parser"],
                weight=0.8,
            ),
            GeneModule(
                module_id="team-collab",
                name="团队协作模块",
                category="social",
                functionality=["manage_team", "coordinate_tasks"],
                dependencies=["core-analysis"],
                weight=0.7,
            ),
            GeneModule(
                module_id="core-utils",
                name="核心工具模块",
                category="core",
                functionality=["utility_functions", "helpers"],
                dependencies=[],
                weight=1.0,
            ),
        ]

        for mod in modules:
            self.register_module(mod)

    def _init_presets(self):
        """初始化预设配置"""
        presets = [
            GenomeConfiguration(
                config_id="preset-creative",
                name="创意配置",
                task_type="creative",
                modules=[
                    "core-parser",
                    "core-analysis",
                    "creative-writer",
                    "visual-creator",
                    "core-utils",
                ],
            ),
            GenomeConfiguration(
                config_id="preset-secure",
                name="安全配置",
                task_type="security",
                modules=["core-parser", "core-analysis", "security-audit", "core-utils"],
            ),
            GenomeConfiguration(
                config_id="preset-learning",
                name="学习配置",
                task_type="learning",
                modules=[
                    "core-parser",
                    "core-analysis",
                    "knowledge-graph",
                    "growth-tracker",
                    "core-utils",
                ],
            ),
        ]

        for config in presets:
            self.configurations[config.config_id] = config

    def register_module(self, module: GeneModule):
        """注册新模块"""
        self.modules[module.module_id] = module

    def generate_configuration(
        self, task_type: str = None, module_count: int = 5
    ) -> GenomeConfiguration:
        """生成新的基因组配置（随机组合）

        对应碳基生物学：基因重排产生多样性
        """
        available_modules = list(self.modules.keys())

        if task_type:
            available_modules = self._filter_by_category(task_type)

        if len(available_modules) > module_count:
            selected_modules = random.sample(available_modules, module_count)
        else:
            selected_modules = available_modules.copy()

        selected_modules = self._resolve_dependencies(selected_modules)

        config = GenomeConfiguration(
            config_id=f"config_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=f"自定义配置_{task_type}",
            modules=selected_modules,
            task_type=task_type or "general",
        )

        return config

    def _filter_by_category(self, task_type: str) -> list[str]:
        """根据任务类型筛选模块"""
        type_mapping = {
            "creative": ["core", "creative"],
            "security": ["core", "safety"],
            "learning": ["core", "memory", "growth"],
            "social": ["core", "social"],
        }

        categories = type_mapping.get(task_type, ["core"])

        return [mod_id for mod_id, mod in self.modules.items() if mod.category in categories]

    def _resolve_dependencies(self, modules: list[str]) -> list[str]:
        """解决依赖关系"""
        final_modules = list(set(modules))

        for mod_id in list(final_modules):
            if mod_id in self.modules:
                for dep in self.modules[mod_id].dependencies:
                    if dep not in final_modules:
                        final_modules.append(dep)

        return final_modules

    def recombine(
        self,
        config1: GenomeConfiguration,
        config2: GenomeConfiguration,
        method: RecombinationType = RecombinationType.HOMOLOGOUS,
    ) -> GenomeConfiguration:
        """重组两个配置

        对应碳基生物学：同源重组
        """
        modules1 = set(config1.modules)
        modules2 = set(config2.modules)

        common_modules = modules1 & modules2
        unique1 = modules1 - common_modules
        unique2 = modules2 - common_modules

        if method == RecombinationType.HOMOLOGOUS:
            new_modules = (
                list(common_modules)
                + list(unique1)[: len(unique1) // 2]
                + list(unique2)[: len(unique2) // 2]
            )
        elif method == RecombinationType.SHUFFLING:
            all_modules = list(modules1 | modules2)
            new_modules = random.sample(all_modules, max(len(all_modules) // 2, 3))
        elif method == RecombinationType.FUSION:
            new_modules = list(modules1 | modules2)
        else:
            new_modules = list(modules1)

        new_config = GenomeConfiguration(
            config_id=f"recombined_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=f"重组配置: {config1.name} + {config2.name}",
            modules=self._resolve_dependencies(new_modules),
            task_type=f"{config1.task_type}+{config2.task_type}",
        )

        return new_config

    def mutate(
        self, config: GenomeConfiguration, mutation_rate: float = 0.2
    ) -> GenomeConfiguration:
        """突变配置"""
        new_modules = list(config.modules)

        available_modules = list(self.modules.keys())

        for i, _mod in enumerate(new_modules):
            if random.random() < mutation_rate:
                candidates = [m for m in available_modules if m not in new_modules]
                if candidates:
                    new_modules[i] = random.choice(candidates)

        mutated = GenomeConfiguration(
            config_id=f"mutated_{config.config_id}",
            name=f"变异配置: {config.name}",
            modules=self._resolve_dependencies(new_modules),
            task_type=config.task_type,
        )

        return mutated

    def evaluate_fitness(
        self, config: GenomeConfiguration, test_cases: list[dict[str, Any]] = None
    ) -> float:
        """评估配置适应度"""
        score = 0.0

        sum(self.modules[mod].weight for mod in config.modules)
        module_count = len(config.modules)
        score += min(module_count / 6.0, 1.0) * 0.4

        if "core-parser" in config.modules and "core-analysis" in config.modules:
            score += 0.3

        if "core-utils" in config.modules:
            score += 0.1

        category_penalty = 0.0
        if len(set(self.modules[m].category for m in config.modules)) < 2:
            category_penalty = 0.2

        config.fitness = max(0.0, min(1.0, score - category_penalty))
        return config.fitness

    def evolve_population(
        self, population: list[GenomeConfiguration], generations: int = 5
    ) -> GenomeConfiguration:
        """进化种群（自然选择）"""
        current_pop = population

        for _gen in range(generations):
            for config in current_pop:
                self.evaluate_fitness(config)

            current_pop.sort(key=lambda c: c.fitness, reverse=True)
            elite = current_pop[: len(current_pop) // 2]

            offspring = []
            for i in range(len(elite)):
                for j in range(i + 1, len(elite)):
                    child = self.recombine(elite[i], elite[j])
                    child = self.mutate(child)
                    offspring.append(child)

            current_pop = elite + offspring[: len(elite)]

        for config in current_pop:
            self.evaluate_fitness(config)

        current_pop.sort(key=lambda c: c.fitness, reverse=True)
        return current_pop[0]

    def get_module_info(self, module_id: str) -> GeneModule | None:
        """获取模块信息"""
        return self.modules.get(module_id)

    def get_best_config(self, task_type: str) -> GenomeConfiguration | None:
        """获取最佳配置"""
        candidates = [c for c in self.configurations.values() if c.task_type == task_type]

        if not candidates:
            return None

        for c in candidates:
            self.evaluate_fitness(c)

        candidates.sort(key=lambda c: c.fitness, reverse=True)
        return candidates[0]

    def list_configurations(self) -> list[dict[str, Any]]:
        """列出所有配置"""
        return [c.to_dict() for c in self.configurations.values()]

    def save_configuration(self, config: GenomeConfiguration, filepath: str = None):
        """保存配置"""
        if not filepath:
            filepath = os.path.join(RECOMBINATION_DIR, f"{config.config_id}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

        self.configurations[config.config_id] = config


def print_recombination_dashboard(engine: RecombinationEngine):
    """打印重组仪表盘"""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║   🔄 模块化重组引擎 · Modular Recombination Dashboard    ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║   可用模块: {len(engine.modules)} 个")
    print(f"║   预设配置: {len(engine.configurations)} 个")
    print("║                                                              ║")

    print("║   📦 可用模块:")
    for _mod_id, mod in engine.modules.items():
        print(f"║     [{mod.category}] {mod.name} ({len(mod.functionality)}功能)")

    print("║                                                              ║")
    print("║   ⚙️  预设配置:")
    for _config_id, config in engine.configurations.items():
        engine.evaluate_fitness(config)
        fit_bar = "█" * int(config.fitness * 10)
        print(f"║     {fit_bar} {config.name} (适应度:{config.fitness:.2f})")
        print(f"║       模块数: {len(config.modules)}")

    print("╚══════════════════════════════════════════════════════════════╝\n")


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🔄 模块化重组引擎 · Modular Recombination Engine

用法:
    python modular_recombination.py dashboard         # 显示仪表盘
    python modular_recombination.py generate <类型>  # 生成配置
    python modular_recombination.py recombine <c1> <c2> # 重组配置
    python modular_recombination.py evolve           # 进化种群
""")
        return

    engine = RecombinationEngine()
    action = sys.argv[1]

    if action == "dashboard":
        print_recombination_dashboard(engine)

    elif action == "generate" and len(sys.argv) > 2:
        task_type = sys.argv[2]
        config = engine.generate_configuration(task_type)
        engine.save_configuration(config)

        print(f"\n✨ 生成了新配置: {config.name}")
        print(f"   模块: {', '.join(config.modules)}")

    elif action == "recombine" and len(sys.argv) > 3:
        c1_id = sys.argv[2]
        c2_id = sys.argv[3]

        if c1_id in engine.configurations and c2_id in engine.configurations:
            child = engine.recombine(engine.configurations[c1_id], engine.configurations[c2_id])
            engine.save_configuration(child)

            print(f"\n🔄 重组成功! 新配置: {child.name}")
            print(f"   模块: {', '.join(child.modules)}")

    elif action == "evolve":
        initial_pop = list(engine.configurations.values())
        best = engine.evolve_population(initial_pop)

        print(f"\n🏆 进化完成! 最佳配置: {best.name}")
        print(f"   适应度: {best.fitness:.3f}")


if __name__ == "__main__":
    main()
