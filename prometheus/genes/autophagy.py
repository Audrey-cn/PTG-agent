"""prometheus/genes/autophagy.py."""

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from re import Pattern
from typing import Any

from prometheus.genes.bank import GeneBank
from prometheus.storage import StorageEngine


class AutophagyLevel(Enum):
    """自噬水平"""

    BASAL = "basal"  # 本底水平（日常清理）
    INDUCED = "induced"  # 诱导水平（营养缺乏时）
    HYPERACTIVE = "hyperactive"  # 过度自噬


@dataclass
class Autophagosome:
    """自噬体 - 包裹需要降解的细胞组分"""

    autophagosome_id: str
    target_gene_id: str
    components_to_degrade: list[str]  # 要降解的组分列表
    captured_at: str
    is_complete_gene: bool
    priority: float  # 降解优先级


@dataclass
class RecycledFragment:
    """回收的代码片段（对应氨基酸）"""

    fragment_id: str
    original_gene_id: str
    fragment_type: str  # "interface", "function", "constant", "dependency"
    content: Any
    confidence: float  # 可用置信度
    sequence_hash: str


@dataclass
class AutophagyResult:
    """自噬结果"""

    autophagosome_id: str
    degraded_components: int
    fragments_recycled: list[RecycledFragment]
    resources_recovered: float  # 回收比例 (0-1)
    success: bool
    energy_gained: int  # "能量" - 释放的内存/存储


class mTORKinase:
    """mTOR激酶 - 自噬的主调控开关

    生物学：mTOR磷酸化抑制自噬起始
    当 mTOR 失活，自噬开始
    """

    def __init__(self):
        # mTOR 活性：高活性 → 抑制自噬
        self.mtor_activity: float = 0.8  # 默认抑制自噬

    def inhibit_mtor(self, inhibition_level: float = 0.8):
        """抑制mTOR → 激活自噬"""
        self.mtor_activity = max(0.0, self.mtor_activity - inhibition_level)

    def activate_mtor(self, activation_level: float = 0.8):
        """激活mTOR → 抑制自噬"""
        self.mtor_activity = min(1.0, self.mtor_activity + activation_level)

    def get_autophagy_level(self) -> AutophagyLevel:
        """根据mTOR活性得到自噬水平"""
        if self.mtor_activity > 0.6:
            return AutophagyLevel.BASAL
        elif self.mtor_activity > 0.2:
            return AutophagyLevel.INDUCED
        else:
            return AutophagyLevel.HYPERACTIVE

    def should_degrade(self, priority: float) -> bool:
        """基于优先级和mTOR活性决定是否降解"""
        threshold = 0.2 + (1.0 - self.mtor_activity) * 0.5
        return priority >= threshold


