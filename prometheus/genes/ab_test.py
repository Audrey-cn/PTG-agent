#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 普罗米修斯 · 基因 A/B 测试 · Gene A/B Testing           ║
║                                                              ║
║   同一种子两版基因对比效果，自动选优。                        ║
║                                                              ║
║   流程：                                                      ║
║     1. 创建变体 A（基准）和变体 B（突变）                    ║
║     2. 在相同任务上运行两个变体                              ║
║     3. 收集指标（成功率、耗时、质量评分）                    ║
║     4. 统计显著性检验                                        ║
║     5. 自动选择优胜版本                                      ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import random
import hashlib
import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════
#   数据结构
# ═══════════════════════════════════════════

class VariantStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SELECTED = "selected"     # 被选为优胜
    REJECTED = "rejected"     # 被淘汰


class TestStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GeneVariant:
    """基因变体"""
    variant_id: str           # 唯一标识
    name: str                 # 变体名称 (A/B)
    gene_config: dict         # 基因配置（突变参数）
    status: VariantStatus = VariantStatus.CREATED
    created_at: str = ""
    score: float = 0.0        # 综合得分
    metrics: Dict[str, float] = field(default_factory=dict)  # 各项指标
    runs: int = 0             # 运行次数
    successes: int = 0        # 成功次数
    total_time_ms: float = 0  # 总耗时

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.datetime.now().isoformat()

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs > 0 else 0.0

    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.runs if self.runs > 0 else 0.0

    def record_run(self, success: bool, time_ms: float, metrics: dict = None):
        """记录一次运行结果"""
        self.runs += 1
        if success:
            self.successes += 1
        self.total_time_ms += time_ms

        # 更新指标（累积平均）
        if metrics:
            for key, value in metrics.items():
                if key in self.metrics:
                    self.metrics[key] = (self.metrics[key] * (self.runs - 1) + value) / self.runs
                else:
                    self.metrics[key] = value

        # 更新综合得分
        self._update_score()

    def _update_score(self):
        """计算综合得分：成功率 * 0.6 + 速度 * 0.2 + 质量 * 0.2"""
        speed_score = max(0, 1 - self.avg_time_ms / 10000)  # 10秒内满分
        quality_score = self.metrics.get("quality", 0.5)
        self.score = (self.success_rate * 0.6 +
                     speed_score * 0.2 +
                     quality_score * 0.2)

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "gene_config": self.gene_config,
            "status": self.status.value,
            "score": round(self.score, 4),
            "success_rate": round(self.success_rate, 4),
            "avg_time_ms": round(self.avg_time_ms, 1),
            "runs": self.runs,
            "successes": self.successes,
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
        }


@dataclass
class ABTest:
    """A/B 测试实例"""
    test_id: str
    name: str
    description: str
    seed_path: str                     # 源种子
    task_prompt: str                   # 测试任务
    variant_a: GeneVariant = None      # 基准变体
    variant_b: GeneVariant = None      # 突变变体
    status: TestStatus = TestStatus.DRAFT
    created_at: str = ""
    completed_at: str = ""
    winner: str = ""                   # 优胜变体 ID
    confidence: float = 0.0            # 置信度
    runs_per_variant: int = 5          # 每个变体运行次数

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "description": self.description,
            "seed_path": self.seed_path,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "winner": self.winner,
            "confidence": round(self.confidence, 4),
            "variant_a": self.variant_a.to_dict() if self.variant_a else None,
            "variant_b": self.variant_b.to_dict() if self.variant_b else None,
        }


# ═══════════════════════════════════════════
#   A/B 测试引擎
# ═══════════════════════════════════════════