class Lysosome:
    """溶酶体 - 降解自噬体内容，回收资源"""

    def __init__(self):
        # 模式匹配：识别常见可回收片段
        self.recyclable_patterns: dict[str, Pattern] = {
            "constant": re.compile(r"^[A-Z_]+ = .+$", re.MULTILINE),
            "function_def": re.compile(r"def\s+(\w+)\s*\([^)]*\):", re.MULTILINE),
            "class_def": re.compile(r"class\s+(\w+)", re.MULTILINE),
            "import": re.compile(r"^import\s+.*|^from\s+.*\s+import", re.MULTILINE),
        }

    def digest(
        self, autophagosome: Autophagosome, gene_blueprint: dict[str, Any]
    ) -> tuple[list[RecycledFragment], float]:
        """消化自噬体内容，回收可用片段"""
        recycled: list[RecycledFragment] = []

        if autophagosome.is_complete_gene:
            recycled.extend(self._process_complete_gene(gene_blueprint))
        else:
            for comp in autophagosome.components_to_degrade:
                if comp in gene_blueprint:
                    fragment = self._extract_fragment(
                        comp, gene_blueprint[comp], autophagosome.target_gene_id
                    )
                    if fragment:
                        recycled.append(fragment)

        total_comps = (
            len(autophagosome.components_to_degrade) if not autophagosome.is_complete_gene else 1
        )
        recovery_rate = len(recycled) / max(total_comps, 1)

        return recycled, recovery_rate

    def _process_complete_gene(self, blueprint: dict[str, Any]) -> list[RecycledFragment]:
        """处理完整基因，回收各个部分"""
        recycled = []

        if "interface" in blueprint:
            frag = self._extract_fragment(
                "interface", blueprint["interface"], blueprint.get("gene_id", "unknown")
            )
            if frag:
                recycled.append(frag)

        if "constants" in blueprint:
            frag = self._extract_fragment(
                "constants", blueprint["constants"], blueprint.get("gene_id", "unknown")
            )
            if frag:
                recycled.append(frag)

        if "dependencies" in blueprint:
            frag = self._extract_fragment(
                "dependencies", blueprint["dependencies"], blueprint.get("gene_id", "unknown")
            )
            if frag:
                recycled.append(frag)

        return recycled

    def _extract_fragment(
        self, fragment_type: str, content: Any, original_gene_id: str
    ) -> RecycledFragment | None:
        """提取单个片段"""
        if content is None or (isinstance(content, (list, dict)) and not content):
            return None

        import hashlib

        content_str = str(content)
        h = hashlib.md5(f"{original_gene_id}{fragment_type}{content_str}".encode()).hexdigest()[:8]

        confidence = self._estimate_confidence(fragment_type, content)

        return RecycledFragment(
            fragment_id=f"rec_{h}",
            original_gene_id=original_gene_id,
            fragment_type=fragment_type,
            content=content,
            confidence=confidence,
            sequence_hash=h,
        )

    def _estimate_confidence(self, frag_type: str, content: Any) -> float:
        """估算片段可用置信度"""
        confidence = 0.6

        if frag_type == "constant" and content:
            confidence += 0.2
        elif frag_type == "interface" and content:
            confidence += 0.15
        elif frag_type == "dependencies" and isinstance(content, list):
            confidence += 0.1

        if isinstance(content, str) and len(content) > 1000:
            confidence -= 0.1

        return min(confidence, 1.0)


class AutophagyNetwork:
    """自噬调控网络 - 整个系统的自噬管理"""

    def __init__(self, storage: StorageEngine, gene_bank: GeneBank, data_dir: str = None):
        self.storage = storage
        self.gene_bank = gene_bank
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "_autophagy")
        os.makedirs(self.data_dir, exist_ok=True)

        self.mtor = mTORKinase()
        self.lysosome = Lysosome()

        self.pending_autophagosomes: dict[str, Autophagosome] = {}
        self.recycled_fragments: dict[str, RecycledFragment] = {}
        self.completed_results: list[AutophagyResult] = []

        self._load_pending()

    def induce_autophagy(self, nutrient_deprivation_level: float = 0.7):
        """诱导自噬 - 模拟营养缺乏激活自噬

        Args:
            nutrient_deprivation_level: 营养缺乏程度 0-1
                越高 → 越强烈抑制mTOR → 越强自噬
        """
        self.mtor.inhibit_mtor(nutrient_deprivation_level)

    def inhibit_autophagy(self):
        """抑制自噬（营养充足时）"""
        self.mtor.activate_mtor(0.8)

    def mark_for_degradation(
        self, gene_id: str, components: list[str] = None, priority: float = 0.5
    ) -> Autophagosome | None:
        """标记组件待降解

        Args:
            gene_id: 基因ID
            components: 要降解的组件列表，None标记整个基因
            priority: 降解优先级

        Returns:
            创建的自噬体
        """
        if components is None:
            components = []
            is_complete = True
        else:
            is_complete = False

        import hashlib

        ts = datetime.now().isoformat()
        h = hashlib.md5(f"{gene_id}{ts}".encode()).hexdigest()[:8]

        ap = Autophagosome(
            autophagosome_id=f"ap_{gene_id}_{h}",
            target_gene_id=gene_id,
            components_to_degrade=components,
            captured_at=ts,
            is_complete_gene=is_complete,
            priority=priority,
        )

        if self.mtor.should_degrade(priority):
            self.pending_autophagosomes[ap.autophagosome_id] = ap
            self._save_pending()
            return ap
        else:
            return None

    def mark_aged_genes(self, age_threshold_days: int = 180, usage_threshold: int = 0) -> int:
        """标记老化基因进行降解

        Returns:
            标记数量
        """
        marked = 0
        all_genes = self.gene_bank.list_genes()

        for gene in all_genes:
            gene_id = gene["gene_id"]
            age_days = gene.get("age_days", 0)
            usage_count = gene.get("usage_count", 0)

            if age_days >= age_threshold_days and usage_count <= usage_threshold:
                priority = 0.3 + (age_days / 365) * 0.4
                if self.mark_for_degradation(gene_id, None, priority):
                    marked += 1

        return marked

    def execute_autophagy(self) -> list[AutophagyResult]:
        """执行一轮自噬"""
        results = []
        level = self.mtor.get_autophagy_level()

        to_remove = []
        for ap_id, ap in self.pending_autophagosomes.items():
            if level == AutophagyLevel.BASAL and ap.priority < 0.5:
                continue

            result = self._execute_single(ap)
            results.append(result)
            to_remove.append(ap_id)

            for frag in result.fragments_recycled:
                if frag.confidence >= 0.5:
                    self.recycled_fragments[frag.fragment_id] = frag

        for ap_id in to_remove:
            del self.pending_autophagosomes[ap_id]

        self._save_pending()
        self.completed_results.extend(results)
        return results

    def get_recycled_fragments(self, min_confidence: float = 0.5) -> list[RecycledFragment]:
        """获取回收的片段"""
        return [f for f in self.recycled_fragments.values() if f.confidence >= min_confidence]

    def use_recycled_fragment(self, fragment_id: str) -> RecycledFragment | None:
        """使用回收的片段"""
        if fragment_id in self.recycled_fragments:
            frag = self.recycled_fragments[fragment_id]
            del self.recycled_fragments[fragment_id]
            self._save_pending()
            return frag
        return None

    def get_statistics(self) -> dict[str, Any]:
        """自噬统计"""
        total_recycled = sum(len(r.fragments_recycled) for r in self.completed_results)
        total_degraded = sum(r.degraded_components for r in self.completed_results)
        total_resources = sum(r.resources_recovered for r in self.completed_results)
        success_count = sum(1 for r in self.completed_results if r.success)

        by_type: dict[str, int] = {}
        for frag in self.recycled_fragments.values():
            by_type[frag.fragment_type] = by_type.get(frag.fragment_type, 0) + 1

        return {
            "mtor_activity": self.mtor.mtor_activity,
            "autophagy_level": self.mtor.get_autophagy_level().value,
            "pending_autophagosomes": len(self.pending_autophagosomes),
            "completed_cycles": len(self.completed_results),
            "successful": success_count,
            "total_degraded_components": total_degraded,
            "total_fragments_recycled": total_recycled,
            "available_fragments": len(self.recycled_fragments),
            "available_by_type": by_type,
            "average_recovery_rate": total_resources / max(len(self.completed_results), 1),
        }

    def _execute_single(self, ap: Autophagosome) -> AutophagyResult:
        """执行单个自噬体降解"""
        blueprint = self.gene_bank.get_gene(ap.target_gene_id)
        if blueprint is None:
            return AutophagyResult(
                autophagosome_id=ap.autophagosome_id,
                degraded_components=0,
                fragments_recycled=[],
                resources_recovered=0.0,
                success=False,
                energy_gained=0,
            )

        recycled, recovery_rate = self.lysosome.digest(ap, blueprint)

        degraded = len(ap.components_to_degrade) if not ap.is_complete_gene else 1

        if ap.is_complete_gene:
            self.gene_bank.remove_gene(ap.target_gene_id)

        energy = int(degraded * 100 * recovery_rate)

        return AutophagyResult(
            autophagosome_id=ap.autophagosome_id,
            degraded_components=degraded,
            fragments_recycled=recycled,
            resources_recovered=recovery_rate,
            success=True,
            energy_gained=energy,
        )

    def _load_pending(self):
        """加载待处理自噬体"""
        pending_path = os.path.join(self.data_dir, "pending_autophagosomes.json")
        if os.path.exists(pending_path):
            with open(pending_path, encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    ap = Autophagosome(**item)
                    self.pending_autophagosomes[ap.autophagosome_id] = ap

        fragments_path = os.path.join(self.data_dir, "recycled_fragments.json")
        if os.path.exists(fragments_path):
            with open(fragments_path, encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    frag = RecycledFragment(**item)
                    self.recycled_fragments[frag.fragment_id] = frag

    def _save_pending(self):
        """保存待处理"""
        pending_path = os.path.join(self.data_dir, "pending_autophagosomes.json")
        data = [asdict(ap) for ap in self.pending_autophagosomes.values()]
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        fragments_path = os.path.join(self.data_dir, "recycled_fragments.json")
        data = [asdict(frag) for frag in self.recycled_fragments.values()]
        with open(fragments_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