class GeneABTest:
    """基因 A/B 测试引擎
    
    流程：
      1. create_test() — 创建测试，定义变体
      2. run_test()    — 运行测试（收集指标）
      3. analyze()     — 统计分析
      4. select()      — 自动选优
    """

    def __init__(self, data_dir: str = None):
        self._data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data"
        )
        os.makedirs(self._data_dir, exist_ok=True)
        self._tests: Dict[str, ABTest] = {}
        self._load_tests()

    def _load_tests(self):
        """加载已有的测试记录"""
        test_dir = os.path.join(self._data_dir, "ab_tests")
        if not os.path.exists(test_dir):
            return

        for f in os.listdir(test_dir):
            if f.endswith(".json"):
                path = os.path.join(test_dir, f)
                try:
                    with open(path, "r") as fh:
                        data = json.load(fh)
                    test = self._deserialize_test(data)
                    if test:
                        self._tests[test.test_id] = test
                except Exception:
                    pass

    def _save_test(self, test: ABTest):
        """保存测试记录"""
        test_dir = os.path.join(self._data_dir, "ab_tests")
        os.makedirs(test_dir, exist_ok=True)
        path = os.path.join(test_dir, f"{test.test_id}.json")
        with open(path, "w") as f:
            json.dump(test.to_dict(), f, ensure_ascii=False, indent=2)

    def _deserialize_test(self, data: dict) -> Optional[ABTest]:
        """反序列化测试"""
        try:
            va = self._deserialize_variant(data.get("variant_a"))
            vb = self._deserialize_variant(data.get("variant_b"))
            return ABTest(
                test_id=data["test_id"],
                name=data["name"],
                description=data.get("description", ""),
                seed_path=data.get("seed_path", ""),
                task_prompt=data.get("task_prompt", ""),
                variant_a=va,
                variant_b=vb,
                status=TestStatus(data.get("status", "draft")),
                created_at=data.get("created_at", ""),
                completed_at=data.get("completed_at", ""),
                winner=data.get("winner", ""),
                confidence=data.get("confidence", 0.0),
            )
        except Exception:
            return None

    def _deserialize_variant(self, data: dict) -> Optional[GeneVariant]:
        """安全反序列化 GeneVariant"""
        if not data:
            return None
        try:
            status_str = data.get("status", "created")
            status = VariantStatus(status_str) if isinstance(status_str, str) else status_str
            return GeneVariant(
                variant_id=data["variant_id"],
                name=data["name"],
                gene_config=data.get("gene_config", {}),
                status=status,
                score=data.get("score", 0.0),
                metrics=data.get("metrics", {}),
                runs=data.get("runs", 0),
                successes=data.get("successes", 0),
                total_time_ms=data.get("total_time_ms", 0),
            )
        except Exception:
            return None

    # ── 创建测试 ────────────────────────────────

    def create_test(
        self,
        name: str,
        seed_path: str,
        task_prompt: str,
        gene_b_overrides: dict,
        description: str = "",
        runs_per_variant: int = 5,
    ) -> ABTest:
        """创建 A/B 测试
        
        Args:
            name: 测试名称
            seed_path: 源种子路径
            task_prompt: 测试任务
            gene_b_overrides: 变体 B 的基因覆盖参数
            description: 测试描述
            runs_per_variant: 每个变体运行次数
        """
        test_id = hashlib.md5(
            f"{name}:{time.time()}".encode()
        ).hexdigest()[:12]

        test = ABTest(
            test_id=test_id,
            name=name,
            description=description,
            seed_path=seed_path,
            task_prompt=task_prompt,
            runs_per_variant=runs_per_variant,
        )

        # 变体 A：基准（保持原始配置）
        test.variant_a = GeneVariant(
            variant_id=f"{test_id}_a",
            name="A (Baseline)",
            gene_config={"mode": "baseline"},
        )

        # 变体 B：突变
        test.variant_b = GeneVariant(
            variant_id=f"{test_id}_b",
            name="B (Mutant)",
            gene_config=gene_b_overrides,
        )

        self._tests[test_id] = test
        self._save_test(test)
        return test

    # ── 运行测试 ────────────────────────────────

    def run_test(
        self,
        test_id: str,
        evaluator: Callable = None,
    ) -> ABTest:
        """运行 A/B 测试
        
        Args:
            test_id: 测试 ID
            evaluator: 评估函数 (variant, task_result) -> {success, time_ms, metrics}
                      如果不提供，使用默认评估
        """
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"测试不存在: {test_id}")

        test.status = TestStatus.RUNNING
        self._save_test(test)

        # 运行变体 A
        test.variant_a.status = VariantStatus.RUNNING
        self._save_test(test)

        for i in range(test.runs_per_variant):
            success, time_ms, metrics = self._run_single(
                test.variant_a, test.task_prompt, evaluator
            )
            test.variant_a.record_run(success, time_ms, metrics)
            self._save_test(test)

        test.variant_a.status = VariantStatus.COMPLETED

        # 运行变体 B
        test.variant_b.status = VariantStatus.RUNNING
        self._save_test(test)

        for i in range(test.runs_per_variant):
            success, time_ms, metrics = self._run_single(
                test.variant_b, test.task_prompt, evaluator
            )
            test.variant_b.record_run(success, time_ms, metrics)
            self._save_test(test)

        test.variant_b.status = VariantStatus.COMPLETED

        # 分析结果
        self.analyze(test_id)

        test.status = TestStatus.COMPLETED
        test.completed_at = datetime.datetime.now().isoformat()
        self._save_test(test)

        return test

    def _run_single(
        self,
        variant: GeneVariant,
        task: str,
        evaluator: Callable = None,
    ) -> tuple:
        """运行单次测试"""
        start = time.time()

        if evaluator:
            try:
                result = evaluator(variant, task)
                success = result.get("success", False)
                metrics = result.get("metrics", {})
            except Exception as e:
                success = False
                metrics = {"error": str(e)}
        else:
            # 默认评估：基于基因配置的质量评估
            success = random.random() > 0.3  # 模拟
            metrics = {"quality": random.uniform(0.5, 1.0)}

        elapsed_ms = (time.time() - start) * 1000
        return success, elapsed_ms, metrics

    # ── 分析 ────────────────────────────────────

    def analyze(self, test_id: str) -> dict:
        """统计分析两个变体的差异"""
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"测试不存在: {test_id}")

        a = test.variant_a
        b = test.variant_b

        if not a or not b:
            return {"error": "缺少变体数据"}

        # 比较各项指标
        comparison = {
            "score_diff": b.score - a.score,
            "success_rate_diff": b.success_rate - a.success_rate,
            "speed_diff_ms": a.avg_time_ms - b.avg_time_ms,  # 正数表示 B 更快
        }

        # 计算置信度（简化的显著性检验）
        if a.runs >= 3 and b.runs >= 3:
            # 基于样本量和差异大小估算置信度
            diff = abs(comparison["score_diff"])
            sample_factor = min(1.0, (a.runs + b.runs) / 20)  # 样本越多置信度越高
            test.confidence = min(0.99, diff * 5 * sample_factor + 0.5)
        else:
            test.confidence = 0.5  # 样本不足，低置信度

        # 确定优胜者
        if b.score > a.score and test.confidence > 0.6:
            test.winner = b.variant_id
            b.status = VariantStatus.SELECTED
            a.status = VariantStatus.REJECTED
        elif a.score > b.score:
            test.winner = a.variant_id
            a.status = VariantStatus.SELECTED
            b.status = VariantStatus.REJECTED
        else:
            test.winner = a.variant_id  # 平局选基准
            a.status = VariantStatus.SELECTED

        self._save_test(test)

        return {
            "variant_a": a.to_dict(),
            "variant_b": b.to_dict(),
            "comparison": comparison,
            "winner": test.winner,
            "confidence": round(test.confidence, 4),
        }

    # ── 查询 ────────────────────────────────────

    def get_test(self, test_id: str) -> Optional[ABTest]:
        return self._tests.get(test_id)

    def list_tests(self, status: str = None) -> List[dict]:
        tests = list(self._tests.values())
        if status:
            tests = [t for t in tests if t.status.value == status]
        return [t.to_dict() for t in tests]

    def get_winner_config(self, test_id: str) -> Optional[dict]:
        """获取优胜变体的基因配置"""
        test = self._tests.get(test_id)
        if not test or not test.winner:
            return None

        if test.winner == test.variant_b.variant_id:
            return test.variant_b.gene_config
        return test.variant_a.gene_config

    def stats(self) -> dict:
        tests = list(self._tests.values())
        return {
            "total": len(tests),
            "completed": len([t for t in tests if t.status == TestStatus.COMPLETED]),
            "running": len([t for t in tests if t.status == TestStatus.RUNNING]),
            "draft": len([t for t in tests if t.status == TestStatus.DRAFT]),
        }


# ═══════════════════════════════════════════
#   便捷函数
# ═══════════════════════════════════════════

def quick_test(
    name: str,
    seed_path: str,
    task: str,
    gene_b_overrides: dict,
    runs: int = 5,
) -> dict:
    """快速 A/B 测试：创建 + 运行 + 分析 一步完成"""
    engine = GeneABTest()
    test = engine.create_test(
        name=name,
        seed_path=seed_path,
        task_prompt=task,
        gene_b_overrides=gene_b_overrides,
        runs_per_variant=runs,
    )
    test = engine.run_test(test.test_id)
    return engine.analyze(test.test_id)


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="基因 A/B 测试")
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="创建测试")
    p_create.add_argument("name", help="测试名称")
    p_create.add_argument("--seed", required=True, help="源种子路径")
    p_create.add_argument("--task", required=True, help="测试任务")
    p_create.add_argument("--desc", default="", help="描述")
    p_create.add_argument("--runs", type=int, default=5, help="每变体运行次数")
    p_create.add_argument("--gene-b", required=True, help="变体B基因配置JSON")

    # list
    sub.add_parser("list", help="列出测试")

    # analyze
    p_analyze = sub.add_parser("analyze", help="分析测试")
    p_analyze.add_argument("test_id", help="测试ID")

    # stats
    sub.add_parser("stats", help="统计概览")

    args = parser.parse_args()
    engine = GeneABTest()

    if args.command == "create":
        gene_b = json.loads(args.gene_b)
        test = engine.create_test(
            name=args.name,
            seed_path=args.seed,
            task_prompt=args.task,
            gene_b_overrides=gene_b,
            description=args.desc,
            runs_per_variant=args.runs,
        )
        print(f"✅ 测试已创建: {test.test_id}")
        print(f"   变体 A: {test.variant_a.name}")
        print(f"   变体 B: {test.variant_b.name}")

    elif args.command == "list":
        tests = engine.list_tests()
        if not tests:
            print("📋 无测试记录")
        for t in tests:
            print(f"  {t['test_id']}: {t['name']} [{t['status']}]")

    elif args.command == "analyze":
        result = engine.analyze(args.test_id)
        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            a = result["variant_a"]
            b = result["variant_b"]
            print(f"📊 A/B 测试分析")
            print(f"  变体 A: score={a['score']:.4f} success={a['success_rate']:.1%}")
            print(f"  变体 B: score={b['score']:.4f} success={b['success_rate']:.1%}")
            print(f"  优胜: {result['winner']}")
            print(f"  置信度: {result['confidence']:.1%}")

    elif args.command == "stats":
        stats = engine.stats()
        print(f"📊 A/B 测试统计")
        print(f"  总计: {stats['total']}")
        print(f"  已完成: {stats['completed']}")
        print(f"  运行中: {stats['running']}")
        print(f"  草稿: {stats['draft']}")


if __name__ == "__main__":
    main()
